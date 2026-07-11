from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.base import new_id


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=new_id)

    title = Column(String(200), nullable=False)
    filename = Column(String(255), nullable=True)
    content_type = Column(String(120), nullable=True)
    content = Column(Text, nullable=False)

    service_name = Column(String(120), nullable=True)
    document_type = Column(String(80), default="runbook", nullable=False)
    severity = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
