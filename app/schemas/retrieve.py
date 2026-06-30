from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(3, ge=1, le=10)


class RetrievalResult(BaseModel):
    document_id: str
    document_title: str
    chunk_id: str
    chunk_index: int
    content: str
    score: float


class RetrieveResponse(BaseModel):
    query: str
    results: list[RetrievalResult]
