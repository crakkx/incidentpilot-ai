from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import SecretStr

from app.core.config import settings
from app.llm.client import (
    RCAGenerationResult,
    RCAClient,
)
from app.models import (
    AnalysisRun,
    Deployment,
    Incident,
    LogEntry,
    Metric,
    Service,
)
from app.schemas.analysis import (
    EvidenceItem,
    RCAReport,
)


def fake_retrieval_results(
    *args: Any,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    service_name = kwargs.get(
        "service_name",
        "payments-api",
    )

    return [
        {
            "chunk_id": "dashboard-runbook-1",
            "document_id": (
                "dashboard-document-1"
            ),
            "document_title": (
                "Dependency Failure Runbook"
            ),
            "chunk_index": 0,
            "content": (
                "Inspect dependency health, "
                "latency, and error responses."
            ),
            "score": 0.89,
            "metadata": {
                "service_name": service_name,
                "document_type": "runbook",
                "severity": "medium",
            },
        }
    ]


def seed_incident(
    db_session,
) -> Incident:
    suffix = uuid4().hex[:8]
    service_name = (
        f"dashboard-api-{suffix}"
    )

    service = Service(
        name=service_name,
        description="Dashboard test service",
        owner_team="platform",
    )

    db_session.add(service)
    db_session.flush()

    started_at = datetime.utcnow()

    incident = Incident(
        title="Dependency timeout",
        description=(
            "Requests failed because an "
            "upstream dependency timed out."
        ),
        severity="medium",
        status="open",
        service_id=service.id,
        service_name=service_name,
        started_at=started_at,
    )

    db_session.add(incident)
    db_session.flush()

    db_session.add_all(
        [
            LogEntry(
                service_id=service.id,
                service_name=service_name,
                incident_id=incident.id,
                timestamp=(
                    started_at
                    + timedelta(minutes=1)
                ),
                level="ERROR",
                message=(
                    "upstream dependency timeout"
                ),
                source="test",
                context={
                    "dependency": "catalog-api",
                },
            ),
            Metric(
                service_name=service_name,
                timestamp=(
                    started_at
                    + timedelta(minutes=2)
                ),
                metric_name="latency_p95",
                value=1800,
                unit="ms",
            ),
            Deployment(
                service_id=service.id,
                service_name=service_name,
                version="dashboard-test",
                environment="production",
                commit_sha="dashboard123",
                deployed_at=(
                    started_at
                    - timedelta(minutes=40)
                ),
            ),
        ]
    )

    db_session.commit()
    db_session.refresh(incident)

    return incident


class DashboardFakeClient(RCAClient):
    def __init__(
        self,
        model_name: str,
    ) -> None:
        self.model_name = model_name

    def _report(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        log_id = str(
            evidence_payload["logs"][0][
                "id"
            ]
        )

        return RCAReport(
            incident_summary=(
                "Requests failed during an "
                "upstream dependency timeout."
            ),
            likely_root_cause=(
                "The immediate observed failure "
                "was an upstream dependency "
                "timeout."
            ),
            evidence=[
                EvidenceItem(
                    source_type="log",
                    source_id=log_id,
                    excerpt=(
                        "upstream dependency "
                        "timeout"
                    ),
                    explanation=(
                        "The application directly "
                        "reported the timeout."
                    ),
                )
            ],
            recommended_actions=[
                "Inspect upstream dependency health."
            ],
            confidence="medium",
            missing_information=[
                "Dependency-side metrics."
            ],
        )

    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        return self._report(
            evidence_payload
        )

    def generate_rca_with_debug(
        self,
        evidence_payload: dict[str, Any],
        **kwargs: Any,
    ) -> RCAGenerationResult:
        report = self._report(
            evidence_payload
        )

        raw_output = (
            report.model_dump_json(
                indent=2
            )
        )

        metadata = {
            "done_reason": "stop",
            "prompt_eval_count": 800,
            "eval_count": 120,
            "total_duration_ms": 6000.0,
            "tokens_per_second": 20.0,
        }

        return RCAGenerationResult(
            report=report,
            raw_output=raw_output,
            metadata=metadata,
            attempts=[
                {
                    "attempt": 1,
                    "raw_output": raw_output,
                    "metadata": metadata,
                    "validation_errors": [],
                }
            ],
        )


def patch_dashboard_dependencies(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.evidence_service."
        "retrieve_document_chunks",
        fake_retrieval_results,
    )

    monkeypatch.setattr(
        "app.services.analysis_service."
        "get_rca_client",
        lambda provider=None, model_name=None, pipeline=None: (
            DashboardFakeClient(
                model_name
                or "mistral-small-latest"
            )
        ),
    )


def test_dev_start_endpoint_returns_202(
    client,
    db_session,
    monkeypatch,
):
    patch_dashboard_dependencies(
        monkeypatch
    )

    incident = seed_incident(
        db_session
    )

    response = client.post(
        (
            "/dev/api/incidents/"
            f"{incident.id}"
            "/analysis-runs"
        ),
        json={
            "provider": "mistral",
            "model_name": "mistral-small-latest",
        },
    )

    assert response.status_code == 202

    body = response.json()

    assert body["analysis_run_id"]
    assert body["status"] == "queued"
    assert (
        body["progress_stage"]
        == "queued"
    )


def test_dev_status_endpoint_returns_debug_data(
    client,
    db_session,
    monkeypatch,
):
    patch_dashboard_dependencies(
        monkeypatch
    )

    incident = seed_incident(
        db_session
    )

    start_response = client.post(
        (
            "/dev/api/incidents/"
            f"{incident.id}"
            "/analysis-runs"
        ),
        json={
            "provider": "mistral",
            "model_name": "mistral-small-latest",
        },
    )

    analysis_run_id = (
        start_response.json()[
            "analysis_run_id"
        ]
    )

    status_response = client.get(
        (
            "/dev/api/analysis-runs/"
            f"{analysis_run_id}"
        )
    )

    assert status_response.status_code == 200

    body = status_response.json()

    assert body["id"] == analysis_run_id
    assert body["status"] == "completed"
    assert body["model_name"] == (
        "mistral-small-latest"
    )
    assert body["provider"] == "mistral"
    assert body["report"] is not None
    assert (
        body["raw_model_output"]
        is not None
    )
    assert (
        body["validation_errors"]
        == []
    )
    assert (
        body["generation_metadata"][
            "prompt_eval_count"
        ]
        == 800
    )
    assert (
        body["retrieval_diagnostics"]
        ["chunks"][0]["chunk_id"]
        == "dashboard-runbook-1"
    )
    assert (
        body["progress_percent"]
        == 100
    )


def test_provider_and_model_are_saved_on_analysis_run(
    client,
    db_session,
    monkeypatch,
):
    patch_dashboard_dependencies(
        monkeypatch
    )

    incident = seed_incident(
        db_session
    )

    response = client.post(
        (
            "/dev/api/incidents/"
            f"{incident.id}"
            "/analysis-runs"
        ),
        json={
            "provider": "mistral",
            "model_name": (
                "mistral-small-latest"
            ),
        },
    )

    analysis_run_id = (
        response.json()[
            "analysis_run_id"
        ]
    )

    db_session.expire_all()

    analysis_run = db_session.get(
        AnalysisRun,
        analysis_run_id,
    )

    assert analysis_run is not None
    assert analysis_run.model_name == (
        "mistral-small-latest"
    )
    assert (
        analysis_run.run_config["llm"][
            "runtime"
        ]
        == "mistral"
    )


def test_dashboard_html_contains_observability_panels(
    client,
):
    response = client.get("/dev")

    assert response.status_code == 200

    html = response.text

    assert 'id="validatedOutput"' in html
    assert 'id="rawOutput"' in html
    assert 'id="issuesOutput"' in html
    assert 'id="retrievalOutput"' in html
    assert 'id="generationOutput"' in html
    assert 'id="progressBar"' in html
    assert 'id="providerSelect"' in html
    assert 'id="retrievalMetricCards"' in html
    assert (
        "/dev/api/analysis-runs/"
        in html
    )
    assert (
        "/dev/api/retrieval-eval"
        in html
    )


def test_mistral_models_require_api_key(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "mistral_api_key",
        None,
    )

    response = client.get(
        "/dev/api/llm-models"
        "?provider=mistral"
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "mistral",
        "configured": False,
        "default_model": (
            settings.mistral_model
        ),
        "models": [],
        "message": (
            "Set MISTRAL_API_KEY to use "
            "the Mistral provider."
        ),
    }


def test_mistral_models_lists_chat_models(
    client,
    monkeypatch,
):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {
                        "id": "mistral-small-latest",
                        "capabilities": {
                            "completion_chat": True,
                        },
                        "archived": False,
                    },
                    {
                        "id": "embed-only",
                        "capabilities": {
                            "completion_chat": False,
                        },
                        "archived": False,
                    },
                ]
            }

    def fake_get(
        url,
        *,
        headers,
        timeout,
    ):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        settings,
        "mistral_api_key",
        SecretStr("dashboard-key"),
    )
    monkeypatch.setattr(
        "app.dev_dashboard.router.httpx.get",
        fake_get,
    )

    response = client.get(
        "/dev/api/llm-models"
        "?provider=mistral"
    )

    assert response.status_code == 200
    assert response.json()["models"] == [
        "mistral-small-latest"
    ]
    assert captured["url"] == (
        "https://api.mistral.ai/v1/models"
    )
    assert captured["headers"] == {
        "Authorization": (
            "Bearer dashboard-key"
        )
    }
