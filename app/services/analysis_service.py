from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import (
    InvalidRCAOutputError,
    OllamaRequestError,
    RCAClient,
)
from app.models import AnalysisRun
from app.repositories.analysis_repository import (
    create_analysis_run,
)
from app.repositories.incident_repository import (
    get_incident,
)
from app.schemas.analysis import RCAReport
from app.services.evidence_service import (
    collect_incident_evidence,
    validate_report_evidence,
)

from app.services.analysis_metadata import (
    build_analysis_run_metadata,
)


def _mark_analysis_failed(
    db: Session,
    analysis_run_id: str,
    error: Exception,
) -> None:
    db.rollback()

    analysis_run = db.get(
        AnalysisRun,
        analysis_run_id,
    )

    if analysis_run is None:
        return

    analysis_run.status = "failed"
    analysis_run.error_message = str(error)[:4000]
    analysis_run.completed_at = datetime.utcnow()

    db.commit()


def analyze_incident(
    db: Session,
    incident_id: str,
    llm_client: RCAClient,
) -> tuple[AnalysisRun, RCAReport]:
    incident = get_incident(
        db=db,
        incident_id=incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="incident not found",
        )

    run_metadata = build_analysis_run_metadata()
    analysis_run = create_analysis_run(
        db=db,
        incident_id=incident.id,
        model_name=settings.ollama_model,
        status="running",
        pipeline_version=(
            run_metadata["pipeline_version"]
        ),
        schema_version=(
            run_metadata["schema_version"]
        ),
        prompt_version=(
            run_metadata["prompt_version"]
        ),
        run_config=run_metadata["run_config"],
    )

    db.commit()
    db.refresh(analysis_run)

    analysis_run_id = analysis_run.id

    try:
        evidence_payload = collect_incident_evidence(
            db=db,
            incident=incident,
        )

        report = llm_client.generate_rca(
            evidence_payload=evidence_payload,
        )

        validate_report_evidence(
            report=report,
            evidence_payload=evidence_payload,
        )

        analysis_run = db.get(
            AnalysisRun,
            analysis_run_id,
        )

        if analysis_run is None:
            raise RuntimeError(
                "Analysis run disappeared during execution."
            )

        analysis_run.status = "completed"
        analysis_run.summary = report.incident_summary

        analysis_run.report = report.model_dump(
            mode="json"
        )

        analysis_run.evidence_snapshot = (
            evidence_payload
        )

        analysis_run.error_message = None
        analysis_run.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(analysis_run)

        return analysis_run, report

    except OllamaRequestError as exc:
        _mark_analysis_failed(
            db=db,
            analysis_run_id=analysis_run_id,
            error=exc,
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "The local Ollama service could not generate "
                "the RCA report."
            ),
        ) from exc

    except InvalidRCAOutputError as exc:
        _mark_analysis_failed(
            db=db,
            analysis_run_id=analysis_run_id,
            error=exc,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "The LLM returned an invalid structured "
                "RCA report."
            ),
        ) from exc

    except ValueError as exc:
        _mark_analysis_failed(
            db=db,
            analysis_run_id=analysis_run_id,
            error=exc,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "The LLM cited evidence that was not supplied "
                "by the application."
            ),
        ) from exc

    except Exception as exc:
        _mark_analysis_failed(
            db=db,
            analysis_run_id=analysis_run_id,
            error=exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Incident analysis failed.",
        ) from exc


