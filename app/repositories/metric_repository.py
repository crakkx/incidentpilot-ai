from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Metric


def list_metrics(db: Session) -> list[Metric]:
    statement = select(Metric).order_by(Metric.timestamp.desc())
    return list(db.execute(statement).scalars().all())
