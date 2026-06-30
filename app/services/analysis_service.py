from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AnalysisRun
from app.repositories.incident_repository import get_incident


def create_placeholder_analysis(
    db: Session,
    incident_id: str,
    question: str | None = None,
) -> AnalysisRun:
    incident = get_incident(db, incident_id)

    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    summary = (
        "LLM analysis is not implemented yet. "
        "This placeholder records that an analysis was requested."
    )

    if question:
        summary = f"{summary} Question: {question}"

    analysis_run = AnalysisRun(
        incident_id=incident_id,
        status="pending",
        model_name="not-configured",
        summary=summary,
    )

    db.add(analysis_run)
    db.commit()
    db.refresh(analysis_run)

    return analysis_run
