from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings
from app.llm.errors import (
    InvalidRCAOutputError,
    MistralRequestError,
    RCAClientError,
    RCARequestError,
)
from app.schemas.analysis import RCAReport

__all__ = [
    "LLMProvider",
    "RCAGenerationResult",
    "RCAClientError",
    "RCARequestError",
    "MistralRequestError",
    "InvalidRCAOutputError",
    "RCAClient",
    "normalize_llm_provider",
    "default_model_for_provider",
    "get_rca_client",
]

LLMProvider = Literal["mistral"]


@dataclass(frozen=True)
class RCAGenerationResult:
    report: RCAReport
    raw_output: str
    metadata: dict[str, Any]
    attempts: list[dict[str, Any]]


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
        **kwargs: Any,
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


def normalize_llm_provider(
    provider: str | None,
) -> LLMProvider:
    selected = (
        provider
        or settings.llm_provider
    ).strip().lower()

    if selected != "mistral":
        raise ValueError(
            "Unsupported LLM provider: "
            f"{selected}. Only 'mistral' is supported."
        )

    return selected


def default_model_for_provider(
    provider: str | None,
) -> str:
    normalize_llm_provider(provider)
    return settings.mistral_model


def get_rca_client(
    provider: str | None = None,
    model_name: str | None = None,
    pipeline: str | None = None, # Left for backwards compatibility with calling code that passes this kwarg
) -> RCAClient:
    normalize_llm_provider(provider)
    
    # Deferred import: app.llm.graph.pipeline imports RCAClient /
    # RCAGenerationResult from this module, so importing it at module
    # load time here would create a circular import.
    from app.llm.graph.pipeline import GraphRCAClient

    return GraphRCAClient(model_name=model_name)
