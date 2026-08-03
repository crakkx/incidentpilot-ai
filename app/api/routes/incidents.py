from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm.client import RCAClient, get_rca_client
from app.schemas.analysis import IncidentAnalysisResponse
from app.schemas.incident import IncidentCreate, IncidentRead
from app.services.analysis_service import (
    enqueue_analysis_incident,
)
from app.models import AnalysisRun
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
    status_code=202,
)
def analyze_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    llm_client: RCAClient = Depends(get_rca_client),
):
    analysis_run = enqueue_analysis_incident(
        db=db,
        incident_id=incident_id,
        llm_client=llm_client,
    )

    return {
        "analysis_run_id": analysis_run.id,
        "incident_id": incident_id,
        "status": analysis_run.status,
        "model_name": analysis_run.model_name,
        "pipeline_version": analysis_run.pipeline_version,
        "schema_version": analysis_run.schema_version,
        "prompt_version": analysis_run.prompt_version,
        "progress_stage": analysis_run.progress_stage,
        "progress_message": analysis_run.progress_message,
        "progress_percent": analysis_run.progress_percent,
        "failure_type": analysis_run.failure_type,
        "error_message": analysis_run.error_message,
        "report": analysis_run.report,
    }


from sqlalchemy import select
from fastapi import HTTPException

@router.get(
    "/{incident_id}/analyze",
    response_model=IncidentAnalysisResponse,
)
def get_latest_analysis(
    incident_id: str,
    db: Session = Depends(get_db),
):
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.incident_id == incident_id)
        .order_by(AnalysisRun.started_at.desc())
    )
    analysis_run = db.execute(stmt).scalars().first()
    
    if not analysis_run:
        raise HTTPException(status_code=404, detail="No analysis runs found for this incident")

    return {
        "analysis_run_id": analysis_run.id,
        "incident_id": analysis_run.incident_id,
        "status": analysis_run.status,
        "model_name": analysis_run.model_name,
        "pipeline_version": analysis_run.pipeline_version,
        "schema_version": analysis_run.schema_version,
        "prompt_version": analysis_run.prompt_version,
        "progress_stage": analysis_run.progress_stage,
        "progress_message": analysis_run.progress_message,
        "progress_percent": analysis_run.progress_percent,
        "failure_type": analysis_run.failure_type,
        "error_message": analysis_run.error_message,
        "report": analysis_run.report,
    }


from fastapi import HTTPException

@router.get(
    "/{incident_id}/analyze/{run_id}",
    response_model=IncidentAnalysisResponse,
)
def get_analysis_status(
    incident_id: str,
    run_id: str,
    db: Session = Depends(get_db),
):
    analysis_run = db.get(AnalysisRun, run_id)
    if not analysis_run or analysis_run.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    return {
        "analysis_run_id": analysis_run.id,
        "incident_id": analysis_run.incident_id,
        "status": analysis_run.status,
        "model_name": analysis_run.model_name,
        "pipeline_version": analysis_run.pipeline_version,
        "schema_version": analysis_run.schema_version,
        "prompt_version": analysis_run.prompt_version,
        "progress_stage": analysis_run.progress_stage,
        "progress_message": analysis_run.progress_message,
        "progress_percent": analysis_run.progress_percent,
        "failure_type": analysis_run.failure_type,
        "error_message": analysis_run.error_message,
        "report": analysis_run.report,
    }


from app.worker.celery_app import celery_app

@router.post(
    "/{incident_id}/analyze/{run_id}/cancel",
)
def cancel_analysis(
    incident_id: str,
    run_id: str,
    db: Session = Depends(get_db),
):
    analysis_run = db.get(AnalysisRun, run_id)
    if not analysis_run or analysis_run.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    if analysis_run.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel run in state: {analysis_run.status}")

    # Revoke Celery task. If it's already executing, terminate=True kills the worker process.
    celery_app.control.revoke(run_id, terminate=True)

    analysis_run.status = "cancelled"
    analysis_run.progress_stage = "cancelled"
    analysis_run.progress_message = "Analysis was cancelled by the user."
    db.commit()

    return {"message": "Analysis cancelled successfully"}


from pydantic import BaseModel

class RejectRemediationRequest(BaseModel):
    reason: str | None = None


@router.get(
    "/{incident_id}/remediation",
)
def get_remediation_proposal(
    incident_id: str,
    db: Session = Depends(get_db),
):
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.incident_id == incident_id)
        .order_by(AnalysisRun.started_at.desc())
    )
    analysis_run = db.execute(stmt).scalars().first()
    if not analysis_run or not analysis_run.remediation_proposal:
        raise HTTPException(status_code=404, detail="No remediation proposal found for this incident")

    return analysis_run.remediation_proposal


@router.post(
    "/{incident_id}/remediation/approve",
)
def approve_remediation(
    incident_id: str,
    db: Session = Depends(get_db),
):
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.incident_id == incident_id)
        .order_by(AnalysisRun.started_at.desc())
    )
    analysis_run = db.execute(stmt).scalars().first()
    if not analysis_run or not analysis_run.remediation_proposal:
        raise HTTPException(status_code=404, detail="No remediation proposal found for this incident")

    proposal = dict(analysis_run.remediation_proposal)
    proposal["status"] = "approved"
    analysis_run.remediation_proposal = proposal
    if analysis_run.status == "awaiting_approval":
        analysis_run.status = "completed"
        analysis_run.progress_stage = "completed"
        analysis_run.progress_message = "Remediation proposal approved by human operator."
        analysis_run.progress_percent = 100

    db.commit()
    return {"message": "Remediation proposal approved", "proposal": proposal}


@router.post(
    "/{incident_id}/remediation/reject",
)
def reject_remediation(
    incident_id: str,
    payload: RejectRemediationRequest | None = None,
    db: Session = Depends(get_db),
):
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.incident_id == incident_id)
        .order_by(AnalysisRun.started_at.desc())
    )
    analysis_run = db.execute(stmt).scalars().first()
    if not analysis_run or not analysis_run.remediation_proposal:
        raise HTTPException(status_code=404, detail="No remediation proposal found for this incident")

    proposal = dict(analysis_run.remediation_proposal)
    proposal["status"] = "rejected"
    if payload and payload.reason:
        proposal["rejection_reason"] = payload.reason

    analysis_run.remediation_proposal = proposal
    if analysis_run.status == "awaiting_approval":
        analysis_run.status = "rejected"
        analysis_run.progress_stage = "rejected"
        analysis_run.progress_message = f"Remediation proposal rejected by human operator. Reason: {proposal.get('rejection_reason', 'None')}"

    db.commit()
    return {"message": "Remediation proposal rejected", "proposal": proposal}

