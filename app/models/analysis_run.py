from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    incident_id = Column(
        String(36),
        ForeignKey("incidents.id"),
        nullable=False,
    )

    status = Column(
        String(50),
        default="pending",
        nullable=False,
    )

    model_name = Column(
        String(120),
        nullable=True,
    )

    # A short summary for easier list/display operations.
    summary = Column(
        Text,
        nullable=True,
    )

    # The validated structured RCAReport.
    report = Column(
        JSON,
        nullable=True,
    )

    # Exact incident/log/metric/deployment/runbook evidence
    # that was sent to the model.
    evidence_snapshot = Column(
        JSON,
        nullable=True,
    )

    # Saved when model generation or validation fails.
    error_message = Column(
        Text,
        nullable=True,
    )

    started_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    incident = relationship(
        "Incident",
        back_populates="analysis_runs",
    )
