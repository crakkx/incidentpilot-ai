from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String(36), primary_key=True, default=new_id)

    service_id = Column(String(36), ForeignKey("services.id"), nullable=False)
    service_name = Column(String(120), nullable=False)

    version = Column(String(80), nullable=False)
    environment = Column(String(80), default="production", nullable=False)
    commit_sha = Column(String(120), nullable=True)
    deployed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service", back_populates="deployments")
