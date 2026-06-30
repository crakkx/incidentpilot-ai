from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String

from app.db.base import Base
from app.models.base import new_id


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(String(36), primary_key=True, default=new_id)

    service_name = Column(String(120), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    metric_name = Column(String(120), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(40), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
