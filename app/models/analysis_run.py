from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(String(36), primary_key=True, default=new_id)

    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False)

    status = Column(String(50), default="pending", nullable=False)
    model_name = Column(String(120), nullable=True)
    summary = Column(Text, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    incident = relationship("Incident", back_populates="analysis_runs")
