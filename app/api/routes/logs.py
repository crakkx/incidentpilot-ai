from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.log import LogIngestRequest, LogIngestResponse
from app.services.ingestion_service import ingest_logs as service_ingest_logs


router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("/ingest", response_model=LogIngestResponse, status_code=201)
def ingest_logs(
    payload: LogIngestRequest,
    db: Session = Depends(get_db),
):
    return service_ingest_logs(db=db, payload=payload)
