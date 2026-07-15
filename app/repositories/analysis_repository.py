from sqlalchemy.orm import Session

from app.models import AnalysisRun


def create_analysis_run(
    db: Session,
    incident_id: str,
    model_name: str,
    status: str = "running",
) -> AnalysisRun:
    analysis_run = AnalysisRun(
        incident_id=incident_id,
        model_name=model_name,
        status=status,
    )

    db.add(analysis_run)
    db.flush()

    return analysis_run


def get_analysis_run(
    db: Session,
    analysis_run_id: str,
) -> AnalysisRun | None:
    return db.get(
        AnalysisRun,
        analysis_run_id,
    )
