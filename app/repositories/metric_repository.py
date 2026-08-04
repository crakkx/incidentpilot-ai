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


def create_metrics_bulk(
    db: Session,
    service_name: str,
    metrics_data: list[dict],
) -> list[Metric]:
    created = []
    for item in metrics_data:
        ts = item.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts is None:
            ts = datetime.utcnow()

        metric = Metric(
            service_name=service_name,
            timestamp=ts,
            metric_name=item["metric_name"],
            value=float(item["value"]),
            unit=item.get("unit"),
        )
        db.add(metric)
        created.append(metric)

    db.commit()
    return created

