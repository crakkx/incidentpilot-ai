import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


SourceType = Literal[
    "log",
    "metric",
    "deployment",
    "runbook",
]

ScenarioType = Literal[
    "clear_cause",
    "ambiguous",
    "insufficient_evidence",
    "conflicting_evidence",
    "false_correlation",
    "multi_cause",
    "numeric_edge_case",
    "temporal_edge_case",
    "noisy_evidence",
]

Difficulty = Literal[
    "easy",
    "medium",
    "hard",
]

Confidence = Literal[
    "low",
    "medium",
    "high",
]

CausalStrength = Literal[
    "confirmed",
    "supported",
    "correlated",
    "unknown",
    "refuted",
]

DeploymentCausalityPolicy = Literal[
    "forbidden",
    "correlation_only",
    "supported",
    "confirmed",
    "not_applicable",
]


class EvalIncident(BaseModel):
    id: str
    title: str
    description: str
    service_name: str
    severity: str
    started_at: datetime

    model_config = ConfigDict(
        extra="forbid",
    )


class EvalEvidenceItem(BaseModel):
    id: str
    source_type: SourceType
    timestamp: datetime | None = None

    # Human-readable canonical content.
    content: str = Field(
        min_length=1,
    )

    # Source-specific structured values.
    data: dict[str, Any] = Field(
        default_factory=dict,
    )

    model_config = ConfigDict(
        extra="forbid",
    )


class ObservationExpectation(BaseModel):
    id: str
    concept: str

    acceptable_source_ids: list[str] = Field(
        default_factory=list,
    )

    keywords_any: list[str] = Field(
        default_factory=list,
    )

    required: bool = True

    model_config = ConfigDict(
        extra="forbid",
    )


class NumericFactExpectation(BaseModel):
    id: str
    source_id: str
    name: str
    value: float
    unit: str | None = None
    tolerance: float = 0.0

    model_config = ConfigDict(
        extra="forbid",
    )


class TemporalFactExpectation(BaseModel):
    id: str

    left_source_id: str
    right_source_id: str

    relation: Literal[
        "before",
        "after",
        "overlaps",
    ]

    max_gap_seconds: int | None = None

    model_config = ConfigDict(
        extra="forbid",
    )


class RootCauseExpectation(BaseModel):
    immediate_mechanism_keywords_any: list[str]

    suspected_trigger_keywords_any: list[str] = (
        Field(default_factory=list)
    )

    causal_strength: CausalStrength

    acceptable_confidence: list[Confidence]

    must_distinguish_mechanism_and_trigger: bool = (
        False
    )

    model_config = ConfigDict(
        extra="forbid",
    )


class ActionExpectation(BaseModel):
    required_categories: list[str] = Field(
        default_factory=list,
    )

    required_keyword_groups: list[list[str]] = (
        Field(default_factory=list)
    )

    forbidden_keywords: list[str] = Field(
        default_factory=list,
    )

    model_config = ConfigDict(
        extra="forbid",
    )


class CausalLanguagePolicy(BaseModel):
    deployment_causality: (
        DeploymentCausalityPolicy
    )

    forbidden_phrases: list[str] = Field(
        default_factory=list,
    )

    model_config = ConfigDict(
        extra="forbid",
    )


class CaseExpectations(BaseModel):
    observations: list[
        ObservationExpectation
    ] = Field(default_factory=list)

    root_cause: RootCauseExpectation

    actions: ActionExpectation = Field(
        default_factory=ActionExpectation,
    )

    numeric_facts: list[
        NumericFactExpectation
    ] = Field(default_factory=list)

    temporal_facts: list[
        TemporalFactExpectation
    ] = Field(default_factory=list)

    causal_language: CausalLanguagePolicy

    required_missing_information: list[str] = (
        Field(default_factory=list)
    )

    forbidden_claims: list[str] = Field(
        default_factory=list,
    )

    model_config = ConfigDict(
        extra="forbid",
    )


class RCAEvalCase(BaseModel):
    id: str
    title: str

    scenario_type: ScenarioType
    difficulty: Difficulty

    tags: list[str] = Field(
        default_factory=list,
    )

    incident: EvalIncident

    evidence: list[EvalEvidenceItem]

    expectations: CaseExpectations

    notes: str | None = None

    model_config = ConfigDict(
        extra="forbid",
    )

    @model_validator(mode="after")
    def validate_source_references(
        self,
    ) -> "RCAEvalCase":
        source_ids = {
            item.id
            for item in self.evidence
        }

        referenced_ids: set[str] = set()

        for observation in (
            self.expectations.observations
        ):
            referenced_ids.update(
                observation.acceptable_source_ids
            )

        for fact in (
            self.expectations.numeric_facts
        ):
            referenced_ids.add(
                fact.source_id
            )

        for fact in (
            self.expectations.temporal_facts
        ):
            referenced_ids.add(
                fact.left_source_id
            )
            referenced_ids.add(
                fact.right_source_id
            )

        unknown_ids = (
            referenced_ids - source_ids
        )

        if unknown_ids:
            raise ValueError(
                "Expectations reference unknown "
                f"source IDs: {sorted(unknown_ids)}"
            )

        return self


class DatasetManifest(BaseModel):
    dataset_id: str
    dataset_version: str
    schema_version: str

    description: str

    case_files: list[str]

    model_config = ConfigDict(
        extra="forbid",
    )


def load_rca_eval_dataset(
    root: Path,
) -> tuple[
    DatasetManifest,
    list[RCAEvalCase],
]:
    manifest_path = root / "manifest.json"

    manifest = DatasetManifest.model_validate_json(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    cases: list[RCAEvalCase] = []

    for relative_path in manifest.case_files:
        case_path = root / relative_path

        case = RCAEvalCase.model_validate_json(
            case_path.read_text(
                encoding="utf-8"
            )
        )

        cases.append(case)

    case_ids = [
        case.id
        for case in cases
    ]

    if len(case_ids) != len(set(case_ids)):
        raise ValueError(
            "Evaluation case IDs must be unique."
        )

    return manifest, cases