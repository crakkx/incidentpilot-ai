import pytest

from app.evals.retrieval_eval import (
    CaseResult,
    calculate_metrics,
    find_first_relevant,
    is_relevant_chunk,
)


def make_chunk(
    service_name: str,
    content: str,
    document_type: str = "runbook",
) -> dict:
    return {
        "chunk_id": "chunk-1",
        "document_id": "document-1",
        "document_title": "Test Runbook",
        "chunk_index": 0,
        "content": content,
        "score": 0.8,
        "metadata": {
            "service_name": service_name,
            "document_type": document_type,
            "severity": "high",
        },
    }


def test_relevant_chunk_requires_metadata_and_keyword():
    case = {
        "expected_service": "payments-api",
        "expected_document_type": "runbook",
        "expected_chunk_keywords": [
            "connection pool",
            "database timeout",
        ],
        "minimum_keyword_matches": 1,
    }

    correct_chunk = make_chunk(
        service_name="payments-api",
        content="Check the database connection pool for exhaustion.",
    )

    wrong_service_chunk = make_chunk(
        service_name="checkout-api",
        content="Check the database connection pool for exhaustion.",
    )

    wrong_content_chunk = make_chunk(
        service_name="payments-api",
        content="Check the external provider status page.",
    )

    assert is_relevant_chunk(correct_chunk, case) is True
    assert is_relevant_chunk(wrong_service_chunk, case) is False
    assert is_relevant_chunk(wrong_content_chunk, case) is False


def test_find_first_relevant_returns_correct_rank():
    case = {
        "expected_service": "payments-api",
        "expected_document_type": "runbook",
        "expected_chunk_keywords": ["connection pool"],
        "minimum_keyword_matches": 1,
    }

    chunks = [
        make_chunk(
            service_name="payments-api",
            content="Check the external provider status.",
        ),
        make_chunk(
            service_name="payments-api",
            content="Inspect database connection pool usage.",
        ),
    ]

    rank, chunk, matched_keywords = find_first_relevant(
        chunks=chunks,
        case=case,
    )

    assert rank == 2
    assert chunk is not None
    assert matched_keywords == ["connection pool"]


def test_calculate_metrics():
    results = [
        CaseResult(
            case_id="case-1",
            query="query 1",
            first_relevant_rank=1,
            latency_ms=10,
            returned_chunks=5,
            top_score=0.9,
            matched_keywords=["timeout"],
            matched_document_title="Document 1",
        ),
        CaseResult(
            case_id="case-2",
            query="query 2",
            first_relevant_rank=2,
            latency_ms=20,
            returned_chunks=5,
            top_score=0.8,
            matched_keywords=["latency"],
            matched_document_title="Document 2",
        ),
        CaseResult(
            case_id="case-3",
            query="query 3",
            first_relevant_rank=None,
            latency_ms=30,
            returned_chunks=5,
            top_score=0.7,
            matched_keywords=[],
            matched_document_title=None,
        ),
        CaseResult(
            case_id="case-4",
            query="query 4",
            first_relevant_rank=5,
            latency_ms=40,
            returned_chunks=5,
            top_score=0.6,
            matched_keywords=["rollback"],
            matched_document_title="Document 4",
        ),
    ]

    metrics = calculate_metrics(results)

    assert metrics["query_count"] == 4
    assert metrics["hit_at_1"] == pytest.approx(0.25)
    assert metrics["hit_at_3"] == pytest.approx(0.50)
    assert metrics["hit_at_5"] == pytest.approx(0.75)
    assert metrics["mrr"] == pytest.approx(0.425)
    assert metrics["avg_latency_ms"] == pytest.approx(25.0)
