from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.rag.embeddings import embed_text


def retrieve_document_chunks(
    db: Session,
    query: str,
    top_k: int,
) -> list[dict]:
    query_embedding = embed_text(query)

    if not any(query_embedding):
        return []

    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    statement = (
        select(
            DocumentChunk,
            Document.title.label("document_title"),
            distance.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .order_by(distance)
        .limit(top_k)
    )

    rows = db.execute(statement).all()

    results = []

    for chunk, document_title, chunk_distance in rows:
        score = 1.0 - float(chunk_distance)

        results.append(
            {
                "document_id": chunk.document_id,
                "document_title": document_title,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "score": score,
            }
        )

    return results
