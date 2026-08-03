"""Agentic investigation nodes for the Phase 5 RCA loop.

Two new node functions are added to the graph between ``extract`` and
``cross_validate``:

1. ``run_hypothesis_node``  — asks the model for its initial hypothesis
   and a list of evidence gaps to fill.
2. ``run_gap_tool_node``    — picks one gap from the queue, deterministically
   selects the best tool (no extra LLM call), fires it, and appends the
   result to both ``tool_results`` and the live ``evidence_payload`` so that
   downstream nodes (synthesis, etc.) see the enriched evidence.

The loop is capped at ``settings.rca_agent_max_rounds`` (default 3) via the
``_should_investigate`` router in ``pipeline.py``.

Prompt for the hypothesis node
--------------------------------
The system prompt follows the same grounding rules as the other nodes — the
model must not invent information not present in the supplied extraction.

Tool selection strategy
------------------------
Deterministic keyword matching keeps tool selection free of extra LLM calls::

    keywords containing "log" / "error" / "warn"  → fetch_logs
    keywords containing "metric" / "cpu" / "mem"  → fetch_metrics
    everything else                                → fetch_runbook_chunks
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.llm.graph.schemas import HypothesisResult
from app.llm.graph.state import GraphState
from app.llm.graph.nodes import _compact, _invoke_node, _record_call
from app.llm.graph.tools import fetch_logs, fetch_metrics, fetch_runbook_chunks, fetch_web_search
from app.llm.tracing import mlflow_trace

# ── system prompt ────────────────────────────────────────────────────────────

HYPOTHESIS_SYSTEM_PROMPT = """
You are the hypothesis stage of an incident root-cause-analysis pipeline.
You have already extracted anomalies from the raw evidence. Your job is to:

1. State your best current hypothesis about the root cause in plain English,
   grounded ONLY in the extracted anomalies and evidence supplied.
2. List the specific pieces of additional information that would help you
   confirm or refute this hypothesis (gap_queries). Be concrete — name the
   service, metric, or runbook section you want to look up.
3. Rate your confidence so far ('low', 'medium', or 'high') based on the
   evidence at hand, NOT on what you hope to find.

Strict grounding rules:
- Do not invent service names, metrics, or log lines not present in the evidence.
- If the existing evidence is already clear, leave gap_queries empty.
- Never return Markdown or text outside the required JSON object.
""".strip()


# ── keyword → tool mapping ───────────────────────────────────────────────────

_LOG_KEYWORDS = {"log", "error", "warn", "exception", "trace", "stderr", "stdout"}
_METRIC_KEYWORDS = {"metric", "cpu", "mem", "memory", "latency", "request", "throughput", "rps", "p99", "p95"}
_WEB_KEYWORDS = {"web", "search", "docs", "google", "internet", "public", "error_code", "cve", "github", "stack", "overflow", "external"}


def _select_tool(gap_query: str) -> str:
    """Deterministically pick a tool name from a gap query string.

    Returns one of: 'fetch_logs', 'fetch_metrics', 'fetch_runbook_chunks', 'fetch_web_search'.
    """
    q = gap_query.lower()
    tokens = set(q.split())

    if tokens & _LOG_KEYWORDS:
        return "fetch_logs"
    if tokens & _METRIC_KEYWORDS:
        return "fetch_metrics"
    if tokens & _WEB_KEYWORDS:
        return "fetch_web_search"
    return "fetch_runbook_chunks"



def _extract_service_name(gap_query: str, evidence_payload: dict[str, Any]) -> str:
    """Best-effort extraction of a service name from the gap query.

    Falls back to the incident's service_name if nothing is found.
    """
    # Use the incident service_name as the default
    fallback = (
        evidence_payload.get("incident", {}).get("service_name")
        or evidence_payload.get("incident", {}).get("service", "unknown")
    )

    # Try to find a quoted or capitalised service name in the query
    words = gap_query.split()
    for word in words:
        word_clean = word.strip("'\",.")
        if "-" in word_clean and len(word_clean) > 3:
            return word_clean

    return fallback


def _extract_keywords(gap_query: str) -> list[str]:
    """Pull likely keyword filters out of the gap query."""
    q_lower = gap_query.lower()
    found = []
    for kw in ["error", "warn", "timeout", "fail", "exception", "crash", "oom"]:
        if kw in q_lower:
            found.append(kw)
    return found or None  # type: ignore[return-value]


# ── nodes ────────────────────────────────────────────────────────────────────

@mlflow_trace(span_type="CHAIN")
def run_hypothesis_node(
    state: GraphState,
    *,
    model_name: str,
    max_repairs: int,
) -> GraphState:
    """Form an initial hypothesis and identify evidence gaps.

    Reads ``extraction`` from state. Writes ``hypothesis`` and ``gap_queries``.
    Also initialises ``tool_results`` and ``investigation_rounds`` to their
    zero values if not already present.
    """
    from app.llm.graph.schemas import ExtractionResult

    extraction: ExtractionResult = state["extraction"]

    payload = {
        "log_anomalies": extraction.log_anomalies,
        "metric_anomalies": extraction.metric_anomalies,
        "deployment_events": extraction.deployment_events,
        "entity_glossary": extraction.entity_glossary,
        "evidence_count": len(extraction.evidence),
    }

    user_prompt = (
        "Based on the extracted anomalies below, form your initial hypothesis "
        "and identify any evidence gaps.\n\n"
        "Return only JSON matching this schema:\n"
        f"{_compact(HypothesisResult.model_json_schema())}\n\n"
        f"Extracted anomalies:\n{_compact(payload)}"
    )

    hypothesis: HypothesisResult = _invoke_node(
        state=state,
        node_name="hypothesis",
        system_prompt=HYPOTHESIS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_model=HypothesisResult,
        schema_name="rca_hypothesis",
        model_name=model_name,
        max_tokens=800,
        max_repairs=max_repairs,
    )

    state["hypothesis"] = hypothesis
    state["gap_queries"] = list(hypothesis.gap_queries)  # mutable copy
    state.setdefault("tool_results", [])
    state.setdefault("investigation_rounds", 0)

    return state


@mlflow_trace(span_type="CHAIN")
def run_gap_tool_node(
    state: GraphState,
    *,
    model_name: str,
    max_repairs: int,  # kept for API parity, not used here
) -> GraphState:
    """Consume one gap query, call the appropriate tool, and append results.

    Deterministically selects the tool (no LLM call), fires it, and:
    - Appends the raw result to ``state["tool_results"]``.
    - Merges the result into the live ``evidence_payload`` so downstream
      nodes (synthesis, cross_validate) see the enriched evidence.
    - Removes the consumed gap from ``state["gap_queries"]``.
    - Increments ``state["investigation_rounds"]``.
    """
    gap_queries: list[str] = state.get("gap_queries", [])
    if not gap_queries:
        return state

    gap = gap_queries[0]
    evidence_payload: dict[str, Any] = state["evidence_payload"]

    tool_name = _select_tool(gap)
    service_name = _extract_service_name(gap, evidence_payload)

    result: list[dict[str, Any]] = []

    if tool_name == "fetch_logs":
        keywords = _extract_keywords(gap)
        result = fetch_logs(
            service_name=service_name,
            time_range_minutes=60,
            keywords=keywords,
            evidence_payload=evidence_payload,
        )
        # Merge into evidence_payload so synthesis sees the new logs
        existing_logs = evidence_payload.get("logs", [])
        seen_msgs = {json.dumps(lg, default=str) for lg in existing_logs}
        new_logs = [lg for lg in result if json.dumps(lg, default=str) not in seen_msgs]
        evidence_payload["logs"] = existing_logs + new_logs

    elif tool_name == "fetch_metrics":
        result = fetch_metrics(
            service_name=service_name,
            time_range_minutes=60,
            evidence_payload=evidence_payload,
        )
        existing_metrics = evidence_payload.get("metrics", [])
        seen = {json.dumps(m, default=str) for m in existing_metrics}
        new_metrics = [m for m in result if json.dumps(m, default=str) not in seen]
        evidence_payload["metrics"] = existing_metrics + new_metrics

    elif tool_name == "fetch_web_search":
        result = fetch_web_search(
            query=gap,
            max_results=3,
            evidence_payload=evidence_payload,
        )
        existing_web = evidence_payload.get("web_search_chunks", [])
        seen = {c.get("content", "") for c in existing_web}
        new_web = [c for c in result if c.get("content", "") not in seen]
        evidence_payload["web_search_chunks"] = existing_web + new_web

    else:  # fetch_runbook_chunks
        result = fetch_runbook_chunks(
            service_name=service_name,
            query=gap,
            top_k=3,
            evidence_payload=evidence_payload,
        )
        existing_chunks = evidence_payload.get("runbook_chunks", [])
        seen = {c.get("content", "") for c in existing_chunks}
        new_chunks = [c for c in result if c.get("content", "") not in seen]
        evidence_payload["runbook_chunks"] = existing_chunks + new_chunks

    state["tool_results"] = state.get("tool_results", []) + [
        {"gap": gap, "tool": tool_name, "service": service_name, "result_count": len(result)}
    ]
    state["gap_queries"] = gap_queries[1:]  # pop the consumed query
    state["investigation_rounds"] = state.get("investigation_rounds", 0) + 1
    state["evidence_payload"] = evidence_payload  # write back enriched payload

    _record_call(
        state,
        node_name="gap_tool",
        raw_output=json.dumps({"tool": tool_name, "gap": gap, "results": len(result)}),
        metadata={"tool": tool_name, "service": service_name, "result_count": len(result)},
    )

    return state
