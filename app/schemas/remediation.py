"""Structured remediation proposal schema for human approval gate (Phase 5)."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class RemediationAction(BaseModel):
    action: str = Field(description="Description of the proposed remediation action.")
    priority: Literal["immediate", "short_term", "preventive"] = Field(
        default="immediate",
        description="Priority level of this remediation action.",
    )
    target_entity: str | None = Field(
        default=None,
        description="Target service, deployment, or infrastructure entity name.",
    )
    rationale: str = Field(
        default="",
        description="Explanation for why this action remediates the root cause.",
    )


class RemediationProposal(BaseModel):
    incident_id: str
    root_cause_summary: str
    actions: list[RemediationAction]
    confidence_level: Literal["low", "medium", "high"] = "low"
    status: Literal["pending_approval", "approved", "rejected"] = "pending_approval"
    proposed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    rejection_reason: str | None = None
