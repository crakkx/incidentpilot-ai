from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.analysis_service import create_placeholder_analysis


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("", response_model=AnalysisResponse, status_code=201)
def create_analysis(
    payload: AnalysisRequest,
    db: Session = Depends(get_db),
):
    analysis_run = create_placeholder_analysis(
        db=db,
        incident_id=payload.incident_id,
        question=payload.question,
    )

    return {
        "analysis_run_id": analysis_run.id,
        "incident_id": analysis_run.incident_id,
        "status": analysis_run.status,
        "summary": analysis_run.summary,
    }
