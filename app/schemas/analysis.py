from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# ---------------------------------------------------------------------------
# Causal-strength vocabulary (shared with the eval dataset schema)
# ---------------------------------------------------------------------------
CausalStrength = Literal[
    "confirmed",
    "supported",
    "correlated",
    "unknown",
    "refuted",
]


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


# ---------------------------------------------------------------------------
# Phase-2 structured sub-models
# ---------------------------------------------------------------------------


class ObservationItem(BaseModel):
    """A single factual observation the LLM extracted from the evidence.

    Each item links back to one or more cited evidence source IDs and
    states a concise concept sentence.
    """

    id: str = Field(
        min_length=1,
        max_length=100,
        description="Short slug identifying this observation, e.g. 'obs-pool-exhausted'.",
    )

    concept: str = Field(
        min_length=1,
        max_length=500,
        description="One-sentence factual statement of what was observed.",
    )

    source_ids: list[str] = Field(
        default_factory=list,
        description="Source IDs from the supplied evidence that support this observation.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class RootCauseAssessment(BaseModel):
    """Structured separation of the failure mechanism from the suspected trigger.

    ``immediate_mechanism`` — *what* broke (e.g. "database connection pool exhausted").
    ``suspected_trigger``   — *why it broke now* (e.g. "recent deployment increased
                              connection hold time"). Omit when genuinely unknown.
    ``causal_strength``     — confidence that the trigger actually caused the mechanism.
    """

    immediate_mechanism: str = Field(
        min_length=1,
        max_length=2000,
        description="The proximate failure mechanism, stated in evidence-grounded terms.",
    )

    suspected_trigger: str | None = Field(
        default=None,
        max_length=2000,
        description="The event or condition suspected to have initiated the mechanism.",
    )

    causal_strength: CausalStrength = Field(
        default="unknown",
        description=(
            "Strength of the causal link: confirmed, supported, correlated, "
            "unknown, or refuted."
        ),
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("causal_strength", mode="before")
    @classmethod
    def normalize_causal_strength(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class EvidenceItem(BaseModel):
    excerpt: str = Field(
        min_length=1,
        max_length=2000,
    )

    explanation: str = Field(
        min_length=1,
        max_length=2000,
    )

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
    """Structured root-cause analysis report produced by the LLM.

    **Backward-compatible additions in schema v2.0.0:**
    - ``observations``  — explicit factual observations (default empty list).
    - ``root_cause``    — structured mechanism / trigger split (default None).

    The ``likely_root_cause`` prose field is preserved for existing
    consumers; ``root_cause`` carries the machine-readable equivalent.
    """

    evidence: list[EvidenceItem] = Field(
        max_length=20,
    )

    observations: list[ObservationItem] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Ordered list of factual observations extracted from the evidence. "
            "Each observation must link back to one or more supplied source IDs."
        ),
    )

    log_anomalies: list[str] = Field(
        default_factory=list,
        description="Explicitly list any anomalies, errors, or significant events found in the log evidence."
    )

    metric_anomalies: list[str] = Field(
        default_factory=list,
        description="Explicitly list any anomalies or significant data points found in the metric evidence."
    )

    contradictions_detected: str | None = Field(
        default=None,
        description="Explicitly state if there is any conflicting or contradictory evidence between logs and metrics, or write 'None'."
    )

    incident_summary: str = Field(
        min_length=1,
        max_length=3000,
    )

    likely_root_cause: str = Field(
        min_length=1,
        max_length=3000,
        description=(
            "Human-readable prose root-cause summary. "
            "Kept for backward compatibility; prefer the structured `root_cause` field."
        ),
    )

    root_cause: RootCauseAssessment | None = Field(
        default=None,
        description=(
            "Structured root-cause assessment separating the immediate failure "
            "mechanism from its suspected trigger. Populate whenever the evidence "
            "supports it."
        ),
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

    pipeline_version: str
    schema_version: str
    prompt_version: str

    report: RCAReport
