"""Structured output schemas for each node in the RCA LangGraph pipeline.

Every schema here is deliberately narrower than :class:`~app.schemas.analysis
.RCAReport` — each node only has to produce the slice of the final report
that its stage is responsible for. Sub-models (``EvidenceItem``,
``ObservationItem``, ``RootCauseAssessment``) are reused directly from
``app.schemas.analysis`` so the pipeline's final assembly step in
``app.llm.graph.pipeline`` can compose them into a valid ``RCAReport``
without a translation layer.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.analysis import (
    CausalStrength,
    EvidenceItem,
    ObservationItem,
    RootCauseAssessment,
    normalize_text_list,
)


class HypothesisResult(BaseModel):
    """Output of the initial hypothesis node (Phase 5 agentic loop).

    The model states its best initial guess about the root cause and lists
    the specific information gaps it would need resolved to be more confident.
    Each ``gap_queries`` entry becomes a tool call in the investigation loop.
    """

    hypothesis: str = Field(
        min_length=1,
        max_length=2000,
        description=(
            "Best initial hypothesis about the root cause, grounded only in "
            "the evidence already extracted. Must be concrete, not generic."
        ),
    )

    gap_queries: list[str] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Ordered list of specific information gaps that would strengthen "
            "or refute the hypothesis. Each entry should describe one piece of "
            "evidence to look up, e.g. 'Fetch CPU metric for payment-service "
            "in the last 30 minutes' or 'Get recent logs for checkout-api "
            "with ERROR level'. Leave empty if the existing evidence is already "
            "sufficient."
        ),
    )

    confidence_so_far: Literal["low", "medium", "high"] = Field(
        default="low",
        description=(
            "How confident the model is in its hypothesis given the current "
            "evidence, BEFORE any additional tool calls. 'low' means important "
            "gaps exist; 'high' means the existing evidence is already clear."
        ),
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("gap_queries", mode="before")
    @classmethod
    def _normalize_gaps(cls, value: Any) -> Any:
        return normalize_text_list(
            value,
            field_name="gap_queries",
            accepted_keys=("query", "gap", "description", "text"),
        )



class ExtractionResult(BaseModel):
    """Output of the anomaly-extraction node.

    Scoped to one job: pull anomalies and literal entity names out of noisy
    evidence, without also having to reason about causality or actions.
    """

    log_anomalies: list[str] = Field(
        default_factory=list,
        max_length=15,
        description="Distinct anomalies or errors found in the log evidence, noise filtered out.",
    )

    metric_anomalies: list[str] = Field(
        default_factory=list,
        max_length=15,
        description="Distinct anomalies or notable data points found in the metric evidence.",
    )

    deployment_events: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Distinct deployment/release events found in the deployment evidence.",
    )

    entity_glossary: list[str] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Literal names copied verbatim from the evidence that a remediation "
            "step might need to reference: process names, tool names, pod/service "
            "names, environment variable names, config flags."
        ),
    )

    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        max_length=20,
        description="One evidence item per anomaly/event listed above, grounding it in the supplied data.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator(
        "log_anomalies",
        "metric_anomalies",
        "deployment_events",
        "entity_glossary",
        mode="before",
    )
    @classmethod
    def _normalize_lists(cls, value: Any, info) -> Any:
        return normalize_text_list(
            value,
            field_name=info.field_name,
            accepted_keys=("description", "text", "value", "name"),
        )


class AnomalyCrossCheck(BaseModel):
    anomaly: str = Field(min_length=1, max_length=300)

    verdict: Literal[
        "confirmed_by_metric",
        "contradicted_by_metric",
        "no_related_metric",
    ]

    rationale: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ContradictionResult(BaseModel):
    """Output of the cross-validation node.

    Forces an explicit per-anomaly verdict instead of a single free-form
    "contradictions_detected" sentence buried among many other instructions,
    which is what the single-call prompt already asks for but empirically
    fails at (confirmation-bias cases rca-027/028).
    """

    cross_checks: list[AnomalyCrossCheck] = Field(
        default_factory=list,
        max_length=20,
    )

    contradictions_detected: str | None = Field(
        default=None,
        max_length=1000,
        description="Plain-English summary of every contradiction found, or null if none were found.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class SynthesisResult(BaseModel):
    """Output of the hypothesis-synthesis node.

    ``confidence`` is deliberately absent — it is computed deterministically
    in ``app.llm.graph.confidence`` from ``supporting_evidence_ids``,
    ``missing_information``, and ``contradiction_conflicts_with_mechanism``
    rather than self-reported by the model.
    """

    observations: list[ObservationItem] = Field(
        default_factory=list,
        max_length=20,
    )

    incident_summary: str = Field(min_length=1, max_length=3000)

    likely_root_cause: str = Field(min_length=1, max_length=3000)

    root_cause: RootCauseAssessment | None = Field(default=None)

    trigger_status: Literal[
        "identified",
        "same_as_mechanism",
        "external_unknown",
    ] = Field(
        default="identified",
        description=(
            "How the suspected trigger relates to the mechanism. "
            "'identified': a distinct triggering event or condition is "
            "named and backed by evidence. 'same_as_mechanism': the "
            "mechanism is self-caused and there is no separate trigger "
            "(e.g. a disk filled to capacity, a slow query is itself the "
            "cause). 'external_unknown': the mechanism is clearly evidenced "
            "but its true trigger lies outside the observed evidence (e.g. "
            "an opaque upstream or third-party dependency)."
        ),
    )

    missing_information: list[str] = Field(
        default_factory=list,
        max_length=15,
    )

    supporting_evidence_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Evidence source_ids (from the extraction stage) that directly support the chosen root_cause mechanism.",
    )

    contradiction_conflicts_with_mechanism: bool = Field(
        default=False,
        description="True only if a contradiction identified earlier is about the same mechanism proposed here.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("missing_information", mode="before")
    @classmethod
    def _normalize_missing_information(cls, value: Any) -> Any:
        return normalize_text_list(
            value,
            field_name="missing_information",
            accepted_keys=("description", "information", "missing", "gap", "text"),
        )

    @field_validator("supporting_evidence_ids", mode="before")
    @classmethod
    def _normalize_supporting_evidence_ids(cls, value: Any) -> Any:
        return normalize_text_list(
            value,
            field_name="supporting_evidence_ids",
            accepted_keys=("id", "source_id", "text"),
        )

    @field_validator("trigger_status", mode="before")
    @classmethod
    def _normalize_trigger_status(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class ValidationResult(BaseModel):
    """Output of the adversarial-validation node.

    This node runs *after* synthesis and tries to break the proposed root
    cause: it states the strongest evidence-based objection, then re-judges
    ``causal_strength`` and ``trigger_status`` in light of that objection.
    Its adjusted verdict overrides synthesis before confidence is calibrated,
    so it is the pipeline's final authority on how strong the causal claim is
    — that is what corrects the model's tendency to over- or under-call
    causal_strength on a single synthesis pass.
    """

    strongest_objection: str = Field(
        min_length=1,
        max_length=1200,
        description=(
            "The single strongest evidence-based reason the proposed root "
            "cause might be wrong or overstated. If, after genuinely trying, "
            "no real objection exists, say so explicitly."
        ),
    )

    adjusted_causal_strength: CausalStrength = Field(
        description=(
            "The causal_strength justified AFTER weighing the objection "
            "against the evidence. Lower it if the objection undermines the "
            "claim; keep or raise it only if the objection is weak or is mere "
            "background noise."
        ),
    )

    adjusted_trigger_status: Literal[
        "identified",
        "same_as_mechanism",
        "external_unknown",
    ] = Field(
        default="identified",
        description=(
            "The trigger_status justified after validation, using the same "
            "meanings as the synthesis stage."
        ),
    )

    contradiction_conflicts_with_mechanism: bool = Field(
        default=False,
        description=(
            "True if a real contradiction in the evidence directly conflicts "
            "with the proposed mechanism (not merely with peripheral details)."
        ),
    )

    rationale: str = Field(
        min_length=1,
        max_length=1500,
        description="One or two sentences explaining the adjusted verdict.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("adjusted_causal_strength", mode="before")
    @classmethod
    def _normalize_causal_strength(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("adjusted_trigger_status", mode="before")
    @classmethod
    def _normalize_trigger_status(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class ActionResult(BaseModel):
    """Output of the action-recommendation node."""

    recommended_actions: list[str] = Field(
        min_length=1,
        max_length=15,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("recommended_actions", mode="before")
    @classmethod
    def _normalize_actions(cls, value: Any) -> Any:
        return normalize_text_list(
            value,
            field_name="recommended_actions",
            accepted_keys=("description", "action", "text", "recommendation"),
        )
