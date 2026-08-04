from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.llm.client import RCAClient, get_rca_client
from app.models import User
from app.repositories.audit_repository import record_audit_event
from app.repositories.incident_repository import get_incident
from app.schemas.analysis import IncidentAnalysisResponse
from app.schemas.incident import IncidentCreate, IncidentRead
from app.schemas.trace import AnalysisTraceResponse
from app.services.analysis_service import (
    enqueue_analysis_incident,
)
from app.services.evidence_service import collect_incident_evidence_with_diagnostics
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
@limiter.limit(settings.analysis_rate_limit)
def create_incident(
    request: Request,
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("operator", "admin")),
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
    _user: User = Depends(get_current_user),
):
    return service_list_incidents(
        db=db,
        status=status,
    )


class IncidentStatusUpdate(BaseModel):
    status: str


@router.patch(
    "/{incident_id}/status",
    response_model=IncidentRead,
)
def update_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("operator", "admin")),
):
    from app.repositories.incident_repository import update_incident_status
    updated = update_incident_status(db=db, incident_id=incident_id, status=payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Incident not found")
    return updated


@router.get(
    "/approvals/list",
)
def list_remediation_approvals(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("operator", "admin")),
):
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.remediation_proposal.is_not(None))
        .order_by(AnalysisRun.started_at.desc())
    )
    runs = db.execute(stmt).scalars().all()
    results = []
    for r in runs:
        prop = r.remediation_proposal or {}
        prop_status = prop.get("status", r.status)
        if status_filter and prop_status != status_filter:
            continue
        inc = r.incident
        results.append({
            "analysis_run_id": r.id,
            "incident_id": r.incident_id,
            "incident_title": inc.title if inc else "Unknown Incident",
            "service_name": inc.service_name if inc else None,
            "run_status": r.status,
            "proposal": prop,
            "created_at": r.started_at.isoformat() if r.started_at else None,
        })
    return results



@router.get("/{incident_id}/evidence")
def get_incident_evidence(
    incident_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Raw evidence (logs/metrics/deployments/runbook chunks) for the
    'Evidence timeline' screen — the same collection window the RCA
    pipeline itself sees, reused directly rather than re-querying."""
    incident = get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    evidence_payload, _diagnostics = collect_incident_evidence_with_diagnostics(
        db=db, incident=incident
    )
    return evidence_payload


@router.post(
    "/{incident_id}/analyze",
    response_model=IncidentAnalysisResponse,
    status_code=202,
)
@limiter.limit(settings.analysis_rate_limit)
def analyze_incident(
    request: Request,
    incident_id: str,
    db: Session = Depends(get_db),
    llm_client: RCAClient = Depends(get_rca_client),
    _user: User = Depends(require_role("operator", "admin")),
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
    _user: User = Depends(get_current_user),
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
    _user: User = Depends(get_current_user),
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


@router.get(
    "/{incident_id}/trace",
    response_model=AnalysisTraceResponse,
)
def get_analysis_trace(
    incident_id: str,
    run_id: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if run_id:
        analysis_run = db.get(AnalysisRun, run_id)
        if not analysis_run or analysis_run.incident_id != incident_id:
            raise HTTPException(status_code=404, detail="Analysis run not found")
    else:
        stmt = (
            select(AnalysisRun)
            .where(AnalysisRun.incident_id == incident_id)
            .order_by(AnalysisRun.started_at.desc())
        )
        analysis_run = db.execute(stmt).scalars().first()
        if not analysis_run:
            raise HTTPException(status_code=404, detail="No analysis runs found for this incident")

    metadata = analysis_run.generation_metadata or {}

    return AnalysisTraceResponse(
        analysis_run_id=analysis_run.id,
        incident_id=analysis_run.incident_id,
        status=analysis_run.status,
        progress_stage=analysis_run.progress_stage,
        progress_message=analysis_run.progress_message,
        progress_percent=analysis_run.progress_percent,
        node_calls=metadata.get("node_calls"),
        repairs_used=metadata.get("repairs_used"),
        investigation_rounds=metadata.get("investigation_rounds"),
        tool_results=metadata.get("tool_results"),
        validation=metadata.get("validation"),
        generation_metadata=metadata,
        generation_attempts=analysis_run.generation_attempts,
        validation_errors=analysis_run.validation_errors,
        retrieval_diagnostics=analysis_run.retrieval_diagnostics,
    )


from app.worker.celery_app import celery_app

@router.post(
    "/{incident_id}/analyze/{run_id}/cancel",
)
def cancel_analysis(
    incident_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("operator", "admin")),
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


from pydantic import BaseModel, Field

class RejectRemediationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2_000)


@router.get(
    "/{incident_id}/remediation",
)
def get_remediation_proposal(
    incident_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
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
    user: User = Depends(require_role("operator", "admin")),
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

    record_audit_event(
        db,
        actor=user,
        action="remediation.approve",
        resource_type="analysis_run",
        resource_id=analysis_run.id,
        metadata={"incident_id": incident_id},
    )

    db.commit()
    return {"message": "Remediation proposal approved", "proposal": proposal}


@router.post(
    "/{incident_id}/remediation/reject",
)
def reject_remediation(
    incident_id: str,
    payload: RejectRemediationRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator", "admin")),
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

    record_audit_event(
        db,
        actor=user,
        action="remediation.reject",
        resource_type="analysis_run",
        resource_id=analysis_run.id,
        metadata={"incident_id": incident_id, "reason": payload.reason if payload else None},
    )

    db.commit()
    return {"message": "Remediation proposal rejected", "proposal": proposal}

