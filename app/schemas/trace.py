from typing import Any

from pydantic import BaseModel


class AnalysisTraceResponse(BaseModel):
    """Investigation-trace view of an analysis run: evidence collection,
    per-node LLM call log, tool calls, and validation — everything the
    'Investigation trace' screen needs. Sourced from ``AnalysisRun`` columns
    that are already redacted before being written (see
    ``app.core.redaction``), so this is safe to expose directly.
    """

    analysis_run_id: str
    incident_id: str
    status: str
    progress_stage: str | None = None
    progress_message: str | None = None
    progress_percent: int = 0

    node_calls: int | None = None
    repairs_used: int | None = None
    investigation_rounds: int | None = None
    tool_results: list[dict[str, Any]] | None = None
    validation: dict[str, Any] | None = None

    generation_metadata: dict[str, Any] | None = None
    generation_attempts: list[dict[str, Any]] | None = None
    validation_errors: Any | None = None
    retrieval_diagnostics: Any | None = None
