from app.worker.celery_app import celery_app
from app.services.analysis_service import run_analysis_job
from app.db.session import SessionLocal
from app.models import AnalysisRun
from app.core.redaction import redact_string
from app.repositories.audit_repository import record_audit_event
from celery.exceptions import SoftTimeLimitExceeded
import logging

logger = logging.getLogger(__name__)


def _audit_worker_event(analysis_run_id: str, action: str, metadata: dict) -> None:
    db = SessionLocal()
    try:
        record_audit_event(
            db,
            actor_label="celery-worker",
            action=action,
            resource_type="analysis_run",
            resource_id=analysis_run_id,
            metadata=metadata,
        )
        db.commit()
    finally:
        db.close()


@celery_app.task(
    name="run_analysis_task",
    bind=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=330,
)
def run_analysis_task(self, analysis_run_id: str):
    try:
        run_analysis_job(analysis_run_id=analysis_run_id)
    except SoftTimeLimitExceeded as exc:
        logger.error(f"Task timed out for run {analysis_run_id}: {exc}")
        db = SessionLocal()
        try:
            run = db.get(AnalysisRun, analysis_run_id)
            if run:
                run.status = "failed"
                run.error_message = "Analysis timed out after 5 minutes."
                run.progress_stage = "failed"
                db.commit()
        finally:
            db.close()
        _audit_worker_event(
            analysis_run_id, "analysis.timeout", {"error": "soft time limit exceeded"}
        )
        raise exc
    except Exception as exc:
        logger.error(f"Error in run_analysis_task for run {analysis_run_id}: {exc}")
        _audit_worker_event(
            analysis_run_id,
            "analysis.retry",
            {"retry_count": self.request.retries + 1, "error": redact_string(str(exc)[:500])},
        )
        # Retry with exponential backoff (e.g. 60s, 120s, 240s)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
