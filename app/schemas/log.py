from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LogCreate(BaseModel):
    timestamp: datetime | None = None
    level: str = Field(default="INFO", max_length=20)
    message: str = Field(max_length=10_000)
    source: str | None = Field(default=None, max_length=200)
    context: dict[str, Any] | None = None


class LogIngestRequest(BaseModel):
    service_name: str = Field(max_length=120)
    incident_id: str | None = None
    logs: list[LogCreate] = Field(max_length=1_000)


class LogIngestResponse(BaseModel):
    ingested_count: int
    service_id: str
    service_name: str
