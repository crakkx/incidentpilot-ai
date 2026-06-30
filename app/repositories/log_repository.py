from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import LogEntry


def create_log_entry(
    db: Session,
    service_id: str,
    incident_id: str | None,
    timestamp: datetime,
    level: str,
    message: str,
    source: str | None,
    context: dict[str, Any] | None,
) -> LogEntry:
    log_entry = LogEntry(
        service_id=service_id,
        incident_id=incident_id,
        timestamp=timestamp,
        level=level,
        message=message,
        source=source,
        context=context,
    )

    db.add(log_entry)

    return log_entry
