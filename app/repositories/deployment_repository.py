from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deployment


def list_deployments(
    db: Session,
) -> list[Deployment]:
    statement = (
        select(Deployment)
        .order_by(Deployment.deployed_at.desc())
    )

    return list(
        db.execute(statement)
        .scalars()
        .all()
    )


def list_deployments_in_window(
    db: Session,
    service_name: str,
    start_time: datetime,
    end_time: datetime,
    limit: int = 20,
) -> list[Deployment]:
    statement = (
        select(Deployment)
        .where(
            Deployment.service_name == service_name,
            Deployment.deployed_at >= start_time,
            Deployment.deployed_at <= end_time,
        )
        .order_by(Deployment.deployed_at.desc())
        .limit(limit)
    )

    return list(
        db.execute(statement)
        .scalars()
        .all()
    )
