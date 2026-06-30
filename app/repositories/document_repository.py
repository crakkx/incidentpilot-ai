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
    return db.query(Document).all()


def count_chunks_for_document(db: Session, document_id: str) -> int:
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .count()
    )


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
