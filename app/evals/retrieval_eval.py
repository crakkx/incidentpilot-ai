from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CASES_PATH = PROJECT_ROOT / "data" / "retrieval_eval_cases.json"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_README_PATH = PROJECT_ROOT / "README.md"

DEFAULT_API_URL = os.getenv(
    "RETRIEVE_URL",
    "http://localhost:8000/retrieve",
)

README_START_MARKER = "<!-- RETRIEVAL_EVAL_START -->"
README_END_MARKER = "<!-- RETRIEVAL_EVAL_END -->"


@dataclass
class CaseResult:
    case_id: str
    query: str
    first_relevant_rank: int | None
    latency_ms: float
    returned_chunks: int
    top_score: float | None
    matched_keywords: list[str]
    matched_document_title: str | None


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Evaluation file does not exist: {path}")

    cases = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation file must contain a non-empty JSON list.")

    for index, case in enumerate(cases, start=1):
        if not case.get("query"):
            raise ValueError(f"Evaluation case {index} is missing 'query'.")

        if not case.get("expected_chunk_keywords"):
            raise ValueError(
                f"Evaluation case {index} is missing "
                "'expected_chunk_keywords'."
            )

    return cases


def build_retrieve_payload(
    case: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": case["query"],
        "top_k": top_k,
    }

    # The expected metadata is also passed to the API as a retrieval filter.
    if case.get("expected_service"):
        payload["service_name"] = case["expected_service"]

    if case.get("expected_document_type"):
        payload["document_type"] = case["expected_document_type"]

    if case.get("expected_severity"):
        payload["severity"] = case["expected_severity"]

    return payload


def call_retrieve(
    api_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> tuple[dict[str, Any], float]:
    request = Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started_at = time.perf_counter()

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")

        raise RuntimeError(
            f"Retrieval API returned HTTP {exc.code}: {error_body}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"Could not reach retrieval API at {api_url}: {exc}"
        ) from exc

    latency_ms = (time.perf_counter() - started_at) * 1000

    result = json.loads(response_body)
    chunks = result.get("chunks")

    if not isinstance(chunks, list):
        raise ValueError(
            "Retrieval response must contain a list named 'chunks'. "
            f"Received: {result}"
        )

    return result, latency_ms


def matched_keywords_for_chunk(
    chunk: dict[str, Any],
    case: dict[str, Any],
) -> list[str]:
    content = str(chunk.get("content", "")).lower()

    return [
        keyword
        for keyword in case["expected_chunk_keywords"]
        if keyword.lower() in content
    ]


def chunk_metadata_matches(
    chunk: dict[str, Any],
    case: dict[str, Any],
) -> bool:
    metadata = chunk.get("metadata") or {}

    expected_service = case.get("expected_service")
    expected_document_type = case.get("expected_document_type")
    expected_severity = case.get("expected_severity")

    if expected_service:
        actual_service = str(metadata.get("service_name", "")).lower()

        if actual_service != expected_service.lower():
            return False

    if expected_document_type:
        actual_document_type = str(
            metadata.get("document_type", "")
        ).lower()

        if actual_document_type != expected_document_type.lower():
            return False

    if expected_severity:
        actual_severity = str(metadata.get("severity", "")).lower()

        if actual_severity != expected_severity.lower():
            return False

    return True


def is_relevant_chunk(
    chunk: dict[str, Any],
    case: dict[str, Any],
) -> bool:
    if not chunk_metadata_matches(chunk, case):
        return False

    expected_keywords = case.get("expected_chunk_keywords", [])

    if not expected_keywords:
        return True

    minimum_matches = int(case.get("minimum_keyword_matches", 1))
    matched_keywords = matched_keywords_for_chunk(chunk, case)

    return len(matched_keywords) >= minimum_matches


def find_first_relevant(
    chunks: list[dict[str, Any]],
    case: dict[str, Any],
) -> tuple[int | None, dict[str, Any] | None, list[str]]:
    for rank, chunk in enumerate(chunks, start=1):
        if is_relevant_chunk(chunk, case):
            return (
                rank,
                chunk,
                matched_keywords_for_chunk(chunk, case),
            )

    return None, None, []


def evaluate_case(
    case: dict[str, Any],
    api_url: str,
    top_k: int,
    timeout_seconds: float,
) -> CaseResult:
    payload = build_retrieve_payload(case, top_k)

    response, latency_ms = call_retrieve(
        api_url=api_url,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )

    chunks = response["chunks"]

    rank, relevant_chunk, matched_keywords = find_first_relevant(
        chunks=chunks,
        case=case,
    )

    top_score = None

    if chunks and chunks[0].get("score") is not None:
        top_score = float(chunks[0]["score"])

    matched_document_title = None

    if relevant_chunk:
        matched_document_title = relevant_chunk.get("document_title")

    return CaseResult(
        case_id=str(case.get("id", case["query"])),
        query=case["query"],
        first_relevant_rank=rank,
        latency_ms=latency_ms,
        returned_chunks=len(chunks),
        top_score=top_score,
        matched_keywords=matched_keywords,
        matched_document_title=matched_document_title,
    )


def calculate_metrics(
    results: list[CaseResult],
) -> dict[str, float | int]:
    if not results:
        raise ValueError("Cannot calculate metrics without results.")

    total_queries = len(results)

    hit_at_1 = sum(
        result.first_relevant_rank is not None
        and result.first_relevant_rank <= 1
        for result in results
    ) / total_queries

    hit_at_3 = sum(
        result.first_relevant_rank is not None
        and result.first_relevant_rank <= 3
        for result in results
    ) / total_queries

    hit_at_5 = sum(
        result.first_relevant_rank is not None
        and result.first_relevant_rank <= 5
        for result in results
    ) / total_queries

    reciprocal_ranks = [
        1.0 / result.first_relevant_rank
        if result.first_relevant_rank is not None
        else 0.0
        for result in results
    ]

    return {
        "query_count": total_queries,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "mrr": statistics.fmean(reciprocal_ranks),
        "avg_latency_ms": statistics.fmean(
            result.latency_ms
            for result in results
        ),
    }


def print_case_result(result: CaseResult) -> None:
    if result.first_relevant_rank is None:
        status = "MISS"
        rank_text = "no relevant chunk"
    else:
        status = "PASS"
        rank_text = f"relevant rank={result.first_relevant_rank}"

    score_text = (
        f"{result.top_score:.4f}"
        if result.top_score is not None
        else "n/a"
    )

    print(
        f"[{status}] {result.case_id} | "
        f"{rank_text} | "
        f"latency={result.latency_ms:.2f} ms | "
        f"top_score={score_text}"
    )
    print(f"       query: {result.query}")

    if result.matched_document_title:
        print(
            "       matched document: "
            f"{result.matched_document_title}"
        )

    if result.matched_keywords:
        print(
            "       matched keywords: "
            f"{', '.join(result.matched_keywords)}"
        )


def print_metrics(metrics: dict[str, float | int]) -> None:
    print()
    print("=" * 72)
    print("Retrieval evaluation summary")
    print("=" * 72)
    print(f"Queries:          {metrics['query_count']}")
    print(f"Hit@1:            {metrics['hit_at_1']:.2%}")
    print(f"Hit@3:            {metrics['hit_at_3']:.2%}")
    print(f"Hit@5:            {metrics['hit_at_5']:.2%}")
    print(f"MRR:              {metrics['mrr']:.4f}")
    print(f"Average latency:  {metrics['avg_latency_ms']:.2f} ms")


def render_markdown_report(
    generated_at: str,
    metrics: dict[str, float | int],
) -> str:
    return f"""# Retrieval Evaluation Report

Generated: `{generated_at}`

Embedding model: `{settings.embedding_model_name}`

Evaluation queries: `{metrics["query_count"]}`

| Metric | Result |
|---|---:|
| Hit@1 | {metrics["hit_at_1"]:.2%} |
| Hit@3 | {metrics["hit_at_3"]:.2%} |
| Hit@5 | {metrics["hit_at_5"]:.2%} |
| MRR | {metrics["mrr"]:.4f} |
| Average latency | {metrics["avg_latency_ms"]:.2f} ms |

These results use the local seeded runbook dataset and rule-based
keyword/metadata relevance labels. They are not a production benchmark.
"""


def render_readme_section(
    generated_at: str,
    metrics: dict[str, float | int],
) -> str:
    return f"""{README_START_MARKER}
## Current retrieval evaluation

Last evaluated: `{generated_at}`

Embedding model: `{settings.embedding_model_name}`

| Metric | Current result |
|---|---:|
| Hit@1 | {metrics["hit_at_1"]:.2%} |
| Hit@3 | {metrics["hit_at_3"]:.2%} |
| Hit@5 | {metrics["hit_at_5"]:.2%} |
| MRR | {metrics["mrr"]:.4f} |
| Average latency | {metrics["avg_latency_ms"]:.2f} ms |
| Evaluation queries | {metrics["query_count"]} |

The evaluation uses seeded IncidentPilot runbooks with metadata and
keyword-based relevance labels. Detailed results are written to
`reports/retrieval_eval_latest.json`.
{README_END_MARKER}"""


def write_reports(
    report: dict[str, Any],
    reports_dir: Path,
) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "retrieval_eval_latest.json"
    markdown_path = reports_dir / "retrieval_eval_latest.md"

    json_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    markdown_path.write_text(
        render_markdown_report(
            generated_at=report["generated_at"],
            metrics=report["metrics"],
        ),
        encoding="utf-8",
    )

    return json_path, markdown_path


def update_readme(
    readme_path: Path,
    generated_at: str,
    metrics: dict[str, float | int],
) -> None:
    section = render_readme_section(
        generated_at=generated_at,
        metrics=metrics,
    )

    if readme_path.exists():
        current_text = readme_path.read_text(encoding="utf-8")
    else:
        current_text = "# IncidentPilot AI\n"

    if (
        README_START_MARKER in current_text
        and README_END_MARKER in current_text
    ):
        start_index = current_text.index(README_START_MARKER)
        end_index = (
            current_text.index(README_END_MARKER)
            + len(README_END_MARKER)
        )

        updated_text = (
            current_text[:start_index]
            + section
            + current_text[end_index:]
        )
    else:
        updated_text = current_text.rstrip() + "\n\n" + section + "\n"

    readme_path.write_text(updated_text, encoding="utf-8")


def run_evals(
    api_url: str,
    cases_path: Path,
    top_k: int = 5,
    timeout_seconds: float = 180,
    warm_up: bool = True,
) -> dict[str, Any]:
    if top_k < 5:
        raise ValueError(
            "top_k must be at least 5 to calculate Hit@5."
        )

    cases = load_cases(cases_path)

    if warm_up:
        print("Warming up the embedding model and retrieval endpoint...")

        warmup_payload = build_retrieve_payload(
            case=cases[0],
            top_k=1,
        )

        call_retrieve(
            api_url=api_url,
            payload=warmup_payload,
            timeout_seconds=timeout_seconds,
        )

        print("Warm-up complete.")
        print()

    results: list[CaseResult] = []

    for case in cases:
        result = evaluate_case(
            case=case,
            api_url=api_url,
            top_k=top_k,
            timeout_seconds=timeout_seconds,
        )

        results.append(result)
        print_case_result(result)

    metrics = calculate_metrics(results)
    print_metrics(metrics)

    generated_at = datetime.now(timezone.utc).isoformat()

    return {
        "generated_at": generated_at,
        "api_url": api_url,
        "embedding_model": settings.embedding_model_name,
        "top_k": top_k,
        "cases_path": str(cases_path),
        "metrics": metrics,
        "results": [
            asdict(result)
            for result in results
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate IncidentPilot document retrieval."
    )

    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Full URL of the /retrieve endpoint.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help="Path to the retrieval evaluation JSON file.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve. Must be at least 5.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--skip-warmup",
        action="store_true",
        help="Include no separate model warm-up request.",
    )
    parser.add_argument(
        "--update-readme",
        action="store_true",
        help="Write the current metrics into README.md.",
    )

    args = parser.parse_args()

    report = run_evals(
        api_url=args.api_url,
        cases_path=args.cases,
        top_k=args.top_k,
        timeout_seconds=args.timeout,
        warm_up=not args.skip_warmup,
    )

    json_path, markdown_path = write_reports(
        report=report,
        reports_dir=DEFAULT_REPORTS_DIR,
    )

    print()
    print(f"JSON report:     {json_path}")
    print(f"Markdown report: {markdown_path}")

    if args.update_readme:
        update_readme(
            readme_path=DEFAULT_README_PATH,
            generated_at=report["generated_at"],
            metrics=report["metrics"],
        )

        print(f"README updated:  {DEFAULT_README_PATH}")


if __name__ == "__main__":
    main()
