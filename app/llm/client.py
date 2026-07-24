import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.llm.prompts import RCA_SYSTEM_PROMPT
from app.schemas.analysis import RCAReport


LLMProvider = Literal["ollama", "mistral"]


@dataclass(frozen=True)
class RCAGenerationResult:
    report: RCAReport
    raw_output: str
    metadata: dict[str, Any]
    attempts: list[dict[str, Any]]


class RCAClientError(RuntimeError):
    pass


class RCARequestError(RCAClientError):
    provider = "llm"


class OllamaRequestError(RCARequestError):
    provider = "ollama"


class MistralRequestError(RCARequestError):
    provider = "mistral"


class InvalidRCAOutputError(RCAClientError):
    def __init__(
        self,
        message: str,
        *,
        debug: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)

        self.debug = debug or {
            "attempts": [],
            "final_raw_output": None,
            "final_metadata": {},
            "final_validation_errors": [],
        }


class RCAClient(ABC):
    provider: LLMProvider | None = None

    @abstractmethod
    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        raise NotImplementedError

    def generate_rca_with_debug(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAGenerationResult:
        report = self.generate_rca(
            evidence_payload
        )

        raw_output = report.model_dump_json(
            indent=2
        )

        metadata = {
            "source": "custom_rca_client",
            "provider": self.provider,
        }

        return RCAGenerationResult(
            report=report,
            raw_output=raw_output,
            metadata=metadata,
            attempts=[
                {
                    "attempt": 1,
                    "raw_output": raw_output,
                    "metadata": metadata,
                    "validation_errors": [],
                }
            ],
        )


class StructuredRCAClient(RCAClient):
    model_name: str

    def _build_messages(
        self,
        evidence_payload: dict[str, Any],
    ) -> list[dict[str, str]]:
        schema = RCAReport.model_json_schema()

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

    @abstractmethod
    def _call_model(
        self,
        messages: list[dict[str, str]],
    ) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError

    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        return self.generate_rca_with_debug(
            evidence_payload
        ).report

    def generate_rca_with_debug(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAGenerationResult:
        messages = self._build_messages(
            evidence_payload=evidence_payload,
        )

        attempts: list[dict[str, Any]] = []

        for attempt_index in range(2):
            content, metadata = self._call_model(
                messages=messages,
            )

            attempt_record: dict[str, Any] = {
                "attempt": attempt_index + 1,
                "raw_output": content,
                "metadata": metadata,
                "validation_errors": [],
            }

            try:
                report = RCAReport.model_validate_json(
                    content
                )

                attempts.append(attempt_record)

                return RCAGenerationResult(
                    report=report,
                    raw_output=content,
                    metadata=metadata,
                    attempts=attempts,
                )

            except ValidationError as exc:
                errors = exc.errors(
                    include_url=False
                )

                attempt_record[
                    "validation_errors"
                ] = errors

                attempts.append(attempt_record)

                if attempt_index == 0:
                    validation_errors_json = json.dumps(
                        errors,
                        separators=(",", ":"),
                        default=str,
                    )

                    messages.extend(
                        [
                            {
                                "role": "assistant",
                                "content": content,
                            },
                            {
                                "role": "user",
                                "content": (
                                    "The previous response failed "
                                    "schema validation. Return the "
                                    "complete corrected JSON object "
                                    "only.\n\n"
                                    "recommended_actions and "
                                    "missing_information must be "
                                    "arrays of plain strings.\n\n"
                                    "Use exact lowercase enum values.\n\n"
                                    "Every evidence item must include "
                                    "excerpt, explanation, source_type "
                                    "and source_id. Start from an exact "
                                    "supplied excerpt before choosing "
                                    "the source ID. If direct evidence "
                                    "is missing, leave evidence empty, "
                                    "add missing_information, and use "
                                    "low confidence.\n\n"
                                    "Validation errors:\n"
                                    f"{validation_errors_json}"
                                ),
                            },
                        ]
                    )

        final_attempt = attempts[-1]

        debug = {
            "attempts": attempts,
            "final_raw_output": final_attempt[
                "raw_output"
            ],
            "final_metadata": final_attempt[
                "metadata"
            ],
            "final_validation_errors": final_attempt[
                "validation_errors"
            ],
        }

        raise InvalidRCAOutputError(
            f"{self.provider.title()} failed RCA schema validation "
            "after two attempts.",
            debug=debug,
        )


class OllamaRCAClient(StructuredRCAClient):
    provider = "ollama"

    def __init__(
        self,
        model_name: str | None = None,
    ) -> None:
        self.base_url = (
            settings.ollama_base_url.rstrip(
                "/"
            )
        )

        self.model_name = (
            model_name
            or settings.ollama_model
        )

        self.timeout = httpx.Timeout(
            timeout=(
                settings
                .ollama_timeout_seconds
            ),
            connect=10.0,
        )

    def _call_model(
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

        eval_duration_ns = response_data.get(
            "eval_duration"
        )

        eval_count = response_data.get(
            "eval_count"
        )

        tokens_per_second = None

        if (
            eval_duration_ns
            and eval_count is not None
            and eval_duration_ns > 0
        ):
            tokens_per_second = (
                eval_count
                / (eval_duration_ns / 1_000_000_000)
            )

        generation_metadata = {
            "provider": self.provider,
            "done_reason": response_data.get(
                "done_reason"
            ),
            "prompt_eval_count": response_data.get(
                "prompt_eval_count"
            ),
            "eval_count": eval_count,
            "total_duration_ms": (
                response_data.get(
                    "total_duration",
                    0,
                )
                / 1_000_000
            ),
            "load_duration_ms": (
                response_data.get(
                    "load_duration",
                    0,
                )
                / 1_000_000
            ),
            "prompt_eval_duration_ms": (
                response_data.get(
                    "prompt_eval_duration",
                    0,
                )
                / 1_000_000
            ),
            "eval_duration_ms": (
                response_data.get(
                    "eval_duration",
                    0,
                )
                / 1_000_000
            ),
            "tokens_per_second": (
                round(tokens_per_second, 2)
                if tokens_per_second is not None
                else None
            ),
        }

        return content, generation_metadata


class MistralRCAClient(StructuredRCAClient):
    provider = "mistral"

    def __init__(
        self,
        model_name: str | None = None,
    ) -> None:
        self.base_url = (
            settings.mistral_base_url.rstrip(
                "/"
            )
        )

        self.model_name = (
            model_name
            or settings.mistral_model
        )

        self.timeout = httpx.Timeout(
            timeout=(
                settings
                .mistral_timeout_seconds
            ),
            connect=10.0,
        )

    def _call_model(
        self,
        messages: list[dict[str, str]],
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

        response_schema = (
            RCAReport.model_json_schema()
        )
        response_schema["required"] = list(
            response_schema["properties"]
        )

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": settings.mistral_temperature,
            "max_tokens": settings.mistral_max_tokens,
            "random_seed": settings.mistral_random_seed,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "rca_report",
                    "schema": response_schema,
                    "strict": True,
                },
            },
        }

        try:
            with httpx.Client(
                timeout=self.timeout,
            ) as client:
                response = client.post(
                    (
                        f"{self.base_url}"
                        "/v1/chat/completions"
                    ),
                    headers={
                        "Authorization": (
                            f"Bearer {api_key}"
                        ),
                        "Content-Type": (
                            "application/json"
                        ),
                    },
                    json=payload,
                )

                response.raise_for_status()

        except httpx.HTTPError as exc:
            raise MistralRequestError(
                "Could not generate RCA with Mistral. "
                f"model={self.model_name}, "
                f"url={self.base_url}, "
                f"error={exc}"
            ) from exc

        try:
            response_data = response.json()
            choice = response_data["choices"][0]
            content = choice["message"]["content"]

        except (
            ValueError,
            IndexError,
            KeyError,
            TypeError,
        ) as exc:
            raise InvalidRCAOutputError(
                "Mistral returned an unexpected API response."
            ) from exc

        if not isinstance(content, str):
            content = json.dumps(content)

        usage = response_data.get("usage") or {}

        generation_metadata = {
            "provider": self.provider,
            "response_id": response_data.get("id"),
            "created": response_data.get("created"),
            "done_reason": choice.get(
                "finish_reason"
            ),
            "prompt_eval_count": usage.get(
                "prompt_tokens"
            ),
            "eval_count": usage.get(
                "completion_tokens"
            ),
            "total_tokens": usage.get(
                "total_tokens"
            ),
        }

        return content, generation_metadata


def normalize_llm_provider(
    provider: str | None,
) -> LLMProvider:
    selected = (
        provider
        or settings.llm_provider
    ).strip().lower()

    if selected not in {
        "ollama",
        "mistral",
    }:
        raise ValueError(
            "Unsupported LLM provider: "
            f"{selected}"
        )

    return selected


def default_model_for_provider(
    provider: str | None,
) -> str:
    selected = normalize_llm_provider(
        provider
    )

    if selected == "mistral":
        return settings.mistral_model

    return settings.ollama_model


def get_rca_client(
    provider: str | None = None,
    model_name: str | None = None,
) -> RCAClient:
    selected = normalize_llm_provider(
        provider
    )

    if selected == "mistral":
        return MistralRCAClient(
            model_name=model_name
        )

    return OllamaRCAClient(
        model_name=model_name
    )
