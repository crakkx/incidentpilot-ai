from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.incident_repository import (
    create_incident as repo_create_incident,
)
from app.repositories.incident_repository import (
    create_service,
    get_service_by_name,
    list_incidents as repo_list_incidents,
)
from app.schemas.incident import IncidentCreate


def get_or_create_service(db: Session, name: str):
    normalized_name = name.strip().lower()

    if not normalized_name:
        raise HTTPException(status_code=400, detail="service_name cannot be empty")

    service = get_service_by_name(db, normalized_name)

    if service:
        return service

    return create_service(
        db=db,
        name=normalized_name,
        description=f"{normalized_name} service",
    )


def create_incident(db: Session, payload: IncidentCreate):
    service = None

    if payload.service_name:
        service = get_or_create_service(db, payload.service_name)

    incident = repo_create_incident(
        db=db,
        title=payload.title,
        severity=payload.severity,
        status=payload.status,
        description=payload.description,
        service_id=service.id if service else None,
    )

    db.commit()
    db.refresh(incident)

    return incident


def list_incidents(db: Session, status: str | None = None):
    return repo_list_incidents(db=db, status=status)
