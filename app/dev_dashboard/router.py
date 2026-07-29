import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.evals.rca_dataset import (
    load_rca_eval_dataset,
)
from app.evals.rca_eval_runner import run_rca_evals
from app.services.analysis_metadata import (
    build_analysis_run_metadata,
)
import httpx

from fastapi import (
    BackgroundTasks,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import AnalysisRun
from app.services.analysis_service import (
    prepare_analysis_run,
    run_analysis_job,
)
from app.llm.client import (
    default_model_for_provider,
    normalize_llm_provider,
)

from pydantic import BaseModel


class StartAnalysisRequest(BaseModel):
    provider: Literal[
        "mistral",
    ] | None = None
    model_name: str | None = None
    pipeline: Literal["graph"] | None = None


class StartBatchEvalRequest(BaseModel):
    provider: Literal[
        "mistral",
    ] = "mistral"
    model_name: str | None = None
    pipeline: Literal["graph"] = "graph"
    case_ids: list[str] | None = None


BATCH_EVAL_STATE = {
    "is_running": False,
    "completed_cases": 0,
    "total_cases": 0,
    "current_case_title": None,
    "error": None,
}


def _run_batch_eval_job(
    provider: str,
    model_name: str | None,
    pipeline: str = "graph",
    case_ids: list[str] | None = None,
):
    global BATCH_EVAL_STATE
    BATCH_EVAL_STATE["is_running"] = True
    BATCH_EVAL_STATE["completed_cases"] = 0
    BATCH_EVAL_STATE["total_cases"] = 0
    BATCH_EVAL_STATE["current_case_title"] = None
    BATCH_EVAL_STATE["error"] = None

    def on_progress(current: int, total: int, title: str):
        BATCH_EVAL_STATE["completed_cases"] = current
        BATCH_EVAL_STATE["total_cases"] = total
        BATCH_EVAL_STATE["current_case_title"] = title

    try:
        run_rca_evals(
            provider=provider,
            model_name=model_name,
            pipeline=pipeline,
            case_ids=case_ids,
            progress_callback=on_progress,
            verbose=False,
        )
    except Exception as e:
        BATCH_EVAL_STATE["error"] = str(e)
    finally:
        BATCH_EVAL_STATE["is_running"] = False


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DASHBOARD_HTML = (
    Path(__file__).resolve().parent
    / "index.html"
)

DATASET_ROOT = (
    PROJECT_ROOT
    / "data"
    / "rca_eval"
    / "v1"
)

BASELINE_ROOT = (
    PROJECT_ROOT
    / "baselines"
    / "v0.1.0"
)

RETRIEVAL_REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "retrieval_eval_latest.json"
)

router = APIRouter(
    prefix="/dev",
    tags=["developer-console"],
    include_in_schema=False,
)


def _read_json(
    path: Path,
) -> dict[str, Any] | None:
    if not path.exists():
        return None

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


@router.get("/api/retrieval-eval")
def retrieval_eval():
    report = _read_json(
        RETRIEVAL_REPORT_PATH
    )

    if report is None:
        return {
            "available": False,
            "message": (
                "Run `make eval` to generate "
                "retrieval metrics."
            ),
        }

    return {
        "available": True,
        "report": report,
    }


@router.get(
    "",
    response_class=HTMLResponse,
)
def developer_console() -> HTMLResponse:
    return HTMLResponse(
        DASHBOARD_HTML.read_text(
            encoding="utf-8"
        )
    )


@router.get("/api/meta")
def current_metadata() -> dict[str, Any]:
    return build_analysis_run_metadata()


@router.get("/api/eval-dataset")
def evaluation_dataset() -> dict[str, Any]:
    manifest, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    return {
        "manifest": manifest.model_dump(
            mode="json"
        ),
        "cases": [
            {
                "id": case.id,
                "title": case.title,
                "scenario_type": (
                    case.scenario_type
                ),
                "difficulty": case.difficulty,
                "tags": case.tags,
                "service_name": (
                    case.incident.service_name
                ),
                "expected_confidence": (
                    case.expectations
                    .root_cause
                    .acceptable_confidence
                ),
                "causal_strength": (
                    case.expectations
                    .root_cause
                    .causal_strength
                ),
            }
            for case in cases
        ],
    }


@router.post("/api/eval-dataset/run", status_code=202)
def start_batch_eval(
    payload: StartBatchEvalRequest,
    background_tasks: BackgroundTasks,
):
    global BATCH_EVAL_STATE
    if BATCH_EVAL_STATE["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="A batch evaluation is already running.",
        )
    
    background_tasks.add_task(
        _run_batch_eval_job,
        payload.provider,
        payload.model_name,
        payload.pipeline,
        payload.case_ids,
    )

    return {"status": "accepted"}


@router.get("/api/eval-dataset/status")
def batch_eval_status():
    global BATCH_EVAL_STATE
    return BATCH_EVAL_STATE


@router.get("/api/eval-dataset/latest-report")
def latest_eval_report():
    report_path = PROJECT_ROOT / "reports" / "rca_eval_latest.json"
    report = _read_json(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No report found.",
        )
    return report




@router.get("/api/baseline")
def baseline() -> dict[str, Any]:
    generation_config = _read_json(
        BASELINE_ROOT
        / "generation_config.json"
    )

    # Temporary backward compatibility in case an older
    # branch used config.json.
    if generation_config is None:
        generation_config = _read_json(
            BASELINE_ROOT / "config.json"
        )

    return {
        "available": BASELINE_ROOT.exists(),
        "manifest": _read_json(
            BASELINE_ROOT / "manifest.json"
        ),
        "metadata": _read_json(
            BASELINE_ROOT / "metadata.json"
        ),
        "generation_config": generation_config,
        "report": _read_json(
            BASELINE_ROOT / "rca_output.json"
        ),
        "schema": _read_json(
            BASELINE_ROOT / "rca_schema.json"
        ),
        "retrieval_eval": _read_json(
            BASELINE_ROOT
            / "retrieval_eval.json"
        ),
    }

@router.post(
    "/api/incidents/{incident_id}/analysis-runs",
    status_code=202,
)
def start_analysis_run(
    incident_id: str,
    payload: StartAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    analysis_run = prepare_analysis_run(
        db=db,
        incident_id=incident_id,
        provider=payload.provider,
        model_name=payload.model_name,
        pipeline=payload.pipeline,
    )

    background_tasks.add_task(
        run_analysis_job,
        analysis_run.id,
    )

    return {
        "analysis_run_id": analysis_run.id,
        "status": analysis_run.status,
        "progress_stage": (
            analysis_run.progress_stage
        ),
    }

@router.get(
    "/api/analysis-runs/{analysis_run_id}"
)
def analysis_run_detail(
    analysis_run_id: str,
    db: Session = Depends(get_db),
):
    analysis_run = db.get(
        AnalysisRun,
        analysis_run_id,
    )

    if analysis_run is None:
        raise HTTPException(
            status_code=404,
            detail="analysis run not found",
        )

    return {
        "id": analysis_run.id,
        "incident_id": (
            analysis_run.incident_id
        ),
        "status": analysis_run.status,
        "model_name": (
            analysis_run.model_name
        ),
        "provider": (
            (analysis_run.run_config or {})
            .get("llm", {})
            .get("runtime", "mistral")
        ),
        "pipeline_mode": (
            (analysis_run.run_config or {})
            .get("llm", {})
            .get("pipeline_mode", "graph")
        ),
        "progress_stage": (
            analysis_run.progress_stage
        ),
        "progress_message": (
            analysis_run.progress_message
        ),
        "progress_percent": (
            analysis_run.progress_percent
        ),
        "failure_type": (
            analysis_run.failure_type
        ),
        "error_message": (
            analysis_run.error_message
        ),
        "report": analysis_run.report,
        "raw_model_output": (
            analysis_run.raw_model_output
        ),
        "validation_errors": (
            analysis_run.validation_errors
            or []
        ),
        "generation_metadata": (
            analysis_run.generation_metadata
        ),
        "generation_attempts": (
            analysis_run.generation_attempts
            or []
        ),
        "retrieval_diagnostics": (
            analysis_run
            .retrieval_diagnostics
        ),
        "pipeline_version": (
            analysis_run.pipeline_version
        ),
        "schema_version": (
            analysis_run.schema_version
        ),
        "prompt_version": (
            analysis_run.prompt_version
        ),
        "started_at": (
            analysis_run.started_at
        ),
        "completed_at": (
            analysis_run.completed_at
        ),
    }

def _mistral_api_key() -> str:
    if settings.mistral_api_key is None:
        return ""

    return (
        settings.mistral_api_key
        .get_secret_value()
        .strip()
    )


@router.get("/api/llm-models")
def llm_models(
    provider: Literal[
        "mistral",
    ],
):
    selected_provider = normalize_llm_provider(
        provider
    )

    api_key = _mistral_api_key()

    if not api_key:
        return {
            "provider": selected_provider,
            "configured": False,
            "default_model": settings.mistral_model,
            "models": [],
            "message": (
                "Set MISTRAL_API_KEY to use "
                "the Mistral provider."
            ),
        }

    url = (
        settings.mistral_base_url
        .rstrip("/")
        + "/v1/models"
    )
    headers = {
        "Authorization": (
            f"Bearer {api_key}"
        )
    }

    try:
        response = httpx.get(
            url,
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()

        payload = response.json()

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not list Mistral "
                f"models: {exc}"
            ),
        ) from exc

    model_records = (
        payload.get("data", [])
        if isinstance(payload, dict)
        else payload
    )
    model_names = sorted(
        model["id"]
        for model in model_records
        if (
            model.get("id")
            and not model.get(
                "archived",
                False,
            )
            and (
                model.get(
                    "capabilities",
                    {},
                ).get(
                    "completion_chat",
                    True,
                )
            )
        )
    )

    return {
        "provider": selected_provider,
        "configured": True,
        "default_model": (
            default_model_for_provider(
                selected_provider
            )
        ),
        "models": model_names,
    }
