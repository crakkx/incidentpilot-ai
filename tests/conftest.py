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


import_models()


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
def clean_database():
    _truncate_database()
    yield
    _truncate_database()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
