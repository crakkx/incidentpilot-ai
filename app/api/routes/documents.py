from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import DocumentUploadResponse, IndexDocumentsResponse
from app.services.retrieval_service import (
    create_and_index_document,
    index_all_documents,
    reindex_all_documents,
)


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    service_name: str | None = Form(None),
    document_type: str = Form("runbook"),
    severity: str | None = Form(None),
    db: Session = Depends(get_db),
):
    raw_content = await file.read()

    try:
        text_content = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Only UTF-8 text documents are supported right now.",
        ) from exc

    document, chunk_count = create_and_index_document(
        db=db,
        title=file.filename or "untitled-document",
        filename=file.filename,
        content_type=file.content_type,
        content=text_content,
        service_name=service_name,
        document_type=document_type,
        severity=severity,
    )

    return {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "content_type": document.content_type,
        "service_name": document.service_name,
        "document_type": document.document_type,
        "severity": document.severity,
        "created_at": document.created_at,
        "chunk_count": chunk_count,
    }


@router.post("/index", response_model=IndexDocumentsResponse)
def index_documents(db: Session = Depends(get_db)):
    return index_all_documents(db=db)


@router.post("/reindex", response_model=IndexDocumentsResponse)
def reindex_documents(db: Session = Depends(get_db)):
    return reindex_all_documents(db=db)
