from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    actor: User | None = None,
    actor_label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_label=actor_label or (actor.email if actor else None),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        audit_metadata=metadata,
    )
    db.add(entry)
    db.flush()
    return entry
