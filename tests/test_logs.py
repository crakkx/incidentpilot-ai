from sqlalchemy import select

from app.models import LogEntry


def test_ingest_logs(client, db_session):
    response = client.post(
        "/logs/ingest",
        json={
            "service_name": "payments-api",
            "logs": [
                {
                    "level": "INFO",
                    "message": "Payment request started",
                    "source": "test",
                },
                {
                    "level": "ERROR",
                    "message": "Payment provider timeout",
                    "source": "test",
                    "context": {"status_code": 504},
                },
            ],
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["ingested_count"] == 2
    assert data["service_name"] == "payments-api"

    statement = select(LogEntry).where(LogEntry.service_name == "payments-api")
    logs = db_session.execute(statement).scalars().all()

    assert len(logs) == 2
    assert {log.level for log in logs} == {"INFO", "ERROR"}


def test_ingest_logs_rejects_empty_logs(client):
    response = client.post(
        "/logs/ingest",
        json={
            "service_name": "payments-api",
            "logs": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "logs cannot be empty"
