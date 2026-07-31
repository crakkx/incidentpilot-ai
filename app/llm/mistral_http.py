"""Low-level Mistral chat-completions caller.

Shared by :class:`~app.llm.client.MistralRCAClient` (single large
``RCAReport`` schema per call) and the LangGraph pipeline in
``app.llm.graph`` (one small per-node schema per call). Keeping this in one
place means both pipelines get identical request/response handling,
timeouts, and error normalization.
"""

import json
from typing import Any

import httpx

from app.core.config import settings
from app.llm.errors import InvalidRCAOutputError, MistralRequestError


import mlflow

@mlflow.trace(name="call_mistral_chat", span_type="LLM")
def call_mistral_chat(
    *,
    messages: list[dict[str, str]],
    response_schema: dict[str, Any],
    schema_name: str,
    model_name: str,
    max_tokens: int | None = None,
) -> tuple[str, dict[str, Any]]:
    api_key = (
        settings.mistral_api_key.get_secret_value()
        if settings.mistral_api_key is not None
        else ""
    ).strip()

    if not api_key:
        raise MistralRequestError(
            "MISTRAL_API_KEY is not configured."
        )

    schema = dict(response_schema)
    schema["required"] = list(schema["properties"])

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": settings.mistral_temperature,
        "max_tokens": (
            max_tokens
            if max_tokens is not None
            else settings.mistral_max_tokens
        ),
        "random_seed": settings.mistral_random_seed,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": schema,
                "strict": True,
            },
        },
    }

    base_url = settings.mistral_base_url.rstrip("/")

    timeout = httpx.Timeout(
        timeout=settings.mistral_timeout_seconds,
        connect=10.0,
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            response.raise_for_status()

    except httpx.HTTPError as exc:
        raise MistralRequestError(
            "Could not generate RCA with Mistral. "
            f"model={model_name}, url={base_url}, error={exc}"
        ) from exc

    try:
        response_data = response.json()
        choice = response_data["choices"][0]
        content = choice["message"]["content"]

    except (ValueError, IndexError, KeyError, TypeError) as exc:
        raise InvalidRCAOutputError(
            "Mistral returned an unexpected API response."
        ) from exc

    if not isinstance(content, str):
        content = json.dumps(content)

    usage = response_data.get("usage") or {}

    generation_metadata = {
        "provider": "mistral",
        "response_id": response_data.get("id"),
        "created": response_data.get("created"),
        "done_reason": choice.get("finish_reason"),
        "prompt_eval_count": usage.get("prompt_tokens"),
        "eval_count": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }

    return content, generation_metadata
