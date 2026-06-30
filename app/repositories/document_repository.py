from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk


def create_document(
    db: Session,
    title: str,
    filename: str | None,
    content_type: str | None,
    content: str,
) -> Document:
    document = Document(
        title=title,
        filename=filename,
        content_type=content_type,
        content=content,
    )

    db.add(document)
    db.flush()

    return document


def list_documents(db: Session) -> list[Document]:
    statement = select(Document)
    return list(db.execute(statement).scalars().all())


def count_chunks_for_document(db: Session, document_id: str) -> int:
    statement = (
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
    )

    return int(db.execute(statement).scalar_one())


def create_document_chunk(
    db: Session,
    document_id: str,
    chunk_index: int,
    content: str,
    embedding: list[float],
) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        embedding=embedding,
    )

    db.add(chunk)

    return chunk
