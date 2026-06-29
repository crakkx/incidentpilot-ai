from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.document_indexer import index_document
from app.embeddings import embed_text
from app.models import Document, DocumentChunk, Incident, LogEntry, Service
from app.schemas import (
    DocumentUploadResponse,
    IncidentCreate,
    IncidentRead,
    IndexDocumentsResponse,
    LogIngestRequest,
    LogIngestResponse,
    RetrieveRequest,
    RetrieveResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="IncidentPilot AI",
    description="AI-powered incident analysis assistant.",
    version="0.3.0",
    lifespan=lifespan,
)


def get_or_create_service(db: Session, name: str) -> Service:
    normalized_name = name.strip().lower()

    if not normalized_name:
        raise HTTPException(status_code=400, detail="service_name cannot be empty")

    service = db.query(Service).filter(Service.name == normalized_name).one_or_none()

    if service:
        return service

    service = Service(
        name=normalized_name,
        description=f"{normalized_name} service",
    )

    db.add(service)
    db.commit()
    db.refresh(service)

    return service


@app.get("/")
def root():
    return {
        "message": "IncidentPilot AI API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "incidentpilot-ai",
        "version": "0.3.0",
    }


@app.post("/incidents", response_model=IncidentRead, status_code=201)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
):
    service = None

    if payload.service_name:
        service = get_or_create_service(db, payload.service_name)

    incident = Incident(
        title=payload.title,
        severity=payload.severity,
        status=payload.status,
        description=payload.description,
        service_id=service.id if service else None,
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    return incident


@app.get("/incidents", response_model=list[IncidentRead])
def list_incidents(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Incident).order_by(Incident.created_at.desc())

    if status:
        query = query.filter(Incident.status == status)

    return query.all()


@app.post("/documents/upload", response_model=DocumentUploadResponse, status_code=201)
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

    document = Document(
        title=file.filename or "untitled-document",
        filename=file.filename,
        content_type=file.content_type,
        content=text_content,
    )

    db.add(document)
    db.flush()

    chunk_count = index_document(db, document)

    db.commit()
    db.refresh(document)

    return {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "content_type": document.content_type,
        "created_at": document.created_at,
        "chunk_count": chunk_count,
    }


@app.post("/documents/index", response_model=IndexDocumentsResponse)
def index_documents(db: Session = Depends(get_db)):
    documents = db.query(Document).all()

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


@app.post("/logs/ingest", response_model=LogIngestResponse, status_code=201)
def ingest_logs(
    payload: LogIngestRequest,
    db: Session = Depends(get_db),
):
    if not payload.logs:
        raise HTTPException(status_code=400, detail="logs cannot be empty")

    service = get_or_create_service(db, payload.service_name)

    if payload.incident_id:
        incident = db.get(Incident, payload.incident_id)

        if incident is None:
            raise HTTPException(status_code=404, detail="incident not found")

    for log_item in payload.logs:
        log_entry = LogEntry(
            service_id=service.id,
            incident_id=payload.incident_id,
            timestamp=log_item.timestamp or datetime.utcnow(),
            level=log_item.level.upper(),
            message=log_item.message,
            source=log_item.source,
            context=log_item.context,
        )

        db.add(log_entry)

    db.commit()

    return LogIngestResponse(
        ingested_count=len(payload.logs),
        service_id=service.id,
        service_name=service.name,
    )


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(
    payload: RetrieveRequest,
    db: Session = Depends(get_db),
):
    query = payload.query.strip()

    if not query:
        raise HTTPException(status_code=400, detail="query cannot be empty")

    query_embedding = embed_text(query)

    if not any(query_embedding):
        raise HTTPException(
            status_code=400,
            detail="query must contain searchable words",
        )

    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    rows = (
        db.query(
            DocumentChunk,
            Document.title.label("document_title"),
            distance.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .order_by(distance)
        .limit(payload.top_k)
        .all()
    )

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

    return {
        "query": query,
        "results": results,
    }
