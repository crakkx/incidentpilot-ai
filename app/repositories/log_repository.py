from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LogEntry


def create_log_entry(
    db: Session,
    service_id: str,
    service_name: str,
    incident_id: str | None,
    timestamp: datetime,
    level: str,
    message: str,
    source: str | None,
    context: dict[str, Any] | None,
) -> LogEntry:
    log_entry = LogEntry(
        service_id=service_id,
        service_name=service_name,
        incident_id=incident_id,
        timestamp=timestamp,
        level=level,
        message=message,
        source=source,
        context=context,
    )

    db.add(log_entry)

    return log_entry


def list_logs_in_window(
    db: Session,
    service_name: str,
    start_time: datetime,
    end_time: datetime,
    limit: int = 50,
) -> list[LogEntry]:
    statement = (
        select(LogEntry)
        .where(
            LogEntry.service_name == service_name,
            LogEntry.timestamp >= start_time,
            LogEntry.timestamp <= end_time,
        )
        .order_by(LogEntry.timestamp.asc())
        .limit(limit)
    )

    return list(
        db.execute(statement)
        .scalars()
        .all()
    )
