from typing import Any, TypedDict

from app.llm.graph.schemas import (
    ActionResult,
    ContradictionResult,
    ExtractionResult,
    HypothesisResult,
    SynthesisResult,
    ValidationResult,
)


class GraphState(TypedDict, total=False):
    """Shared state threaded through every node of the RCA graph.

    Original pipeline fields
    ------------------------
    ``repairs_used`` is a run-wide counter (not per-node) so a single
    stubborn node cannot exhaust the whole schema-repair budget by itself.
    ``call_log`` records every model call (including failed attempts that
    triggered a repair) for debugging/attempt-history parity with the
    single-call client's ``RCAGenerationResult.attempts``.

    Agentic investigation fields (Phase 5)
    ---------------------------------------
    ``hypothesis``           – The agent's current working hypothesis after
                               the initial extraction pass.
    ``gap_queries``          – Ordered list of evidence gaps the agent wants
                               to fill via tool calls.  Each entry is a plain
                               English description (e.g. "Fetch CPU metric for
                               payment-service in the last 30 minutes").
    ``tool_results``         – Accumulated results returned by tool calls this
                               run, appended to the evidence_payload before
                               synthesis.
    ``investigation_rounds`` – How many tool-call rounds have fired so far.
                               Compared against ``settings.rca_agent_max_rounds``
                               to enforce the loop cap.
    """

    # ── core evidence ────────────────────────────────────────────────────────
    evidence_payload: dict[str, Any]

    # ── pipeline node outputs ────────────────────────────────────────────────
    extraction: ExtractionResult
    contradiction: ContradictionResult
    synthesis: SynthesisResult
    validation: ValidationResult
    validation_debug: dict[str, Any]
    actions: ActionResult

    # ── schema-repair budget ─────────────────────────────────────────────────
    repairs_used: int
    call_log: list[dict[str, Any]]

    # ── agentic investigation (Phase 5) ──────────────────────────────────────
    hypothesis: HypothesisResult
    gap_queries: list[str]
    tool_results: list[dict[str, Any]]
    investigation_rounds: int
