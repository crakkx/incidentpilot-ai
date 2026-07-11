from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=2)
    service_name: str | None = None
    document_type: str | None = None
    severity: str | None = None
    top_k: int = Field(3, ge=1, le=10)


class RetrievalMetadata(BaseModel):
    service_name: str | None
    document_type: str | None
    severity: str | None


class RetrievalChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    score: float
    metadata: RetrievalMetadata


class RetrieveResponse(BaseModel):
    query: str
    chunks: list[RetrievalChunk]
