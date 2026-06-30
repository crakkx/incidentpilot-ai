from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(tags=["health"])


@router.get("/")
def root():
    return {
        "message": f"{settings.app_name} API",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "incidentpilot-ai",
        "version": settings.app_version,
    }
