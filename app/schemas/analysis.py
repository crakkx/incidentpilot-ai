from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    source_type: Literal[
        "log",
        "metric",
        "deployment",
        "runbook",
    ]

    source_id: str | int | None

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
    )

    confidence: Literal[
        "low",
        "medium",
        "high",
    ]

    missing_information: list[str] = Field(
        default_factory=list,
        max_length=15,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class IncidentAnalysisResponse(BaseModel):
    analysis_run_id: str
    incident_id: str
    status: str
    model_name: str
    report: RCAReport


# Kept temporarily so the existing POST /analysis endpoint
# and its older tests do not break.
class AnalysisRequest(BaseModel):
    incident_id: str = Field(..., min_length=1)
    question: str | None = None


class AnalysisResponse(BaseModel):
    analysis_run_id: str
    incident_id: str
    status: str
    summary: str | None
