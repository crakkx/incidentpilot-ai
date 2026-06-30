from datetime import datetime

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
    service_name: str | None
    started_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
