import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.evals.rca_dataset import (
    load_rca_eval_dataset,
)
from app.services.analysis_metadata import (
    build_analysis_run_metadata,
)


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


@router.get("/api/baseline")
def baseline() -> dict[str, Any]:
    return {
        "available": BASELINE_ROOT.exists(),
        "manifest": _read_json(
            BASELINE_ROOT / "manifest.json"
        ),
        "config": _read_json(
            BASELINE_ROOT / "config.json"
        ),
        "report": _read_json(
            BASELINE_ROOT / "rca_output.json"
        ),
        "retrieval_eval": _read_json(
            BASELINE_ROOT
            / "retrieval_eval.json"
        ),
    }