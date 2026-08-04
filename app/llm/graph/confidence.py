"""Deterministic confidence calibration for the RCA graph pipeline.

The single-call prompt asks the model to self-report ``confidence``, which
empirically erodes under noise: a large volume of unrelated background
errors pushes the model toward "low" even when the actual causal chain is
well supported. This module replaces that self-report with a rule computed
from structured signals the earlier nodes already produced, so noise
volume alone can no longer move the number.
"""

from app.llm.graph.schemas import (
    ContradictionResult,
    ExtractionResult,
    SynthesisResult,
)

_DEPLOYMENT_TRIGGER_KEYWORDS = ("deploy", "release", "rollout")


def calibrate_confidence(
    *,
    extraction: ExtractionResult,
    contradiction: ContradictionResult,
    synthesis: SynthesisResult,
) -> str:
    root_cause = synthesis.root_cause

    if root_cause is None:
        return "low"

    if synthesis.contradiction_conflicts_with_mechanism:
        return "low"

    if root_cause.causal_strength in ("unknown", "refuted"):
        return "low"

    evidence_by_id = {
        item.source_id: item for item in extraction.evidence
    }

    supporting_source_types = {
        evidence_by_id[source_id].source_type
        for source_id in synthesis.supporting_evidence_ids
        if source_id in evidence_by_id
    }

    trigger_claims_deployment = bool(
        root_cause.suspected_trigger
        and any(
            keyword in root_cause.suspected_trigger.lower()
            for keyword in _DEPLOYMENT_TRIGGER_KEYWORDS
        )
    )

    trigger_unsupported = (
        trigger_claims_deployment
        and root_cause.causal_strength in ("confirmed", "supported")
        and "deployment" not in supporting_source_types
    )

    if trigger_unsupported:
        # Trigger names a deployment but no deployment evidence backs it —
        # this is exactly the unsupported-causality failure mode; do not
        # let it reach "high" confidence.
        if root_cause.causal_strength == "confirmed":
            # Asserting deployment causation with full confidence but no
            # deployment evidence to back it is the more serious
            # overconfidence case — keep the stricter cap.
            return "low" if synthesis.missing_information else "medium"

        # "supported" already carries some hedging on the model's part; a
        # deployment-shaped trigger description without deployment
        # evidence caps at "medium" rather than being punished further to
        # "low" for the mere presence of unrelated missing_information.
        return "medium"

    if root_cause.causal_strength == "confirmed":
        if synthesis.trigger_status == "external_unknown":
            # The mechanism is clearly evidenced but its true trigger lies
            # outside the observed evidence — we know *what* broke, not
            # *why*. "Confirmed" here only vouches for the symptom, so cap
            # below "high" no matter how clean the mechanism evidence is.
            return "medium"

        # "identified" (a distinct evidenced trigger) or
        # "same_as_mechanism" (a self-caused mechanism with no separate
        # trigger, e.g. disk exhaustion) — the causal chain is fully
        # accounted for. A single decisive source is sufficient; do not
        # cap just because only one source type was cited or the model
        # listed unrelated open questions.
        return "high"

    # causal_strength is "supported" or "correlated": the mechanism is
    # backed but the link to its trigger is inferred rather than directly
    # evidenced. A model-acknowledged evidence gap for this incident caps
    # confidence, regardless of how many sources agree on the mechanism.
    ceiling = "medium" if synthesis.missing_information else "high"

    if len(supporting_source_types) >= 2:
        return ceiling

    if supporting_source_types:
        return "medium" if ceiling in ("high", "medium") else "low"

    return "low"
