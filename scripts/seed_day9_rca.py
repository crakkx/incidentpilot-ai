import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Deployment,
    Document,
    Incident,
    LogEntry,
    Metric,
    Service,
)
from app.services.retrieval_service import (  # noqa: E402
    index_document,
)


INCIDENT_TITLE = "Payments database timeout after deployment"


def main() -> None:
    db = SessionLocal()

    try:
        service = db.execute(
            select(Service).where(
                Service.name == "payments-api"
            )
        ).scalar_one_or_none()

        if service is None:
            service = Service(
                name="payments-api",
                description=(
                    "Handles payment authorization and capture."
                ),
                owner_team="payments",
            )

            db.add(service)
            db.flush()

        incident = db.execute(
            select(Incident).where(
                Incident.title == INCIDENT_TITLE
            )
        ).scalar_one_or_none()

        if incident is None:
            started_at = (
                datetime.utcnow()
                - timedelta(minutes=10)
            )

            incident = Incident(
                title=INCIDENT_TITLE,
                description=(
                    "Payment requests began failing shortly after "
                    "a payments-api deployment. Application logs "
                    "show database connection timeouts."
                ),
                severity="high",
                status="open",
                service_id=service.id,
                service_name=service.name,
                started_at=started_at,
            )

            db.add(incident)
            db.flush()
        else:
            started_at = incident.started_at

        deployment = db.execute(
            select(Deployment).where(
                Deployment.service_name == "payments-api",
                Deployment.version == "v2.4.0-day9",
            )
        ).scalar_one_or_none()

        if deployment is None:
            deployment = Deployment(
                service_id=service.id,
                service_name=service.name,
                version="v2.4.0-day9",
                environment="production",
                commit_sha="day9abc123",
                deployed_at=(
                    started_at
                    - timedelta(minutes=45)
                ),
            )

            db.add(deployment)

        existing_day9_logs = list(
            db.execute(
                select(LogEntry).where(
                    LogEntry.incident_id == incident.id,
                    LogEntry.source == "day9-seed",
                )
            )
            .scalars()
            .all()
        )

        if not existing_day9_logs:
            db.add_all(
                [
                    LogEntry(
                        service_id=service.id,
                        service_name=service.name,
                        incident_id=incident.id,
                        timestamp=(
                            started_at
                            - timedelta(minutes=2)
                        ),
                        level="INFO",
                        message=(
                            "payments-api database pool usage "
                            "increased after deployment"
                        ),
                        source="day9-seed",
                        context={
                            "pool_usage_percent": 94,
                        },
                    ),
                    LogEntry(
                        service_id=service.id,
                        service_name=service.name,
                        incident_id=incident.id,
                        timestamp=(
                            started_at
                            + timedelta(minutes=1)
                        ),
                        level="ERROR",
                        message=(
                            "database connection timeout while "
                            "authorizing payment"
                        ),
                        source="day9-seed",
                        context={
                            "status_code": 500,
                            "operation": "authorize_payment",
                        },
                    ),
                    LogEntry(
                        service_id=service.id,
                        service_name=service.name,
                        incident_id=incident.id,
                        timestamp=(
                            started_at
                            + timedelta(minutes=3)
                        ),
                        level="ERROR",
                        message=(
                            "database connection pool exhausted; "
                            "request failed"
                        ),
                        source="day9-seed",
                        context={
                            "active_connections": 95,
                            "pool_limit": 100,
                        },
                    ),
                ]
            )

        for metric_name, value, unit in [
            ("error_rate", 37, "percent"),
            ("latency_p95", 5000, "ms"),
            ("db_connections", 95, "count"),
        ]:
            metric = db.execute(
                select(Metric).where(
                    Metric.service_name == "payments-api",
                    Metric.metric_name == metric_name,
                    Metric.timestamp >= (
                        started_at
                        - timedelta(minutes=30)
                    ),
                    Metric.timestamp <= (
                        started_at
                        + timedelta(minutes=30)
                    ),
                )
            ).scalar_one_or_none()

            if metric is None:
                db.add(
                    Metric(
                        service_name="payments-api",
                        timestamp=(
                            started_at
                            + timedelta(minutes=4)
                        ),
                        metric_name=metric_name,
                        value=value,
                        unit=unit,
                    )
                )

        document = db.execute(
            select(Document).where(
                Document.title
                == "Payments Database Timeout Runbook"
            )
        ).scalar_one_or_none()

        if document is None:
            document = Document(
                title="Payments Database Timeout Runbook",
                filename="payments-database-timeout-runbook.md",
                content_type="text/markdown",
                service_name="payments-api",
                document_type="runbook",
                severity="high",
                content="""
# Payments Database Timeout Runbook

Use this runbook when payments-api experiences database
timeouts after a deployment.

Investigation steps:

- Compare error rate and latency before and after the deployment.
- Check database connection pool usage and active connections.
- Search logs for connection timeout and pool exhausted errors.
- Inspect the new deployment for connection leaks or slow queries.
- Check whether transaction duration increased after the release.

Recommended mitigation:

- Roll back the latest deployment when the timing strongly
  correlates with the incident.
- Reduce incoming traffic temporarily if the pool is saturated.
- Restart the service only when a confirmed connection leak exists.
- Inspect slow queries and database locks.
- Increase pool size only after confirming database capacity.
""".strip(),
            )

            db.add(document)
            db.flush()

        index_document(
            db=db,
            document=document,
        )

        db.commit()

        print("Day 9 RCA seed data is ready.")
        print(f"Incident ID: {incident.id}")
        print(f"Incident title: {incident.title}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
