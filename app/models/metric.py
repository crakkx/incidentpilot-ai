from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(String(36), primary_key=True, default=new_id)

    service_id = Column(String(36), ForeignKey("services.id"), nullable=False)

    name = Column(String(120), index=True, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(40), nullable=True)
    context = Column(JSON, nullable=True)

    recorded_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service", back_populates="metrics")
