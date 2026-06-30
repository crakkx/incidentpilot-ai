from sqlalchemy.orm import Session

from app.models import Deployment


def list_deployments(db: Session) -> list[Deployment]:
    return (
        db.query(Deployment)
        .order_by(Deployment.deployed_at.desc())
        .all()
    )
