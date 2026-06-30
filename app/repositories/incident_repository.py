from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Incident, Service


def get_service_by_name(db: Session, name: str) -> Service | None:
    statement = select(Service).where(Service.name == name)
    return db.execute(statement).scalar_one_or_none()


def create_service(db: Session, name: str, description: str | None = None) -> Service:
    service = Service(
        name=name,
        description=description,
    )

    db.add(service)
    db.flush()

    return service


def create_incident(
    db: Session,
    title: str,
    severity: str,
    status: str,
    description: str | None,
    service_id: str | None,
    service_name: str | None,
) -> Incident:
    incident = Incident(
        title=title,
        severity=severity,
        status=status,
        description=description,
        service_id=service_id,
        service_name=service_name,
    )

    db.add(incident)
    db.flush()

    return incident


def list_incidents(db: Session, status: str | None = None) -> list[Incident]:
    statement = select(Incident).order_by(Incident.created_at.desc())

    if status:
        statement = statement.where(Incident.status == status)

    return list(db.execute(statement).scalars().all())


def get_incident(db: Session, incident_id: str) -> Incident | None:
    return db.get(Incident, incident_id)
