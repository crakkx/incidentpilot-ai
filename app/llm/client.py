import json
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.llm.prompts import RCA_SYSTEM_PROMPT
from app.schemas.analysis import RCAReport


class RCAClientError(RuntimeError):
    pass


class OllamaRequestError(RCAClientError):
    pass


class InvalidRCAOutputError(RCAClientError):
    pass


class RCAClient(ABC):
    @abstractmethod
    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        raise NotImplementedError


class OllamaRCAClient(RCAClient):
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model_name = settings.ollama_model

        self.timeout = httpx.Timeout(
            timeout=settings.ollama_timeout_seconds,
            connect=10.0,
        )

    def _build_messages(
        self,
        evidence_payload: dict[str, Any],
    ) -> list[dict[str, str]]:
        schema = RCAReport.model_json_schema()

        user_prompt = (
            "Generate an RCA report using only the supplied evidence.\n\n"
            "The report must conform exactly to this JSON schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            "Incident evidence:\n"
            f"{json.dumps(evidence_payload, indent=2, default=str)}"
        )

        return [
            {
                "role": "system",
                "content": RCA_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

    def _call_ollama(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "format": RCAReport.model_json_schema(),
            "options": {
                "temperature": settings.ollama_temperature,
                "num_ctx": settings.ollama_num_ctx,
            },
            "keep_alive": settings.ollama_keep_alive,
        }

        try:
            with httpx.Client(
                timeout=self.timeout,
            ) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )

                response.raise_for_status()

        except httpx.HTTPError as exc:
            raise OllamaRequestError(
                "Could not generate RCA with Ollama. "
                f"Model={self.model_name}, "
                f"URL={self.base_url}. "
                f"Original error: {exc}"
            ) from exc

        try:
            response_data = response.json()
            content = response_data["message"]["content"]

        except (
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            raise InvalidRCAOutputError(
                "Ollama returned an unexpected response format."
            ) from exc

        if not isinstance(content, str):
            content = json.dumps(content)

        return content

    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        messages = self._build_messages(
            evidence_payload
        )

        validation_error: ValidationError | None = None

        # Two attempts help a small local model recover from
        # an occasional schema mistake.
        for attempt in range(2):
            content = self._call_ollama(messages)

            try:
                return RCAReport.model_validate_json(
                    content
                )

            except ValidationError as exc:
                validation_error = exc

                if attempt == 0:
                    messages.extend(
                        [
                            {
                                "role": "assistant",
                                "content": content,
                            },
                            {
                                "role": "user",
                                "content": (
                                    "The previous response failed schema "
                                    "validation. Correct it and return only "
                                    "valid JSON matching the schema. "
                                    f"Validation errors: {exc.errors()}"
                                ),
                            },
                        ]
                    )

        raise InvalidRCAOutputError(
            "Ollama did not produce a valid RCA report "
            f"after two attempts: {validation_error}"
        )


def get_rca_client() -> RCAClient:
    return OllamaRCAClient()
