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

        # Compact JSON saves prompt tokens while still grounding
        # the model with the exact expected schema.
        compact_schema = json.dumps(
            schema,
            separators=(",", ":"),
        )

        compact_evidence = json.dumps(
            evidence_payload,
            separators=(",", ":"),
            default=str,
        )

        user_prompt = (
            "Generate one incident RCA report using only the supplied "
            "evidence.\n\n"
            "Return only JSON matching this schema:\n"
            f"{compact_schema}\n\n"
            "Supplied evidence:\n"
            f"{compact_evidence}"
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
    ) -> tuple[str, dict[str, Any]]:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "format": RCAReport.model_json_schema(),
            "options": {
                "temperature": settings.ollama_temperature,
                "num_ctx": settings.ollama_num_ctx,
                "num_predict": settings.ollama_num_predict,
                "seed": settings.ollama_seed,
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
                f"model={self.model_name}, "
                f"url={self.base_url}, "
                f"error={exc}"
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
                "Ollama returned an unexpected API response."
            ) from exc

        if not isinstance(content, str):
            content = json.dumps(content)

        generation_metadata = {
            "done_reason": response_data.get("done_reason"),
            "prompt_eval_count": response_data.get(
                "prompt_eval_count"
            ),
            "eval_count": response_data.get("eval_count"),
            "total_duration": response_data.get(
                "total_duration"
            ),
            "load_duration": response_data.get(
                "load_duration"
            ),
        }

        return content, generation_metadata

    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        messages = self._build_messages(
            evidence_payload=evidence_payload,
        )

        last_content = ""
        last_metadata: dict[str, Any] = {}
        last_validation_error: ValidationError | None = None

        for attempt in range(2):
            content, metadata = self._call_ollama(
                messages=messages,
            )

            last_content = content
            last_metadata = metadata

            try:
                return RCAReport.model_validate_json(
                    content
                )

            except ValidationError as exc:
                last_validation_error = exc

                if attempt == 0:
                    validation_errors = json.dumps(
                        exc.errors(),
                        separators=(",", ":"),
                        default=str,
                    )

                    correction_instruction = (
                        "The previous response failed schema validation. "
                        "Return the complete corrected JSON object only.\n\n"
                        "Critical representation rules:\n"
                        "- recommended_actions must be an array of strings.\n"
                        "- missing_information must be an array of strings.\n"
                        "- Do not put description, action, or text objects inside those arrays.\n"
                        "- Every evidence item must include source_type, source_id, "
                        "excerpt, and explanation.\n\n"
                        'Correct example: "recommended_actions": '
                        '["Roll back the deployment", "Inspect slow queries"]\n\n'
                        'Incorrect example: "recommended_actions": '
                        '[{"description": "Roll back the deployment"}]\n\n'
                        f"Validation errors:\n{validation_errors}"
                    )

                    if metadata.get("done_reason") == "length":
                        correction_instruction += (
                            "\nThe previous answer was truncated. "
                            "Use shorter summaries and fewer evidence "
                            "items, but return a complete JSON object."
                        )

                    messages.extend(
                        [
                            {
                                "role": "assistant",
                                "content": content,
                            },
                            {
                                "role": "user",
                                "content": correction_instruction,
                            },
                        ]
                    )

        error_details = (
            last_validation_error.errors()
            if last_validation_error
            else []
        )

        raise InvalidRCAOutputError(
            "Ollama failed RCA schema validation after two attempts. "
            f"generation_metadata="
            f"{json.dumps(last_metadata, default=str)}; "
            f"validation_errors="
            f"{json.dumps(error_details, default=str)}; "
            f"raw_output={last_content[:1500]!r}"
        )


def get_rca_client() -> RCAClient:
    return OllamaRCAClient()