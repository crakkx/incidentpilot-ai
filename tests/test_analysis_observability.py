from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app.llm.client import (
    InvalidRCAOutputError,
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
from app.services.analysis_service import (
    execute_analysis_run,
    prepare_analysis_run,
)


def fake_retrieval_results(
    *args: Any,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    service_name = kwargs.get(
        "service_name",
        "checkout-api",
    )

    return [
        {
            "chunk_id": "runbook-chunk-1",
            "document_id": "runbook-document-1",
            "document_title": (
                "Checkout Latency Runbook"
            ),
            "chunk_index": 0,
            "content": (
                "Inspect dependency latency, database "
                "pressure, cache misses, and recent "
                "deployments before assigning a cause."
            ),
            "score": 0.91,
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
        f"checkout-api-{suffix}"
    )

    service = Service(
        name=service_name,
        description="Checkout service",
        owner_team="checkout",
    )

    db_session.add(service)
    db_session.flush()

    started_at = datetime.utcnow()

    incident = Incident(
        title="Checkout latency increased",
        description=(
            "Checkout requests became slow "
            "during a dependency degradation."
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
                    "inventory dependency timeout"
                ),
                source="test",
                context={
                    "dependency": "inventory-api",
                    "status_code": 504,
                },
            ),
            Metric(
                service_name=service_name,
                timestamp=(
                    started_at
                    + timedelta(minutes=2)
                ),
                metric_name="latency_p95",
                value=2200,
                unit="ms",
            ),
            Deployment(
                service_id=service.id,
                service_name=service_name,
                version="v-test",
                environment="production",
                commit_sha="abc123",
                deployed_at=(
                    started_at
                    - timedelta(minutes=50)
                ),
            ),
        ]
    )

    db_session.commit()
    db_session.refresh(incident)

    return incident


def build_valid_report(
    evidence_payload: dict[str, Any],
) -> RCAReport:
    log_id = str(
        evidence_payload["logs"][0]["id"]
    )

    runbook_id = str(
        evidence_payload[
            "runbook_chunks"
        ][0]["id"]
    )

    return RCAReport(
        incident_summary=(
            "Checkout latency increased while "
            "the inventory dependency timed out."
        ),
        likely_root_cause=(
            "The immediate observed failure was "
            "an inventory dependency timeout. "
            "Further evidence is needed to prove "
            "the underlying trigger."
        ),
        evidence=[
            EvidenceItem(
                source_type="log",
                source_id=log_id,
                excerpt=(
                    "inventory dependency timeout"
                ),
                explanation=(
                    "The application directly "
                    "reported a timeout from the "
                    "inventory dependency."
                ),
            ),
            EvidenceItem(
                source_type="runbook",
                source_id=runbook_id,
                excerpt=(
                    "Inspect dependency latency "
                    "before assigning a cause."
                ),
                explanation=(
                    "The runbook recommends "
                    "collecting dependency evidence."
                ),
            ),
        ],
        recommended_actions=[
            "Inspect inventory dependency latency.",
            "Collect distributed traces.",
        ],
        confidence="medium",
        missing_information=[
            "Inventory service health data.",
        ],
    )


class SuccessfulDebugClient(RCAClient):
    def __init__(
        self,
        model_name: str = "qwen3:4b",
    ) -> None:
        self.model_name = model_name

    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        return build_valid_report(
            evidence_payload
        )

    def generate_rca_with_debug(
        self,
        evidence_payload: dict[str, Any],
        **kwargs: Any,
    ) -> RCAGenerationResult:
        report = self.generate_rca(
            evidence_payload
        )

        raw_output = (
            report.model_dump_json(
                indent=2
            )
        )

        metadata = {
            "done_reason": "stop",
            "prompt_eval_count": 1200,
            "eval_count": 180,
            "total_duration_ms": 9000.0,
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


class SchemaFailureClient(RCAClient):
    raw_output = (
        "{\n"
        '  "incident_summary": "Checkout is slow",\n'
        '  "likely_root_cause": "Unknown",\n'
        '  "evidence": [],\n'
        '  "recommended_actions": [\n'
        '    {"description": "Inspect traces"}\n'
        "  ],\n"
        '  "confidence": "medium",\n'
        '  "missing_information": []\n'
        "}"
    )

    validation_error = {
        "type": "string_type",
        "loc": [
            "recommended_actions",
            0,
        ],
        "msg": (
            "Input should be a valid string"
        ),
        "input": {
            "description": "Inspect traces",
        },
    }

    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        raise self._error()

    def generate_rca_with_debug(
        self,
        evidence_payload: dict[str, Any],
        **kwargs: Any,
    ) -> RCAGenerationResult:
        raise self._error()

    def _error(
        self,
    ) -> InvalidRCAOutputError:
        metadata = {
            "done_reason": "stop",
            "prompt_eval_count": 1000,
            "eval_count": 80,
            "total_duration_ms": 5000.0,
        }

        attempt = {
            "attempt": 1,
            "raw_output": self.raw_output,
            "metadata": metadata,
            "validation_errors": [
                self.validation_error
            ],
        }

        return InvalidRCAOutputError(
            "Invalid structured RCA output.",
            debug={
                "attempts": [attempt],
                "final_raw_output": (
                    self.raw_output
                ),
                "final_metadata": metadata,
                "final_validation_errors": [
                    self.validation_error
                ],
            },
        )


class InventedEvidenceClient(RCAClient):
    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        return RCAReport(
            incident_summary=(
                "Checkout latency increased."
            ),
            likely_root_cause=(
                "An inventory dependency "
                "timeout is suspected."
            ),
            evidence=[
                EvidenceItem(
                    source_type="log",
                    source_id=(
                        "invented-log-id"
                    ),
                    excerpt=(
                        "inventory dependency "
                        "timeout"
                    ),
                    explanation=(
                        "This ID was not supplied."
                    ),
                )
            ],
            recommended_actions=[
                "Inspect dependency latency."
            ],
            confidence="low",
            missing_information=[],
        )

    def generate_rca_with_debug(
        self,
        evidence_payload: dict[str, Any],
        **kwargs: Any,
    ) -> RCAGenerationResult:
        report = self.generate_rca(
            evidence_payload
        )

        raw_output = (
            report.model_dump_json(
                indent=2
            )
        )

        return RCAGenerationResult(
            report=report,
            raw_output=raw_output,
            metadata={
                "done_reason": "stop",
                "prompt_eval_count": 900,
                "eval_count": 90,
                "total_duration_ms": 4500.0,
            },
            attempts=[
                {
                    "attempt": 1,
                    "raw_output": raw_output,
                    "metadata": {},
                    "validation_errors": [],
                }
            ],
        )


def execute_with_client(
    db_session,
    incident: Incident,
    client: RCAClient,
):
    analysis_run = prepare_analysis_run(
        db=db_session,
        incident_id=incident.id,
        model_name="qwen3:4b",
    )

    return execute_analysis_run(
        db=db_session,
        analysis_run_id=analysis_run.id,
        llm_client=client,
        raise_http_errors=False,
    )


def test_success_saves_raw_and_validated_output(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.evidence_service."
        "retrieve_document_chunks",
        fake_retrieval_results,
    )

    incident = seed_incident(
        db_session
    )

    analysis_run, report = execute_with_client(
        db_session,
        incident,
        SuccessfulDebugClient(),
    )

    assert report is not None
    assert analysis_run.status == "completed"

    db_session.expire_all()

    persisted = db_session.get(
        AnalysisRun,
        analysis_run.id,
    )

    assert persisted is not None
    assert persisted.report is not None
    assert (
        persisted.raw_model_output
        is not None
    )
    assert (
        "incident_summary"
        in persisted.raw_model_output
    )
    assert (
        persisted.generation_metadata[
            "prompt_eval_count"
        ]
        == 1200
    )


def test_schema_failure_saves_raw_model_output(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.evidence_service."
        "retrieve_document_chunks",
        fake_retrieval_results,
    )

    incident = seed_incident(
        db_session
    )

    analysis_run, report = execute_with_client(
        db_session,
        incident,
        SchemaFailureClient(),
    )

    assert report is None
    assert analysis_run.status == "failed"
    assert (
        analysis_run.failure_type
        == "schema_validation"
    )
    assert (
        analysis_run.raw_model_output
        == SchemaFailureClient.raw_output
    )


def test_schema_failure_saves_pydantic_errors(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.evidence_service."
        "retrieve_document_chunks",
        fake_retrieval_results,
    )

    incident = seed_incident(
        db_session
    )

    analysis_run, _ = execute_with_client(
        db_session,
        incident,
        SchemaFailureClient(),
    )

    assert analysis_run.validation_errors
    assert (
        analysis_run.validation_errors[0][
            "loc"
        ]
        == [
            "recommended_actions",
            0,
        ]
    )
    assert (
        analysis_run.validation_errors[0][
            "type"
        ]
        == "string_type"
    )
    assert (
        analysis_run.generation_attempts[0][
            "validation_errors"
        ]
    )


def test_invented_evidence_saves_exact_issue_path(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.evidence_service."
        "retrieve_document_chunks",
        fake_retrieval_results,
    )

    incident = seed_incident(
        db_session
    )

    analysis_run, report = execute_with_client(
        db_session,
        incident,
        InventedEvidenceClient(),
    )

    assert report is None
    assert analysis_run.status == "failed"
    assert (
        analysis_run.failure_type
        == "invented_evidence"
    )

    issue = (
        analysis_run.validation_errors[0]
    )

    assert issue["type"] == (
        "invented_evidence"
    )

    assert issue["loc"] == [
        "evidence",
        0,
        "source_id",
    ]

    assert issue["input"] == (
        "invented-log-id"
    )

    assert issue["allowed_source_ids"]


def test_retrieval_diagnostics_are_persisted(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.evidence_service."
        "retrieve_document_chunks",
        fake_retrieval_results,
    )

    incident = seed_incident(
        db_session
    )

    analysis_run, _ = execute_with_client(
        db_session,
        incident,
        SuccessfulDebugClient(),
    )

    diagnostics = (
        analysis_run.retrieval_diagnostics
    )

    assert diagnostics is not None
    assert diagnostics[
        "top_k_requested"
    ] >= 1
    assert diagnostics[
        "returned_count"
    ] == 1
    assert diagnostics["latency_ms"] >= 0
    assert diagnostics["chunks"][0][
        "chunk_id"
    ] == "runbook-chunk-1"
    assert diagnostics["chunks"][0][
        "score"
    ] == 0.91


def test_analysis_progress_reaches_completed(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.evidence_service."
        "retrieve_document_chunks",
        fake_retrieval_results,
    )

    incident = seed_incident(
        db_session
    )

    analysis_run, _ = execute_with_client(
        db_session,
        incident,
        SuccessfulDebugClient(),
    )

    assert analysis_run.status == "completed"
    assert (
        analysis_run.progress_stage
        == "completed"
    )
    assert (
        analysis_run.progress_percent
        == 100
    )
    assert (
        "success"
        in analysis_run
        .progress_message
        .lower()
    )


def test_failed_analysis_progress_reaches_failed(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.evidence_service."
        "retrieve_document_chunks",
        fake_retrieval_results,
    )

    incident = seed_incident(
        db_session
    )

    analysis_run, _ = execute_with_client(
        db_session,
        incident,
        SchemaFailureClient(),
    )

    assert analysis_run.status == "failed"
    assert (
        analysis_run.progress_stage
        == "failed"
    )
    assert (
        analysis_run.failure_type
        == "schema_validation"
    )
    assert (
        "schema"
        in analysis_run
        .progress_message
        .lower()
    )