from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Deployment, Document, Incident, LogEntry, Metric, Service
from app.services.retrieval_service import index_document


def get_or_create_service(
    db,
    name: str,
    description: str,
    owner_team: str,
) -> Service:
    statement = select(Service).where(Service.name == name)
    service = db.execute(statement).scalar_one_or_none()

    if service:
        return service

    service = Service(
        name=name,
        description=description,
        owner_team=owner_team,
    )

    db.add(service)
    db.flush()

    return service


def table_count(db, model) -> int:
    statement = select(func.count()).select_from(model)
    return int(db.execute(statement).scalar_one())


def main():
    db = SessionLocal()

    try:
        checkout = get_or_create_service(
            db=db,
            name="checkout-api",
            description="Handles cart checkout and order creation.",
            owner_team="commerce-platform",
        )

        payments = get_or_create_service(
            db=db,
            name="payments-api",
            description="Handles payment authorization and capture.",
            owner_team="payments",
        )

        search = get_or_create_service(
            db=db,
            name="search-api",
            description="Handles product search queries.",
            owner_team="discovery",
        )

        if table_count(db, Deployment) == 0:
            db.add_all(
                [
                    Deployment(
                        service_id=checkout.id,
                        service_name=checkout.name,
                        version="v1.8.2",
                        environment="production",
                        commit_sha="abc1234",
                        deployed_at=datetime.utcnow() - timedelta(hours=2),
                    ),
                    Deployment(
                        service_id=payments.id,
                        service_name=payments.name,
                        version="v2.3.0",
                        environment="production",
                        commit_sha="def5678",
                        deployed_at=datetime.utcnow() - timedelta(hours=5),
                    ),
                    Deployment(
                        service_id=search.id,
                        service_name=search.name,
                        version="v0.9.7",
                        environment="production",
                        commit_sha="ghi9012",
                        deployed_at=datetime.utcnow() - timedelta(days=1),
                    ),
                ]
            )

        incident_statement = select(Incident).where(
            Incident.title == "Checkout latency spike"
        )
        incident = db.execute(incident_statement).scalar_one_or_none()

        if incident is None:
            incident = Incident(
                title="Checkout latency spike",
                severity="high",
                status="open",
                description=(
                    "Users report slow checkout responses during payment confirmation."
                ),
                service_id=checkout.id,
                service_name=checkout.name,
                started_at=datetime.utcnow() - timedelta(minutes=30),
            )
            db.add(incident)
            db.flush()

        if table_count(db, Document) == 0:
            documents = [
                Document(
                    title="Checkout API Runbook",
                    filename="checkout-runbook.md",
                    content_type="text/markdown",
                    content=(
                        "# Checkout API Runbook\n\n"
                        "If checkout latency increases, check payment gateway latency, "
                        "database connection pool usage, recent deployments, and "
                        "checkout-api WARN and ERROR logs."
                    ),
                ),
                Document(
                    title="Payment Timeout Guide",
                    filename="payment-timeout-guide.md",
                    content_type="text/markdown",
                    content=(
                        "# Payment Timeout Guide\n\n"
                        "Payment gateway timeouts often appear as HTTP 504 errors. "
                        "Check provider status, retry queue depth, and payments-api logs."
                    ),
                ),
            ]

            db.add_all(documents)
            db.flush()

            for document in documents:
                index_document(db, document)

        if table_count(db, LogEntry) == 0:
            db.add_all(
                [
                    LogEntry(
                        service_id=checkout.id,
                        service_name=checkout.name,
                        incident_id=incident.id,
                        level="INFO",
                        message="POST /checkout started",
                        source="app",
                        context={"request_id": "req-001"},
                        timestamp=datetime.utcnow() - timedelta(minutes=29),
                    ),
                    LogEntry(
                        service_id=checkout.id,
                        service_name=checkout.name,
                        incident_id=incident.id,
                        level="WARN",
                        message="Payment provider response time exceeded 2000ms",
                        source="app",
                        context={"request_id": "req-001", "provider": "stripe"},
                        timestamp=datetime.utcnow() - timedelta(minutes=28),
                    ),
                    LogEntry(
                        service_id=checkout.id,
                        service_name=checkout.name,
                        incident_id=incident.id,
                        level="ERROR",
                        message="Checkout confirmation failed due to upstream timeout",
                        source="app",
                        context={"request_id": "req-001", "status_code": 504},
                        timestamp=datetime.utcnow() - timedelta(minutes=27),
                    ),
                ]
            )

        if table_count(db, Metric) == 0:
            metric_time = datetime(2026, 6, 26, 14, 30)

            db.add_all(
                [
                    Metric(
                        service_name="payments-api",
                        timestamp=metric_time,
                        metric_name="error_rate",
                        value=37,
                        unit="percent",
                    ),
                    Metric(
                        service_name="payments-api",
                        timestamp=metric_time,
                        metric_name="latency_p95",
                        value=5000,
                        unit="ms",
                    ),
                    Metric(
                        service_name="payments-api",
                        timestamp=metric_time,
                        metric_name="db_connections",
                        value=95,
                        unit="count",
                    ),
                ]
            )

        db.commit()

        print("Seed data inserted successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
