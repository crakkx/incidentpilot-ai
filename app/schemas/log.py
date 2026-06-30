from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
