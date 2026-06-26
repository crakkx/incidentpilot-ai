from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Document, Incident, LogEntry, Service
from app.schemas import (
    DocumentRead,
    IncidentCreate,
    IncidentRead,
    LogIngestRequest,
    LogIngestResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="IncidentPilot AI",
    description="AI-powered incident analysis assistant.",
    version="0.2.0",
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
        "version": "0.2.0",
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


@app.post("/documents/upload", response_model=DocumentRead, status_code=201)
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
    db.commit()
    db.refresh(document)

    return document


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
