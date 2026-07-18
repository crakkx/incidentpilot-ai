from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


def normalize_text_list(
    value: Any,
    *,
    field_name: str,
    accepted_keys: tuple[str, ...],
) -> Any:
    """
    Accept the correct list[str] representation.

    Also repair a small, known LLM formatting mistake such as:
        [{"description": "Rollback the deployment"}]

    Unknown object structures are still rejected.
    """
    if not isinstance(value, list):
        return value

    normalized: list[str] = []

    for index, item in enumerate(value):
        if isinstance(item, str):
            text = item.strip()

        elif isinstance(item, dict):
            text = ""

            for key in accepted_keys:
                candidate = item.get(key)

                if isinstance(candidate, str) and candidate.strip():
                    text = candidate.strip()
                    break

            if not text:
                raise ValueError(
                    f"{field_name}[{index}] must be a string or an "
                    f"object containing one of these string fields: "
                    f"{', '.join(accepted_keys)}"
                )

        else:
            raise ValueError(
                f"{field_name}[{index}] must be a string, "
                f"not {type(item).__name__}"
            )

        if not text:
            raise ValueError(
                f"{field_name}[{index}] cannot be empty"
            )

        normalized.append(text)

    return normalized


class EvidenceItem(BaseModel):
    source_type: Literal[
        "log",
        "metric",
        "deployment",
        "runbook",
    ]

    source_id: str = Field(
        min_length=1,
        max_length=100,
    )

    excerpt: str = Field(
        min_length=1,
        max_length=2000,
    )

    explanation: str = Field(
        min_length=1,
        max_length=2000,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        cleaned = value.strip().lower()

        aliases = {
            "logs": "log",
            "metrics": "metric",
            "deployments": "deployment",
            "runbooks": "runbook",
            "document": "runbook",
            "document_chunk": "runbook",
        }

        return aliases.get(cleaned, cleaned)

    @field_validator("source_id", mode="before")
    @classmethod
    def normalize_source_id(cls, value: Any) -> str:
        if value is None:
            raise ValueError(
                "Every evidence item must contain source_id"
            )

        return str(value).strip()


class RCAReport(BaseModel):
    incident_summary: str = Field(
        min_length=1,
        max_length=3000,
    )

    likely_root_cause: str = Field(
        min_length=1,
        max_length=3000,
    )

    evidence: list[EvidenceItem] = Field(
        min_length=1,
        max_length=20,
    )

    recommended_actions: list[str] = Field(
        min_length=1,
        max_length=15,
        description=(
            "A JSON array containing plain strings only. "
            'Correct: ["Roll back the deployment"]. '
            "Never return objects containing description or action fields."
        ),
    )

    confidence: Literal[
        "low",
        "medium",
        "high",
    ]

    missing_information: list[str] = Field(
        default_factory=list,
        max_length=15,
        description=(
            "A JSON array containing plain strings only. "
            'Correct: ["Database pool limit is unavailable"].'
        ),
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator(
        "recommended_actions",
        mode="before",
    )
    @classmethod
    def normalize_recommended_actions(
        cls,
        value: Any,
    ) -> Any:
        return normalize_text_list(
            value,
            field_name="recommended_actions",
            accepted_keys=(
                "description",
                "action",
                "text",
                "recommendation",
            ),
        )

    @field_validator(
        "missing_information",
        mode="before",
    )
    @classmethod
    def normalize_missing_information(
        cls,
        value: Any,
    ) -> Any:
        return normalize_text_list(
            value,
            field_name="missing_information",
            accepted_keys=(
                "description",
                "information",
                "missing",
                "gap",
                "text",
            ),
        )

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()

        return value


class IncidentAnalysisResponse(BaseModel):
    analysis_run_id: str
    incident_id: str
    status: str
    model_name: str
    report: RCAReport