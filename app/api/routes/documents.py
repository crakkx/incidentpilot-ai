from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import DocumentUploadResponse, IndexDocumentsResponse
from app.services.retrieval_service import (
    create_and_index_document,
    index_all_documents,
)


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
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
    )

    return {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "content_type": document.content_type,
        "created_at": document.created_at,
        "chunk_count": chunk_count,
    }


@router.post("/index", response_model=IndexDocumentsResponse)
def index_documents(db: Session = Depends(get_db)):
    return index_all_documents(db=db)
