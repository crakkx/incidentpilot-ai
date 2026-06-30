from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    id: str
    title: str
    filename: str | None
    content_type: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    id: str
    title: str
    filename: str | None
    content_type: str | None
    created_at: datetime
    chunk_count: int


class IndexDocumentsResponse(BaseModel):
    documents_indexed: int
    chunks_created: int
