import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.db.base import Base, import_models  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.repositories.user_repository import create_user, get_user_by_email  # noqa: E402


import_models()
Base.metadata.create_all(bind=engine)


def _assert_test_database() -> None:
    database_name = engine.url.database or ""

    if "test" not in database_name:
        raise RuntimeError(
            "Refusing to run tests against a non-test database. "
            f"Current database is: {database_name!r}. "
            "Set TEST_DATABASE_URL to a database name containing 'test'."
        )


def _truncate_database() -> None:
    _assert_test_database()

    table_names = [
        table.name
        for table in reversed(Base.metadata.sorted_tables)
    ]

    if not table_names:
        return

    quoted_table_names = ", ".join(
        f'"{table_name}"'
        for table_name in table_names
    )

    statement = text(
        f"TRUNCATE TABLE {quoted_table_names} RESTART IDENTITY CASCADE"
    )

    with engine.begin() as connection:
        connection.execute(statement)


@pytest.fixture(autouse=True)
def clean_database(request):
    if "no_db" in request.keywords:
        yield
        return
    _truncate_database()
    yield
    _truncate_database()


def _issue_token(role: str) -> str:
    db = SessionLocal()
    try:
        email = f"test-{role}@incidentpilot.example"
        user = get_user_by_email(db, email)
        if user is None:
            user = create_user(
                db,
                email=email,
                hashed_password=hash_password("test-password"),
                role=role,
            )
            db.commit()
        return create_access_token(user_id=user.id, email=user.email, role=user.role)
    finally:
        db.close()


@pytest.fixture()
def client(clean_database):
    """Authenticated as an admin — passes every role gate. Most tests only
    care about the endpoint under test, not the auth layer itself."""
    with TestClient(app) as test_client:
        test_client.headers.update(
            {"Authorization": f"Bearer {_issue_token('admin')}"}
        )
        yield test_client


@pytest.fixture()
def anon_client(clean_database):
    """Unauthenticated client, for testing the auth layer itself."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def role_client(clean_database):
    """Factory fixture: role_client('viewer') -> TestClient authenticated as that role."""

    def _make(role: str) -> TestClient:
        test_client = TestClient(app)
        test_client.headers.update(
            {"Authorization": f"Bearer {_issue_token(role)}"}
        )
        return test_client

    return _make


@pytest.fixture()
def db_session():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
