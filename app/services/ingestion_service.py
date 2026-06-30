from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.incident_repository import get_incident
from app.repositories.log_repository import create_log_entry
from app.schemas.log import LogIngestRequest
from app.services.incident_service import get_or_create_service


def ingest_logs(db: Session, payload: LogIngestRequest):
    if not payload.logs:
        raise HTTPException(status_code=400, detail="logs cannot be empty")

    service = get_or_create_service(db, payload.service_name)

    if payload.incident_id:
        incident = get_incident(db, payload.incident_id)

        if incident is None:
            raise HTTPException(status_code=404, detail="incident not found")

    for log_item in payload.logs:
        create_log_entry(
            db=db,
            service_id=service.id,
            incident_id=payload.incident_id,
            timestamp=log_item.timestamp or datetime.utcnow(),
            level=log_item.level.upper(),
            message=log_item.message,
            source=log_item.source,
            context=log_item.context,
        )

    db.commit()

    return {
        "ingested_count": len(payload.logs),
        "service_id": service.id,
        "service_name": service.name,
    }
