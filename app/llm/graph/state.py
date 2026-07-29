from typing import Any, TypedDict

from app.llm.graph.schemas import (
    ActionResult,
    ContradictionResult,
    ExtractionResult,
    SynthesisResult,
    ValidationResult,
)


class GraphState(TypedDict, total=False):
    """Shared state threaded through every node of the RCA graph.

    ``repairs_used`` is a run-wide counter (not per-node) so a single
    stubborn node cannot exhaust the whole schema-repair budget by itself.
    ``call_log`` records every model call (including failed attempts that
    triggered a repair) for debugging/attempt-history parity with the
    single-call client's ``RCAGenerationResult.attempts``.
    """

    evidence_payload: dict[str, Any]
    extraction: ExtractionResult
    contradiction: ContradictionResult
    synthesis: SynthesisResult
    validation: ValidationResult
    validation_debug: dict[str, Any]
    actions: ActionResult
    repairs_used: int
    call_log: list[dict[str, Any]]
