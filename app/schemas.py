from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=3)
    severity: str = "medium"
    status: str = "open"
    description: str | None = None
    service_name: str | None = None


class IncidentRead(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    description: str | None
    service_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentRead(BaseModel):
    id: str
    title: str
    filename: str | None
    content_type: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LogCreate(BaseModel):
    timestamp: datetime | None = None
    level: str = "INFO"
    message: str
    source: str | None = None
    context: dict[str, Any] | None = None


class LogIngestRequest(BaseModel):
    service_name: str
    incident_id: str | None = None
    logs: list[LogCreate]


class LogIngestResponse(BaseModel):
    ingested_count: int
    service_id: str
    service_name: str
