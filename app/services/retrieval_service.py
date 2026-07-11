from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Document
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_texts
from app.rag.retriever import retrieve_document_chunks
from app.repositories.document_repository import (
    count_chunks_for_document,
    create_document,
    create_document_chunk,
    delete_all_document_chunks,
    list_documents,
)


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip().lower()

    if not cleaned:
        return None

    return cleaned


def _normalize_document_type(value: str | None) -> str:
    cleaned = _normalize_optional(value)

    return cleaned or "runbook"


def index_document(db: Session, document: Document) -> int:
    existing_chunk_count = count_chunks_for_document(db, document.id)

    if existing_chunk_count > 0:
        return 0

    chunks = chunk_text(document.content)

    if not chunks:
        return 0

    embeddings = embed_texts(chunks)

    for chunk_index, chunk_content in enumerate(chunks):
        create_document_chunk(
            db=db,
            document_id=document.id,
            chunk_index=chunk_index,
            content=chunk_content,
            embedding=embeddings[chunk_index],
        )

    return len(chunks)


def create_and_index_document(
    db: Session,
    title: str,
    filename: str | None,
    content_type: str | None,
    content: str,
    service_name: str | None,
    document_type: str | None,
    severity: str | None,
):
    document = create_document(
        db=db,
        title=title,
        filename=filename,
        content_type=content_type,
        content=content,
        service_name=_normalize_optional(service_name),
        document_type=_normalize_document_type(document_type),
        severity=_normalize_optional(severity),
    )

    chunk_count = index_document(db, document)

    db.commit()
    db.refresh(document)

    return document, chunk_count


def index_all_documents(db: Session) -> dict:
    documents = list_documents(db)

    documents_indexed = 0
    chunks_created = 0

    for document in documents:
        created_for_document = index_document(db, document)

        if created_for_document > 0:
            documents_indexed += 1
            chunks_created += created_for_document

    db.commit()

    return {
        "documents_indexed": documents_indexed,
        "chunks_created": chunks_created,
    }


def reindex_all_documents(db: Session) -> dict:
    delete_all_document_chunks(db)

    documents = list_documents(db)

    documents_indexed = 0
    chunks_created = 0

    for document in documents:
        created_for_document = index_document(db, document)

        if created_for_document > 0:
            documents_indexed += 1
            chunks_created += created_for_document

    db.commit()

    return {
        "documents_indexed": documents_indexed,
        "chunks_created": chunks_created,
    }


def retrieve(
    db: Session,
    query: str,
    top_k: int,
    service_name: str | None = None,
    document_type: str | None = None,
    severity: str | None = None,
) -> dict:
    cleaned_query = query.strip()

    if not cleaned_query:
        raise HTTPException(status_code=400, detail="query cannot be empty")

    chunks = retrieve_document_chunks(
        db=db,
        query=cleaned_query,
        top_k=top_k,
        service_name=_normalize_optional(service_name),
        document_type=_normalize_optional(document_type),
        severity=_normalize_optional(severity),
    )

    return {
        "query": cleaned_query,
        "chunks": chunks,
    }
