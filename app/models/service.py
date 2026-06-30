from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id


class Service(Base):
    __tablename__ = "services"

    id = Column(String(36), primary_key=True, default=new_id)
    name = Column(String(120), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    owner_team = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incidents = relationship("Incident", back_populates="service")
    logs = relationship("LogEntry", back_populates="service")
    deployments = relationship("Deployment", back_populates="service")
