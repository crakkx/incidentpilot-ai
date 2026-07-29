from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.llm.client import (
    InvalidRCAOutputError,
    RCAClient,
    RCARequestError,
    default_model_for_provider,
    normalize_llm_provider,
)
from app.models import AnalysisRun
from app.repositories.analysis_repository import (
    create_analysis_run,
)
from app.repositories.incident_repository import (
    get_incident,
)
from app.schemas.analysis import RCAReport

from app.db.session import SessionLocal
from app.llm.client import get_rca_client
from app.services.evidence_service import (
    EvidenceValidationError,
    collect_incident_evidence_with_diagnostics,
    validate_report_evidence,
)

from app.services.analysis_metadata import (
    build_analysis_run_metadata,
)

def _set_progress(
    db: Session,
    analysis_run: AnalysisRun,
    *,
    stage: str,
    message: str,
    percent: int,
    status: str = "running",
) -> None:
    analysis_run.status = status
    analysis_run.progress_stage = stage
    analysis_run.progress_message = message
    analysis_run.progress_percent = percent

    db.commit()
    db.refresh(analysis_run)


def _save_generation_debug(
    analysis_run: AnalysisRun,
    debug: dict | None,
) -> None:
    debug = debug or {}

    attempts = debug.get(
        "attempts"
    ) or []

    raw_output = debug.get(
        "final_raw_output"
    )

    metadata = debug.get(
        "final_metadata"
    ) or {}

    validation_errors = debug.get(
        "final_validation_errors"
    ) or []

    if raw_output is None and attempts:
        raw_output = attempts[-1].get(
            "raw_output"
        )

    if not metadata and attempts:
        metadata = (
            attempts[-1].get(
                "metadata"
            )
            or {}
        )

    if (
        not validation_errors
        and attempts
    ):
        validation_errors = (
            attempts[-1].get(
                "validation_errors"
            )
            or []
        )

    analysis_run.generation_attempts = (
        attempts
    )

    analysis_run.raw_model_output = (
        raw_output
    )

    analysis_run.generation_metadata = (
        metadata
    )

    analysis_run.validation_errors = (
        validation_errors
    )


def prepare_analysis_run(
    db: Session,
    incident_id: str,
    provider: str | None = None,
    model_name: str | None = None,
    pipeline: str | None = None,
) -> AnalysisRun:
    incident = get_incident(
        db=db,
        incident_id=incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="incident not found",
        )

    selected_provider = normalize_llm_provider(
        provider
    )

    selected_model = (
        model_name
        or default_model_for_provider(
            selected_provider
        )
    )

    run_metadata = (
        build_analysis_run_metadata(
            provider=selected_provider,
            model_name=selected_model,
            pipeline=pipeline,
        )
    )

    analysis_run = create_analysis_run(
        db=db,
        incident_id=incident.id,
        model_name=selected_model,
        status="queued",
        pipeline_version=(
            run_metadata[
                "pipeline_version"
            ]
        ),
        schema_version=(
            run_metadata[
                "schema_version"
            ]
        ),
        prompt_version=(
            run_metadata[
                "prompt_version"
            ]
        ),
        run_config=(
            run_metadata["run_config"]
        ),
    )

    analysis_run.progress_stage = "queued"
    analysis_run.progress_message = (
        "Analysis has been queued."
    )
    analysis_run.progress_percent = 0

    db.commit()
    db.refresh(analysis_run)

    return analysis_run


def execute_analysis_run(
    db: Session,
    analysis_run_id: str,
    llm_client: RCAClient,
    *,
    raise_http_errors: bool,
) -> tuple[
    AnalysisRun,
    RCAReport | None,
]:
    analysis_run = db.get(
        AnalysisRun,
        analysis_run_id,
    )

    if analysis_run is None:
        raise RuntimeError(
            "Analysis run not found."
        )

    incident = get_incident(
        db=db,
        incident_id=(
            analysis_run.incident_id
        ),
    )

    if incident is None:
        raise RuntimeError(
            "Incident for analysis run "
            "was not found."
        )

    def progress(
        stage: str,
        message: str,
        percent: int,
    ) -> None:
        _set_progress(
            db,
            analysis_run,
            stage=stage,
            message=message,
            percent=percent,
        )

    try:
        progress(
            "loading_incident",
            "Loading incident details.",
            5,
        )

        (
            evidence_payload,
            retrieval_diagnostics,
        ) = (
            collect_incident_evidence_with_diagnostics(
                db=db,
                incident=incident,
                progress=progress,
            )
        )

        analysis_run.evidence_snapshot = (
            evidence_payload
        )

        analysis_run.retrieval_diagnostics = (
            retrieval_diagnostics
        )

        db.commit()
        db.refresh(analysis_run)

        progress(
            "building_prompt",
            "Building grounded RCA prompt.",
            55,
        )

        progress(
            "generating_rca",
            (
                "Generating RCA with "
                f"{analysis_run.model_name}."
            ),
            65,
        )

        generation_result = (
            llm_client
            .generate_rca_with_debug(
                evidence_payload
            )
        )

        analysis_run.raw_model_output = (
            generation_result.raw_output
        )

        analysis_run.generation_metadata = (
            generation_result.metadata
        )

        analysis_run.generation_attempts = (
            generation_result.attempts
        )

        analysis_run.validation_errors = []
        db.commit()

        progress(
            "validating_schema",
            "Structured RCA schema is valid.",
            80,
        )

        progress(
            "validating_evidence",
            "Checking every cited evidence ID.",
            90,
        )

        validate_report_evidence(
            report=generation_result.report,
            evidence_payload=evidence_payload,
        )

        progress(
            "persisting_result",
            "Saving validated RCA report.",
            95,
        )

        report = generation_result.report

        analysis_run.status = "completed"
        analysis_run.progress_stage = (
            "completed"
        )
        analysis_run.progress_message = (
            "Analysis completed successfully."
        )
        analysis_run.progress_percent = 100

        analysis_run.summary = (
            report.incident_summary
        )

        analysis_run.report = (
            report.model_dump(
                mode="json"
            )
        )

        analysis_run.error_message = None
        analysis_run.failure_type = None
        analysis_run.completed_at = (
            datetime.utcnow()
        )

        db.commit()
        db.refresh(analysis_run)

        return analysis_run, report

    except InvalidRCAOutputError as exc:
        _save_generation_debug(
            analysis_run,
            getattr(
                exc,
                "debug",
                {},
            )
            or {},
        )

        analysis_run.failure_type = (
            "schema_validation"
        )

        analysis_run.error_message = str(exc)
        analysis_run.status = "failed"
        analysis_run.progress_stage = "failed"
        analysis_run.progress_message = (
            "The model output failed "
            "Pydantic schema validation."
        )
        analysis_run.completed_at = (
            datetime.utcnow()
        )

        db.commit()
        db.refresh(analysis_run)

        if raise_http_errors:
            raise HTTPException(
                status_code=502,
                detail=(
                    "The LLM returned an invalid "
                    "structured RCA report."
                ),
            ) from exc

        return analysis_run, None

    except EvidenceValidationError as exc:
        analysis_run.failure_type = (
            "invented_evidence"
        )

        analysis_run.validation_errors = (
            exc.issues
        )

        analysis_run.error_message = str(exc)
        analysis_run.status = "failed"
        analysis_run.progress_stage = "failed"
        analysis_run.progress_message = (
            "The model cited evidence that "
            "was not supplied."
        )
        analysis_run.completed_at = (
            datetime.utcnow()
        )

        db.commit()
        db.refresh(analysis_run)

        if raise_http_errors:
            raise HTTPException(
                status_code=502,
                detail=(
                    "The LLM cited evidence that "
                    "was not supplied by the "
                    "application."
                ),
            ) from exc

        return analysis_run, None

    except RCARequestError as exc:
        analysis_run.failure_type = (
            f"{exc.provider}_request"
        )

        analysis_run.error_message = str(exc)
        analysis_run.status = "failed"
        analysis_run.progress_stage = "failed"
        analysis_run.progress_message = (
            f"{exc.provider.title()} could not generate "
            "the RCA."
        )
        analysis_run.completed_at = (
            datetime.utcnow()
        )

        db.commit()
        db.refresh(analysis_run)

        if raise_http_errors:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"The {exc.provider} service "
                    "could not generate the RCA."
                ),
            ) from exc

        return analysis_run, None

    except Exception as exc:
        db.rollback()

        analysis_run = db.get(
            AnalysisRun,
            analysis_run_id,
        )

        if analysis_run is not None:
            analysis_run.failure_type = (
                "internal_error"
            )
            analysis_run.error_message = (
                str(exc)[:8000]
            )
            analysis_run.status = "failed"
            analysis_run.progress_stage = (
                "failed"
            )
            analysis_run.progress_message = (
                "Unexpected analysis failure."
            )
            analysis_run.completed_at = (
                datetime.utcnow()
            )

            db.commit()
            db.refresh(analysis_run)

        if raise_http_errors:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Incident analysis failed."
                ),
            ) from exc

        return analysis_run, None


def run_analysis_job(
    analysis_run_id: str,
) -> None:
    db = SessionLocal()

    try:
        analysis_run = db.get(
            AnalysisRun,
            analysis_run_id,
        )

        if analysis_run is None:
            return

        llm_client = get_rca_client(
            provider=(
                (analysis_run.run_config or {})
                .get("llm", {})
                .get("runtime", "mistral")
            ),
            model_name=(
                analysis_run.model_name
            ),
            pipeline=(
                (analysis_run.run_config or {})
                .get("llm", {})
                .get("pipeline_mode")
            ),
        )

        execute_analysis_run(
            db=db,
            analysis_run_id=analysis_run_id,
            llm_client=llm_client,
            raise_http_errors=False,
        )

    finally:
        db.close()


def analyze_incident(
    db: Session,
    incident_id: str,
    llm_client: RCAClient,
) -> tuple[AnalysisRun, RCAReport]:
    analysis_run = prepare_analysis_run(
        db=db,
        incident_id=incident_id,
        provider=(
            llm_client.provider
            or "mistral"
        ),
        model_name=getattr(
            llm_client,
            "model_name",
            None,
        ),
        pipeline=getattr(
            llm_client,
            "pipeline_mode",
            None,
        ),
    )

    completed_run, report = (
        execute_analysis_run(
            db=db,
            analysis_run_id=(
                analysis_run.id
            ),
            llm_client=llm_client,
            raise_http_errors=True,
        )
    )

    if report is None:
        raise RuntimeError(
            "Completed analysis has no report."
        )

    return completed_run, report
