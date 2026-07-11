from sqlalchemy import func, select

from app.models import Document, Incident, LogEntry, Metric, Service
from scripts.seed import main as seed_main


def count_rows(db_session, model) -> int:
    statement = select(func.count()).select_from(model)
    return int(db_session.execute(statement).scalar_one())


def test_seed_data(db_session):
    seed_main()

    assert count_rows(db_session, Service) >= 3
    assert count_rows(db_session, Incident) >= 1
    assert count_rows(db_session, Document) >= 2
    assert count_rows(db_session, LogEntry) >= 3
    assert count_rows(db_session, Metric) == 3

    statement = select(Document).where(Document.service_name == "payments-api")
    payments_document = db_session.execute(statement).scalar_one_or_none()

    assert payments_document is not None
    assert payments_document.document_type == "runbook"
