from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth, documents, health, incidents, logs, metrics as telemetry_metrics, retrieve, users
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.core.request_limits import MaxBodySizeMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()

    try:
        import os
        import mlflow
        tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
        # Only connect to MLflow if explicitly configured.
        # In CI / unit-test environments the MLflow server is not running,
        # so we skip initialisation entirely to avoid a connection error.
        if tracking_uri:
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(incidents.router)
app.include_router(logs.router)
app.include_router(telemetry_metrics.router)
app.include_router(documents.router)
app.include_router(retrieve.router)

from app.api.metrics import router as prometheus_metrics_router, metrics_app
app.include_router(prometheus_metrics_router)
app.mount("/metrics", metrics_app)

if settings.environment == "development":
    from app.dev_dashboard.router import (
        router as developer_dashboard_router,
    )

    app.include_router(
        developer_dashboard_router
    )
