from datetime import datetime

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    id: str
    title: str
    filename: str | None
    content_type: str | None
    service_name: str | None
    document_type: str
    severity: str | None
    created_at: datetime
    chunk_count: int


class IndexDocumentsResponse(BaseModel):
    documents_indexed: int
    chunks_created: int
