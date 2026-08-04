from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    severity: str = Field(default="medium", max_length=50)
    status: str = Field(default="open", max_length=50)
    description: str | None = Field(default=None, max_length=10_000)
    service_name: str | None = Field(default=None, max_length=120)
    started_at: datetime | None = None


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
