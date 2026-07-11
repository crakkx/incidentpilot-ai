from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.retrieve import RetrieveRequest, RetrieveResponse
from app.services.retrieval_service import retrieve as service_retrieve


router = APIRouter(tags=["retrieve"])


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(
    payload: RetrieveRequest,
    db: Session = Depends(get_db),
):
    return service_retrieve(
        db=db,
        query=payload.query,
        top_k=payload.top_k,
        service_name=payload.service_name,
        document_type=payload.document_type,
        severity=payload.severity,
    )
