import json

import httpx
from pydantic import SecretStr

from app.core.config import settings
from app.llm.client import (
    MistralRCAClient,
    get_rca_client,
)
from app.llm.prompts import RCA_SYSTEM_PROMPT


def sample_report() -> dict:
    return {
        "incident_summary": (
            "Checkout requests timed out."
        ),
        "likely_root_cause": (
            "The upstream payment provider "
            "timed out."
        ),
        "evidence": [
            {
                "source_type": "log",
                "source_id": "log-1",
                "excerpt": (
                    "payment provider timeout"
                ),
                "explanation": (
                    "The application recorded "
                    "the upstream timeout."
                ),
            }
        ],
        "recommended_actions": [
            "Inspect the payment provider."
        ],
        "confidence": "medium",
        "missing_information": [],
    }


def test_mistral_client_uses_strict_schema(
    monkeypatch,
):
    captured_request = {}
    real_client = httpx.Client

    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        captured_request["request"] = request
        captured_request["payload"] = (
            json.loads(request.content)
        )

        return httpx.Response(
            200,
            request=request,
            json={
                "id": "completion-1",
                "created": 123,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                sample_report()
                            )
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 700,
                    "completion_tokens": 120,
                    "total_tokens": 820,
                },
            },
        )

    transport = httpx.MockTransport(
        handle_request
    )

    monkeypatch.setattr(
        settings,
        "mistral_api_key",
        SecretStr("test-key"),
    )
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(
            transport=transport,
            **kwargs,
        ),
    )

    client = MistralRCAClient(
        model_name="mistral-small-latest"
    )
    result = client.generate_rca_with_debug(
        {
            "logs": [
                {
                    "id": "log-1",
                    "message": (
                        "payment provider timeout"
                    ),
                }
            ]
        }
    )

    request = captured_request["request"]
    payload = captured_request["payload"]

    assert request.url.path == (
        "/v1/chat/completions"
    )
    assert request.headers[
        "authorization"
    ] == "Bearer test-key"
    assert payload["model"] == (
        "mistral-small-latest"
    )
    assert payload["messages"][0] == {
        "role": "system",
        "content": RCA_SYSTEM_PROMPT,
    }
    assert payload["response_format"][
        "type"
    ] == "json_schema"
    assert payload["response_format"][
        "json_schema"
    ]["strict"] is True
    assert "missing_information" in (
        payload["response_format"][
            "json_schema"
        ]["schema"]["required"]
    )
    assert result.report.confidence == "medium"
    assert result.metadata["provider"] == (
        "mistral"
    )
    assert result.metadata[
        "prompt_eval_count"
    ] == 700


def test_client_factory_selects_mistral():
    client = get_rca_client(
        provider="mistral",
        model_name="mistral-small-latest",
    )

    assert isinstance(
        client,
        MistralRCAClient,
    )
