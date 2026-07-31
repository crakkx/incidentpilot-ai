from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import documents, health, incidents, logs, retrieve
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    
    try:
        import mlflow
        import os
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("IncidentPilot-RCA")
    except ImportError:
        pass
        
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-powered incident analysis assistant.",
    version=settings.app_version,
    lifespan=lifespan,
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(incidents.router)
app.include_router(logs.router)
app.include_router(documents.router)
app.include_router(retrieve.router)

from app.api.metrics import router as metrics_router, metrics_app
app.include_router(metrics_router)
app.mount("/metrics", metrics_app)

if settings.environment == "development":
    from app.dev_dashboard.router import (
        router as developer_dashboard_router,
    )

    app.include_router(
        developer_dashboard_router
    )
