from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models import User
from app.repositories.metric_repository import create_metrics_bulk


router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
)


class MetricItem(BaseModel):
    metric_name: str
    value: float
    unit: str | None = None
    timestamp: datetime | None = None


class MetricsIngestRequest(BaseModel):
    service_name: str
    metrics: list[MetricItem] = Field(min_length=1, max_length=500)


@router.post("")
def ingest_metrics(
    payload: MetricsIngestRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("operator", "admin")),
):
    """Ingest service telemetry metrics (e.g. CPU utilization, memory, latency)."""
    metrics_dicts = [item.model_dump() for item in payload.metrics]
    created = create_metrics_bulk(
        db=db,
        service_name=payload.service_name,
        metrics_data=metrics_dicts,
    )
    return {
        "message": f"Successfully ingested {len(created)} metric entries.",
        "ingested_count": len(created),
    }
