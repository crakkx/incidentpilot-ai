"""Offline RCA evaluation runner.

Loads the eval dataset, runs each case through a configurable
:class:`~app.llm.client.RCAClient`, validates the output with
:func:`~app.evals.rca_validators.validate_case`, computes aggregate
:class:`~app.evals.rca_metrics.RCAEvalMetrics`, and writes JSON + Markdown
reports to disk.

The runner is **offline-first**: evidence payloads are built directly from
the :class:`~app.evals.rca_dataset.EvalEvidenceItem` objects in each case
file, so no database or running API is required.

Usage (CLI)::

    python scripts/run_rca_evals.py [--provider mistral] [--model MODEL]
                                    [--dataset PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.evals.rca_dataset import (
    EvalEvidenceItem,
    RCAEvalCase,
    load_rca_eval_dataset,
)
from app.evals.rca_metrics import (
    RCAEvalMetrics,
    compute_metrics,
    render_metrics_markdown,
)
from app.evals.rca_validators import (
    CaseValidationResult,
    validate_case,
)
from app.llm.client import (
    InvalidRCAOutputError,
    RCAClient,
    RCARequestError,
    get_rca_client,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATASET_ROOT = PROJECT_ROOT / "data" / "rca_eval" / "v1"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports"


# ---------------------------------------------------------------------------
# Evidence payload builder
# ---------------------------------------------------------------------------


def _iso(ts: Any) -> str | None:
    if ts is None:
        return None
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)


def build_evidence_payload(case: RCAEvalCase) -> dict[str, Any]:
    """Construct the evidence payload dict from an :class:`RCAEvalCase`.

    The structure mirrors what :func:`~app.services.evidence_service
    .collect_incident_evidence_with_diagnostics` produces for live runs.
    The LLM client accepts this dict directly.
    """
    logs: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    deployments: list[dict[str, Any]] = []
    runbook_chunks: list[dict[str, Any]] = []

    for item in case.evidence:
        if item.source_type == "log":
            logs.append(
                {
                    "id": item.id,
                    "timestamp": _iso(item.timestamp),
                    "level": item.data.get("level", "INFO"),
                    "message": item.content,
                    "source": case.incident.service_name,
                    "context": item.data,
                }
            )
        elif item.source_type == "metric":
            metrics.append(
                {
                    "id": item.id,
                    "timestamp": _iso(item.timestamp),
                    "description": item.content,
                    "metric_name": item.data.get(
                        "metric_name", item.id
                    ),
                    "value": item.data.get("value"),
                    "unit": item.data.get("unit"),
                }
            )
        elif item.source_type == "deployment":
            deployments.append(
                {
                    "id": item.id,
                    "description": item.content,
                    "version": item.data.get("version"),
                    "environment": item.data.get(
                        "environment", "production"
                    ),
                    "commit_sha": item.data.get("commit_sha"),
                    "deployed_at": _iso(item.timestamp),
                }
            )
        elif item.source_type == "runbook":
            runbook_chunks.append(
                {
                    "id": item.id,
                    "document_id": item.id,
                    "document_title": item.data.get(
                        "document_title", item.id
                    ),
                    "content": item.content,
                    "score": 1.0,
                    "metadata": item.data,
                }
            )

    return {
        "incident": {
            "id": case.incident.id,
            "title": case.incident.title,
            "description": case.incident.description,
            "severity": case.incident.severity,
            "status": "open",
            "service_name": case.incident.service_name,
            "started_at": _iso(case.incident.started_at),
        },
        "collection_windows": {},
        "logs": logs,
        "deployments": deployments,
        "metrics": metrics,
        "runbook_chunks": runbook_chunks,
    }


# ---------------------------------------------------------------------------
# Per-case runner
# ---------------------------------------------------------------------------


def run_case(
    case: RCAEvalCase,
    client: RCAClient,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run a single eval case and return a result dict.

    The result dict contains:

    * ``case_id``, ``case_title``, ``scenario_type``, ``difficulty``
    * ``status``      — ``"passed"`` / ``"failed"`` / ``"error"``
    * ``error``       — set when the LLM call itself failed
    * ``dimensions``  — list of per-dimension results
    * ``overall_score``
    """
    evidence_payload = build_evidence_payload(case)

    if verbose:
        print(f"  Running case {case.id}: {case.title}")

    try:
        generation_result = client.generate_rca_with_debug(evidence_payload)
        report = generation_result.report

    except (InvalidRCAOutputError, RCARequestError) as exc:
        if verbose:
            print(f"    [ERROR] {exc}")

        return {
            "case_id": case.id,
            "case_title": case.title,
            "scenario_type": case.scenario_type,
            "difficulty": case.difficulty,
            "status": "error",
            "error": str(exc),
            "dimensions": [],
            "overall_score": 0.0,
            "raw_output": None,
        }

    validation_result: CaseValidationResult = validate_case(case, report)
    status = "passed" if validation_result.passed else "failed"

    if verbose:
        icon = "✓" if validation_result.passed else "✗"
        print(
            f"    [{icon}] score={validation_result.overall_score:.2f} "
            f"passed={validation_result.passed}"
        )
        for dim in validation_result.dimensions:
            if not dim.passed:
                for issue in dim.issues:
                    print(f"       {dim.dimension}: {issue}")

    return {
        "case_id": case.id,
        "case_title": case.title,
        "scenario_type": case.scenario_type,
        "difficulty": case.difficulty,
        "status": status,
        "error": None,
        "overall_score": validation_result.overall_score,
        "dimensions": [
            {
                "dimension": d.dimension,
                "passed": d.passed,
                "score": d.score,
                "issues": d.issues,
            }
            for d in validation_result.dimensions
        ],
        "raw_output": report.model_dump(mode="json"),
        "validation": generation_result.metadata.get("validation"),
        "investigation_rounds": generation_result.metadata.get("investigation_rounds", 0),
        "tool_calls": len(generation_result.metadata.get("tool_results", [])),
    }



# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_rca_evals(
    *,
    provider: str = "mistral",
    model_name: str | None = None,

    case_ids: list[str] | None = None,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    verbose: bool = True,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Run eval cases offline and write JSON + Markdown reports.

    Args:
        provider:     LLM provider (``"mistral"`` only).
        model_name:   Model name override; provider default is used when
                      ``None``.

        case_ids:     Optional subset of case IDs to run. ``None`` (default)
                      runs every case in the dataset.
        dataset_root: Path to the dataset directory containing
                      ``manifest.json``.
        output_dir:   Directory where reports are written.
        verbose:      Print per-case results to stdout.
        progress_callback: Optional callback receiving (current_index, total_cases, case_title).

    Returns:
        The full report dict (also written to ``rca_eval_latest.json``).
    """
    manifest, cases = load_rca_eval_dataset(dataset_root)

    if case_ids:
        selected_ids = set(case_ids)
        cases = [case for case in cases if case.id in selected_ids]

    client = get_rca_client(
        provider=provider,
        model_name=model_name,

    )
    actual_model = getattr(client, "model_name", provider)

    if verbose:
        print(
            f"\nRCA eval — provider={provider}, "
            f"model={actual_model}"
        )
        print(f"Dataset: {manifest.dataset_id} v{manifest.dataset_version}")
        print(f"Cases:   {len(cases)}\n")

    case_results: list[dict[str, Any]] = []
    validation_results: list[CaseValidationResult] = []
    
    total_cases = len(cases)

    for idx, case in enumerate(cases):
        if progress_callback:
            progress_callback(idx + 1, total_cases, case.title)

        result = run_case(case, client, verbose=verbose)
        case_results.append(result)

        # Build a dummy CaseValidationResult for metric aggregation when the
        # LLM call itself failed (so metrics still account for the error case).
        if result["status"] == "error":
            from app.evals.rca_validators import DimensionResult

            validation_results.append(
                CaseValidationResult(
                    case_id=case.id,
                    dimensions=[
                        DimensionResult(
                            dimension=dim,
                            passed=False,
                            score=0.0,
                            issues=[result.get("error", "LLM call failed")],
                        )
                        for dim in (
                            "observations",
                            "root_cause",
                            "actions",
                            "source_types",
                            "numeric_facts",
                            "temporal_facts",
                            "causal_language",
                        )
                    ],
                )
            )
        else:
            from app.evals.rca_validators import (
                CaseValidationResult as CVR,
                DimensionResult,
            )

            validation_results.append(
                CVR(
                    case_id=case.id,
                    dimensions=[
                        DimensionResult(
                            dimension=d["dimension"],
                            passed=d["passed"],
                            score=d["score"],
                            issues=d["issues"],
                        )
                        for d in result["dimensions"]
                    ],
                )
            )

    rounds_list = [r.get("investigation_rounds", 0) for r in case_results]
    tool_calls_list = [r.get("tool_calls", 0) for r in case_results]
    metrics: RCAEvalMetrics = compute_metrics(validation_results, rounds_list, tool_calls_list)


    if verbose:
        print()
        print("=" * 72)
        print("RCA evaluation summary")
        print("=" * 72)
        print(metrics)

    generated_at = datetime.now(timezone.utc).isoformat()

    report: dict[str, Any] = {
        "generated_at": generated_at,
        "provider": provider,
        "pipeline": "graph",
        "model_name": actual_model,
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "case_ids_filter": list(case_ids) if case_ids else None,
        "metrics": metrics.to_dict(),
        "cases": case_results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "rca_eval_latest.json"
    markdown_path = output_dir / "rca_eval_latest.md"

    json_path.write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    markdown_path.write_text(
        render_metrics_markdown(
            metrics=metrics,
            generated_at=generated_at,
            model_name=actual_model,
            provider=provider,
        ),
        encoding="utf-8",
    )

    if verbose:
        print(f"\nJSON report:     {json_path}")
        print(f"Markdown report: {markdown_path}")

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: D401
    parser = argparse.ArgumentParser(
        description="Run IncidentPilot RCA evaluation offline against the eval dataset."
    )

    parser.add_argument(
        "--provider",
        default="mistral",
        choices=["mistral"],
        help="LLM provider to use (default: mistral).",
    )

    parser.add_argument(
        "--model",
        default=None,
        help="Model name override (uses provider default when omitted).",
    )



    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Subset of case IDs to run (default: all cases in the dataset).",
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help=f"Path to eval dataset root (default: {DEFAULT_DATASET_ROOT}).",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for reports (default: {DEFAULT_OUTPUT_DIR}).",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-case output.",
    )

    args = parser.parse_args()

    run_rca_evals(
        provider=args.provider,
        model_name=args.model,

        case_ids=args.cases,
        dataset_root=args.dataset,
        output_dir=args.output,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
