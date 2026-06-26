from datetime import datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.models import Deployment, Document, Incident, LogEntry, Service


def main():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        if db.query(Service).count() > 0:
            print("Seed data already exists. Skipping.")
            return

        checkout = Service(
            name="checkout-api",
            description="Handles cart checkout and order creation.",
            owner_team="commerce-platform",
        )

        payments = Service(
            name="payments-api",
            description="Handles payment authorization and capture.",
            owner_team="payments",
        )

        search = Service(
            name="search-api",
            description="Handles product search queries.",
            owner_team="discovery",
        )

        db.add_all([checkout, payments, search])
        db.flush()

        db.add_all(
            [
                Deployment(
                    service_id=checkout.id,
                    version="v1.8.2",
                    environment="production",
                    commit_sha="abc1234",
                    deployed_at=datetime.utcnow() - timedelta(hours=2),
                ),
                Deployment(
                    service_id=payments.id,
                    version="v2.3.0",
                    environment="production",
                    commit_sha="def5678",
                    deployed_at=datetime.utcnow() - timedelta(hours=5),
                ),
                Deployment(
                    service_id=search.id,
                    version="v0.9.7",
                    environment="production",
                    commit_sha="ghi9012",
                    deployed_at=datetime.utcnow() - timedelta(days=1),
                ),
            ]
        )

        incident = Incident(
            title="Checkout latency spike",
            severity="high",
            status="open",
            description="Users report slow checkout responses during payment confirmation.",
            service_id=checkout.id,
        )

        db.add(incident)
        db.flush()

        db.add_all(
            [
                Document(
                    title="Checkout API Runbook",
                    filename="checkout-runbook.md",
                    content_type="text/markdown",
                    content=(
                        "# Checkout API Runbook\n\n"
                        "If checkout latency increases, check payment gateway latency, "
                        "database connection pool usage, and recent deployments."
                    ),
                ),
                Document(
                    title="Payment Timeout Guide",
                    filename="payment-timeout-guide.md",
                    content_type="text/markdown",
                    content=(
                        "# Payment Timeout Guide\n\n"
                        "Payment gateway timeouts often appear as HTTP 504 errors. "
                        "Check provider status and retry queue depth."
                    ),
                ),
            ]
        )

        db.add_all(
            [
                LogEntry(
                    service_id=checkout.id,
                    incident_id=incident.id,
                    level="INFO",
                    message="POST /checkout started",
                    source="app",
                    context={"request_id": "req-001"},
                ),
                LogEntry(
                    service_id=checkout.id,
                    incident_id=incident.id,
                    level="WARN",
                    message="Payment provider response time exceeded 2000ms",
                    source="app",
                    context={"request_id": "req-001", "provider": "stripe"},
                ),
                LogEntry(
                    service_id=checkout.id,
                    incident_id=incident.id,
                    level="ERROR",
                    message="Checkout confirmation failed due to upstream timeout",
                    source="app",
                    context={"request_id": "req-001", "status_code": 504},
                ),
            ]
        )

        db.commit()

        print("Seed data inserted successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
