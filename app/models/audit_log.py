from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String

from app.db.base import Base
from app.models.base import new_id


class AuditLog(Base):
    """Append-only record of security-relevant actions: who did what, to
    which resource, when. Covers remediation approve/reject and analysis
    retries — the actions a real incident-response audit would ask about."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=new_id)

    actor_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    actor_label = Column(
        String(255),
        nullable=True,
        doc="Fallback identifier when the action wasn't triggered by a User row (e.g. 'celery-worker').",
    )

    action = Column(String(80), nullable=False)
    resource_type = Column(String(80), nullable=False)
    resource_id = Column(String(36), nullable=False)

    audit_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
