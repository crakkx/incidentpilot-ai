from sqlalchemy.orm import Session

from app import models
from app.chunking import chunk_text
from app.embeddings import embed_text


def index_document(db: Session, document: models.Document) -> int:
    existing_chunk_count = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.document_id == document.id)
        .count()
    )

    if existing_chunk_count > 0:
        return 0

    chunks = chunk_text(document.content)

    for chunk_index, chunk_content in enumerate(chunks):
        chunk = models.DocumentChunk(
            document_id=document.id,
            chunk_index=chunk_index,
            content=chunk_content,
            embedding=embed_text(chunk_content),
        )

        db.add(chunk)

    return len(chunks)
