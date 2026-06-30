from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.incident import IncidentCreate, IncidentRead
from app.services.incident_service import (
    create_incident as service_create_incident,
)
from app.services.incident_service import (
    list_incidents as service_list_incidents,
)


router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", response_model=IncidentRead, status_code=201)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
):
    return service_create_incident(db=db, payload=payload)


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return service_list_incidents(db=db, status=status)
