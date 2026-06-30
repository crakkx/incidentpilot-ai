from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def init_db() -> None:
    """
    Database schema is now managed by Alembic migrations.

    This function is intentionally kept as a no-op for backwards compatibility
    with old scripts that may still import it.
    """
    return None


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
