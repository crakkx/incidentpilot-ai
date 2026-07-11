from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.rag.embeddings import embed_text


def retrieve_document_chunks(
    db: Session,
    query: str,
    top_k: int,
    service_name: str | None = None,
    document_type: str | None = None,
    severity: str | None = None,
) -> list[dict]:
    query_embedding = embed_text(query)

    if not any(query_embedding):
        return []

    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    statement = (
        select(
            DocumentChunk,
            Document.title.label("document_title"),
            Document.service_name.label("service_name"),
            Document.document_type.label("document_type"),
            Document.severity.label("severity"),
            distance.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
    )

    if service_name:
        statement = statement.where(Document.service_name == service_name)

    if document_type:
        statement = statement.where(Document.document_type == document_type)

    if severity:
        statement = statement.where(Document.severity == severity)

    statement = (
        statement
        .order_by(distance)
        .limit(top_k)
    )

    rows = db.execute(statement).all()

    chunks = []

    for (
        chunk,
        document_title,
        row_service_name,
        row_document_type,
        row_severity,
        chunk_distance,
    ) in rows:
        score = 1.0 - float(chunk_distance)

        chunks.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_title": document_title,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "score": score,
                "metadata": {
                    "service_name": row_service_name,
                    "document_type": row_document_type,
                    "severity": row_severity,
                },
            }
        )

    return chunks
