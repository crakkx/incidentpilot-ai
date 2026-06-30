from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deployment


def list_deployments(db: Session) -> list[Deployment]:
    statement = select(Deployment).order_by(Deployment.deployed_at.desc())
    return list(db.execute(statement).scalars().all())
