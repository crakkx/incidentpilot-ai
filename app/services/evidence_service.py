from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

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


def collect_incident_evidence(
    db: Session,
    incident: Incident,
) -> dict[str, Any]:
    started_at = incident.started_at
    service_name = _resolve_service_name(incident)

    logs_start = started_at - timedelta(minutes=30)
    logs_end = started_at + timedelta(minutes=30)

    deployments_start = started_at - timedelta(hours=2)
    deployments_end = started_at + timedelta(minutes=30)

    metrics_start = started_at - timedelta(minutes=30)
    metrics_end = started_at + timedelta(minutes=30)

    logs = []

    deployments = []

    metrics = []

    if service_name:
        logs = list_logs_in_window(
            db=db,
            service_name=service_name,
            start_time=logs_start,
            end_time=logs_end,
            limit=settings.rca_max_logs,
        )

        deployments = list_deployments_in_window(
            db=db,
            service_name=service_name,
            start_time=deployments_start,
            end_time=deployments_end,
            limit=settings.rca_max_deployments,
        )

        metrics = list_metrics_in_window(
            db=db,
            service_name=service_name,
            start_time=metrics_start,
            end_time=metrics_end,
            limit=settings.rca_max_metrics,
        )

    retrieval_query = _build_retrieval_query(
        incident=incident,
        service_name=service_name,
    )

    runbook_chunks = retrieve_document_chunks(
        db=db,
        query=retrieval_query,
        top_k=settings.rca_runbook_top_k,
        service_name=service_name,
        document_type="runbook",
    )

    return {
        "incident": {
            "id": incident.id,
            "title": incident.title,
            "description": incident.description,
            "severity": incident.severity,
            "status": incident.status,
            "service_name": service_name,
            "started_at": _iso(incident.started_at),
        },
        "collection_windows": {
            "logs": {
                "start": _iso(logs_start),
                "end": _iso(logs_end),
            },
            "deployments": {
                "start": _iso(deployments_start),
                "end": _iso(deployments_end),
            },
            "metrics": {
                "start": _iso(metrics_start),
                "end": _iso(metrics_end),
            },
        },
        "logs": [
            {
                "id": log.id,
                "timestamp": _iso(log.timestamp),
                "level": log.level,
                "message": _clip(log.message, 1200),
                "source": log.source,
                "context": log.context,
            }
            for log in logs
        ],
        "deployments": [
            {
                "id": deployment.id,
                "version": deployment.version,
                "environment": deployment.environment,
                "commit_sha": deployment.commit_sha,
                "deployed_at": _iso(deployment.deployed_at),
            }
            for deployment in deployments
        ],
        "metrics": [
            {
                "id": metric.id,
                "timestamp": _iso(metric.timestamp),
                "metric_name": metric.metric_name,
                "value": metric.value,
                "unit": metric.unit,
            }
            for metric in metrics
        ],
        "runbook_chunks": [
            {
                "id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "document_title": chunk["document_title"],
                "content": _clip(chunk["content"], 1800),
                "score": chunk["score"],
                "metadata": chunk["metadata"],
            }
            for chunk in runbook_chunks
        ],
    }


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

    for evidence_item in report.evidence:
        if evidence_item.source_id is None:
            continue

        source_id = str(evidence_item.source_id)

        valid_source_ids = allowed_ids[
            evidence_item.source_type
        ]

        if source_id not in valid_source_ids:
            raise ValueError(
                "The model cited an unknown evidence source: "
                f"type={evidence_item.source_type}, "
                f"id={source_id}"
            )
