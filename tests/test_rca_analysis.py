from datetime import datetime, timedelta

from sqlalchemy import select

from app.llm.client import (
    InvalidRCAOutputError,
    RCAClient,
    get_rca_client,
)
from app.main import app
from app.models import (
    AnalysisRun,
    Deployment,
    Document,
    DocumentChunk,
    Incident,
    LogEntry,
    Metric,
    Service,
)
from app.rag.embeddings import embed_text
from app.schemas.analysis import (
    EvidenceItem,
    RCAReport,
)


class FakeRCAClient(RCAClient):
    def __init__(self):
        self.last_evidence = None

    def generate_rca(
        self,
        evidence_payload,
    ) -> RCAReport:
        self.last_evidence = evidence_payload

        metric = evidence_payload["metrics"][0]
        log = evidence_payload["logs"][0]

        return RCAReport(
            incident_summary=(
                "Payments failed after a recent deployment."
            ),
            likely_root_cause=(
                "Database connection pool exhaustion caused "
                "payment authorization requests to time out."
            ),
            evidence=[
                EvidenceItem(
                    source_type="metric",
                    source_id=metric["id"],
                    excerpt=(
                        f"{metric['metric_name']}="
                        f"{metric['value']} {metric['unit']}"
                    ),
                    explanation=(
                        "The database connection count was near "
                        "the configured capacity."
                    ),
                ),
                EvidenceItem(
                    source_type="log",
                    source_id=log["id"],
                    excerpt=log["message"],
                    explanation=(
                        "The application directly reported a "
                        "database connection timeout."
                    ),
                ),
            ],
            recommended_actions=[
                "Roll back the recent payments-api deployment.",
                "Inspect database connection pool usage.",
            ],
            confidence="high",
            missing_information=[
                "The exact database pool maximum was not supplied."
            ],
        )


class InventedEvidenceClient(RCAClient):
    def generate_rca(
        self,
        evidence_payload,
    ) -> RCAReport:
        return RCAReport(
            incident_summary="A payment incident occurred.",
            likely_root_cause="Database timeout.",
            evidence=[
                EvidenceItem(
                    source_type="log",
                    source_id="invented-log-id",
                    excerpt="Invented log.",
                    explanation="This source does not exist.",
                )
            ],
            recommended_actions=[
                "Inspect the database."
            ],
            confidence="low",
            missing_information=[],
        )


class InvalidOutputClient(RCAClient):
    def generate_rca(
        self,
        evidence_payload,
    ) -> RCAReport:
        raise InvalidRCAOutputError(
            "Invalid test output."
        )


def seed_incident_evidence(db_session):
    service = Service(
        name="payments-api",
        description="Payment service",
        owner_team="payments",
    )

    db_session.add(service)
    db_session.flush()

    started_at = datetime.utcnow()

    incident = Incident(
        title="Payments database timeout",
        description=(
            "Payments failed shortly after deployment."
        ),
        severity="high",
        status="open",
        service_id=service.id,
        service_name=service.name,
        started_at=started_at,
    )

    db_session.add(incident)
    db_session.flush()

    deployment = Deployment(
        service_id=service.id,
        service_name=service.name,
        version="v-test",
        environment="production",
        commit_sha="test123",
        deployed_at=(
            started_at
            - timedelta(minutes=45)
        ),
    )

    log = LogEntry(
        service_id=service.id,
        service_name=service.name,
        incident_id=incident.id,
        timestamp=(
            started_at
            + timedelta(minutes=1)
        ),
        level="ERROR",
        message="database connection timeout",
        source="test",
        context={},
    )

    out_of_window_log = LogEntry(
        service_id=service.id,
        service_name=service.name,
        incident_id=incident.id,
        timestamp=(
            started_at
            + timedelta(hours=3)
        ),
        level="ERROR",
        message="This log must not be collected",
        source="test",
        context={},
    )

    metric = Metric(
        service_name=service.name,
        timestamp=(
            started_at
            + timedelta(minutes=2)
        ),
        metric_name="db_connections",
        value=95,
        unit="count",
    )

    document = Document(
        title="Payment Database Runbook",
        filename="payment-db-runbook.md",
        content_type="text/markdown",
        service_name=service.name,
        document_type="runbook",
        severity="high",
        content=(
            "When database connection timeout errors begin "
            "after deployment, check connection pool usage "
            "and consider rollback."
        ),
    )

    db_session.add_all(
        [
            deployment,
            log,
            out_of_window_log,
            metric,
            document,
        ]
    )

    db_session.flush()

    chunk_content = (
        "Check database connection pool usage and roll back "
        "a recent deployment when strongly correlated."
    )

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content=chunk_content,
        embedding=embed_text(chunk_content),
    )

    db_session.add(chunk)
    db_session.commit()

    return {
        "incident": incident,
        "log": log,
        "out_of_window_log": out_of_window_log,
        "metric": metric,
        "deployment": deployment,
    }


def test_analyze_incident_returns_and_saves_report(
    client,
    db_session,
):
    seeded = seed_incident_evidence(db_session)
    fake_client = FakeRCAClient()

    app.dependency_overrides[get_rca_client] = (
        lambda: fake_client
    )

    try:
        response = client.post(
            f"/incidents/{seeded['incident'].id}/analyze"
        )
    finally:
        app.dependency_overrides.pop(
            get_rca_client,
            None,
        )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "completed"
    assert data["model_name"] == "qwen2.5:3b"

    assert (
        data["report"]["confidence"]
        == "high"
    )

    assert len(
        data["report"]["evidence"]
    ) >= 1

    db_session.expire_all()

    analysis_run = db_session.get(
        AnalysisRun,
        data["analysis_run_id"],
    )

    assert analysis_run is not None
    assert analysis_run.status == "completed"
    assert analysis_run.report is not None
    assert analysis_run.evidence_snapshot is not None

    collected_log_ids = {
        item["id"]
        for item in fake_client.last_evidence["logs"]
    }

    assert str(
        seeded["log"].id
    ) in collected_log_ids

    assert str(
        seeded["out_of_window_log"].id
    ) not in collected_log_ids


def test_analyze_unknown_incident_returns_404(
    client,
):
    response = client.post(
        "/incidents/missing-incident/analyze"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "incident not found"
    )


def test_invented_evidence_id_marks_run_failed(
    client,
    db_session,
):
    seeded = seed_incident_evidence(db_session)

    app.dependency_overrides[get_rca_client] = (
        lambda: InventedEvidenceClient()
    )

    try:
        response = client.post(
            f"/incidents/{seeded['incident'].id}/analyze"
        )
    finally:
        app.dependency_overrides.pop(
            get_rca_client,
            None,
        )

    assert response.status_code == 502

    db_session.expire_all()

    statement = (
        select(AnalysisRun)
        .where(
            AnalysisRun.incident_id
            == seeded["incident"].id
        )
        .order_by(
            AnalysisRun.started_at.desc()
        )
    )

    analysis_run = (
        db_session.execute(statement)
        .scalars()
        .first()
    )

    assert analysis_run is not None
    assert analysis_run.status == "failed"
    assert analysis_run.error_message is not None


def test_invalid_llm_output_marks_run_failed(
    client,
    db_session,
):
    seeded = seed_incident_evidence(db_session)

    app.dependency_overrides[get_rca_client] = (
        lambda: InvalidOutputClient()
    )

    try:
        response = client.post(
            f"/incidents/{seeded['incident'].id}/analyze"
        )
    finally:
        app.dependency_overrides.pop(
            get_rca_client,
            None,
        )

    assert response.status_code == 502

    db_session.expire_all()

    statement = (
        select(AnalysisRun)
        .where(
            AnalysisRun.incident_id
            == seeded["incident"].id
        )
        .order_by(
            AnalysisRun.started_at.desc()
        )
    )

    analysis_run = (
        db_session.execute(statement)
        .scalars()
        .first()
    )

    assert analysis_run is not None
    assert analysis_run.status == "failed"
