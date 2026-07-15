from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Metric


def list_metrics(
    db: Session,
) -> list[Metric]:
    statement = (
        select(Metric)
        .order_by(Metric.timestamp.desc())
    )

    return list(
        db.execute(statement)
        .scalars()
        .all()
    )


def list_metrics_in_window(
    db: Session,
    service_name: str,
    start_time: datetime,
    end_time: datetime,
    limit: int = 50,
) -> list[Metric]:
    statement = (
        select(Metric)
        .where(
            Metric.service_name == service_name,
            Metric.timestamp >= start_time,
            Metric.timestamp <= end_time,
        )
        .order_by(Metric.timestamp.asc())
        .limit(limit)
    )

    return list(
        db.execute(statement)
        .scalars()
        .all()
    )
