from sqlalchemy.orm import Session

from app.models import Metric


def list_metrics(db: Session) -> list[Metric]:
    return (
        db.query(Metric)
        .order_by(Metric.recorded_at.desc())
        .all()
    )
