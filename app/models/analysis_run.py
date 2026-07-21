from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id

from app.core.versions import (
    PIPELINE_VERSION,
    RCA_PROMPT_VERSION,
    RCA_SCHEMA_VERSION,
)

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
        nullable=False,
        default="pending",
    )

    model_name = Column(
        String(120),
        nullable=True,
    )

    pipeline_version = Column(
        String(50),
        default=PIPELINE_VERSION,
        nullable=False,
    )

    schema_version = Column(
        String(80),
        default=RCA_SCHEMA_VERSION,
        nullable=False,
    )

    prompt_version = Column(
        String(80),
        default=RCA_PROMPT_VERSION,
        nullable=False,
    )

    run_config = Column(
        JSON,
        nullable=True,
    )

    summary = Column(Text, nullable=True)
    report = Column(JSON, nullable=True)
    evidence_snapshot = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

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