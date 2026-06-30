from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    incident_id: str = Field(..., min_length=1)
    question: str | None = None


class AnalysisResponse(BaseModel):
    analysis_run_id: str
    incident_id: str
    status: str
    summary: str | None
