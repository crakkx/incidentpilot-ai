from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from collections.abc import Callable
from statistics import fmean
from time import perf_counter

from app.core.config import settings
from app.models import Incident
from app.rag.retriever import retrieve_document_chunks
from app.repositories.deployment_repository import (
    list_deployments_in_window,
)
from app.repositories.log_repository import (
    list_logs_in_window,
)
from app.repositories.metric_repository import (
    list_metrics_in_window,
)
from app.schemas.analysis import RCAReport

class EvidenceValidationError(ValueError):
    def __init__(
        self,
        issues: list[dict[str, Any]],
    ) -> None:
        super().__init__(
            "The model cited evidence that was "
            "not supplied by the application."
        )

        self.issues = issues

def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _clip(
    value: str | None,
    limit: int,
) -> str | None:
    if value is None:
        return None

    if len(value) <= limit:
        return value

    return value[:limit] + "... [truncated]"


def _resolve_service_name(
    incident: Incident,
) -> str | None:
    if incident.service_name:
        return incident.service_name

    if incident.service:
        return incident.service.name

    return None


def _build_retrieval_query(
    incident: Incident,
    service_name: str | None,
) -> str:
    values = [
        incident.title,
        incident.description,
        service_name,
        incident.severity,
        "incident investigation root cause remediation runbook",
    ]

    return " ".join(
        value
        for value in values
        if value
    )


def build_allowed_evidence_ids(
    evidence_payload: dict[str, Any],
) -> dict[str, set[str]]:
    return {
        "log": {
            str(item["id"])
            for item in evidence_payload["logs"]
        },
        "metric": {
            str(item["id"])
            for item in evidence_payload["metrics"]
        },
        "deployment": {
            str(item["id"])
            for item in evidence_payload["deployments"]
        },
        "runbook": {
            str(item["id"])
            for item in evidence_payload["runbook_chunks"]
        },
    }


def validate_report_evidence(
    report: RCAReport,
    evidence_payload: dict[str, Any],
) -> None:
    allowed_ids = build_allowed_evidence_ids(
        evidence_payload
    )

    issues: list[dict[str, Any]] = []

    for index, evidence_item in enumerate(
        report.evidence
    ):
        source_id = str(
            evidence_item.source_id
        )

        valid_source_ids = allowed_ids[
            evidence_item.source_type
        ]

        if source_id not in valid_source_ids:
            issues.append(
                {
                    "type": "invented_evidence",
                    "loc": [
                        "evidence",
                        index,
                        "source_id",
                    ],
                    "msg": (
                        "The source ID was not present "
                        "in the evidence supplied to "
                        "the model."
                    ),
                    "input": source_id,
                    "source_type": (
                        evidence_item.source_type
                    ),
                    "allowed_source_ids": sorted(
                        valid_source_ids
                    ),
                }
            )

    if issues:
        raise EvidenceValidationError(
            issues
        )


ProgressCallback = Callable[
    [str, str, int],
    None,
]

def collect_incident_evidence_with_diagnostics(
    db: Session,
    incident: Incident,
    progress: ProgressCallback | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    def report_progress(
        stage: str,
        message: str,
        percent: int,
    ) -> None:
        if progress:
            progress(
                stage,
                message,
                percent,
            )

    started_at = incident.started_at
    service_name = _resolve_service_name(
        incident
    )

    logs_start = (
        started_at
        - timedelta(minutes=30)
    )
    logs_end = (
        started_at
        + timedelta(minutes=30)
    )

    deployments_start = (
        started_at
        - timedelta(hours=2)
    )
    deployments_end = (
        started_at
        + timedelta(minutes=30)
    )

    metrics_start = (
        started_at
        - timedelta(minutes=30)
    )
    metrics_end = (
        started_at
        + timedelta(minutes=30)
    )

    logs = []
    deployments = []
    metrics = []

    if service_name:
        report_progress(
            "collecting_logs",
            "Collecting service logs.",
            15,
        )

        logs = list_logs_in_window(
            db=db,
            service_name=service_name,
            start_time=logs_start,
            end_time=logs_end,
            limit=settings.rca_max_logs,
        )

        report_progress(
            "collecting_metrics",
            "Collecting service metrics.",
            25,
        )

        metrics = list_metrics_in_window(
            db=db,
            service_name=service_name,
            start_time=metrics_start,
            end_time=metrics_end,
            limit=settings.rca_max_metrics,
        )

        report_progress(
            "collecting_deployments",
            "Collecting recent deployments.",
            35,
        )

        deployments = (
            list_deployments_in_window(
                db=db,
                service_name=service_name,
                start_time=deployments_start,
                end_time=deployments_end,
                limit=(
                    settings
                    .rca_max_deployments
                ),
            )
        )

    retrieval_query = _build_retrieval_query(
        incident=incident,
        service_name=service_name,
    )

    report_progress(
        "retrieving_runbooks",
        "Retrieving relevant runbook chunks.",
        45,
    )

    retrieval_started = perf_counter()

    runbook_chunks = retrieve_document_chunks(
        db=db,
        query=retrieval_query,
        top_k=settings.rca_runbook_top_k,
        service_name=service_name,
        document_type="runbook",
    )

    retrieval_latency_ms = (
        perf_counter() - retrieval_started
    ) * 1000

    scores = [
        float(chunk.get("score", 0.0))
        for chunk in runbook_chunks
    ]

    retrieval_diagnostics = {
        "query": retrieval_query,
        "filters": {
            "service_name": service_name,
            "document_type": "runbook",
            "severity": None,
        },
        "top_k_requested": (
            settings.rca_runbook_top_k
        ),
        "returned_count": len(
            runbook_chunks
        ),
        "latency_ms": round(
            retrieval_latency_ms,
            2,
        ),
        "score_summary": {
            "top_score": (
                max(scores)
                if scores
                else None
            ),
            "lowest_score": (
                min(scores)
                if scores
                else None
            ),
            "mean_score": (
                round(fmean(scores), 4)
                if scores
                else None
            ),
        },
        "chunks": [
            {
                "rank": index + 1,
                "chunk_id": chunk.get(
                    "chunk_id"
                ),
                "document_id": chunk.get(
                    "document_id"
                ),
                "document_title": chunk.get(
                    "document_title"
                ),
                "score": chunk.get("score"),
                "metadata": chunk.get(
                    "metadata"
                ),
                "preview": (
                    chunk.get(
                        "content",
                        "",
                    )[:600]
                ),
            }
            for index, chunk in enumerate(
                runbook_chunks
            )
        ],
    }

    evidence_payload = {
        "incident": {
            "id": incident.id,
            "title": incident.title,
            "description": (
                incident.description
            ),
            "severity": incident.severity,
            "status": incident.status,
            "service_name": service_name,
            "started_at": _iso(
                incident.started_at
            ),
        },
        "collection_windows": {
            "logs": {
                "start": _iso(logs_start),
                "end": _iso(logs_end),
            },
            "deployments": {
                "start": _iso(
                    deployments_start
                ),
                "end": _iso(
                    deployments_end
                ),
            },
            "metrics": {
                "start": _iso(metrics_start),
                "end": _iso(metrics_end),
            },
        },
        "logs": [
            {
                "id": log.id,
                "timestamp": _iso(
                    log.timestamp
                ),
                "level": log.level,
                "message": _clip(
                    log.message,
                    1200,
                ),
                "source": log.source,
                "context": log.context,
            }
            for log in logs
        ],
        "deployments": [
            {
                "id": deployment.id,
                "version": (
                    deployment.version
                ),
                "environment": (
                    deployment.environment
                ),
                "commit_sha": (
                    deployment.commit_sha
                ),
                "deployed_at": _iso(
                    deployment.deployed_at
                ),
            }
            for deployment in deployments
        ],
        "metrics": [
            {
                "id": metric.id,
                "timestamp": _iso(
                    metric.timestamp
                ),
                "metric_name": (
                    metric.metric_name
                ),
                "value": metric.value,
                "unit": metric.unit,
            }
            for metric in metrics
        ],
        "runbook_chunks": [
            {
                "id": chunk["chunk_id"],
                "document_id": chunk[
                    "document_id"
                ],
                "document_title": chunk[
                    "document_title"
                ],
                "content": _clip(
                    chunk["content"],
                    1800,
                ),
                "score": chunk["score"],
                "metadata": chunk[
                    "metadata"
                ],
            }
            for chunk in runbook_chunks
        ],
    }

    return (
        evidence_payload,
        retrieval_diagnostics,
    )
