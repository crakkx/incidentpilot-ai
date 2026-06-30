from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import analysis, documents, health, incidents, logs, retrieve
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
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
app.include_router(analysis.router)
