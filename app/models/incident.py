from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=new_id)

    title = Column(String(200), nullable=False)
    severity = Column(String(50), default="medium", nullable=False)
    status = Column(String(50), default="open", index=True, nullable=False)
    description = Column(Text, nullable=True)

    service_id = Column(String(36), ForeignKey("services.id"), nullable=True)
    service_name = Column(String(120), nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    service = relationship("Service", back_populates="incidents")
    logs = relationship("LogEntry", back_populates="incident")
    analysis_runs = relationship("AnalysisRun", back_populates="incident")
