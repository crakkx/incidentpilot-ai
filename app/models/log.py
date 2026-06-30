from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id


class LogEntry(Base):
    __tablename__ = "logs"

    id = Column(String(36), primary_key=True, default=new_id)

    service_id = Column(String(36), ForeignKey("services.id"), nullable=False)
    service_name = Column(String(120), nullable=False)

    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    level = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    source = Column(String(120), nullable=True)
    context = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service", back_populates="logs")
    incident = relationship("Incident", back_populates="logs")
