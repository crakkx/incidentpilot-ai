from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm.client import RCAClient, get_rca_client
from app.schemas.analysis import IncidentAnalysisResponse
from app.schemas.incident import IncidentCreate, IncidentRead
from app.services.analysis_service import (
    analyze_incident as service_analyze_incident,
)
from app.services.incident_service import (
    create_incident as service_create_incident,
)
from app.services.incident_service import (
    list_incidents as service_list_incidents,
)


router = APIRouter(
    prefix="/incidents",
    tags=["incidents"],
)


@router.post(
    "",
    response_model=IncidentRead,
    status_code=201,
)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
):
    return service_create_incident(
        db=db,
        payload=payload,
    )


@router.get(
    "",
    response_model=list[IncidentRead],
)
def list_incidents(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return service_list_incidents(
        db=db,
        status=status,
    )


@router.post(
    "/{incident_id}/analyze",
    response_model=IncidentAnalysisResponse,
    status_code=201,
)
def analyze_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    llm_client: RCAClient = Depends(get_rca_client),
):
    analysis_run, report = service_analyze_incident(
        db=db,
        incident_id=incident_id,
        llm_client=llm_client,
    )

    return {
        "analysis_run_id": analysis_run.id,
        "incident_id": incident_id,
        "status": analysis_run.status,
        "model_name": analysis_run.model_name,
        "report": report,
    }
