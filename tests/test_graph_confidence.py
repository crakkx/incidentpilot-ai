from app.llm.graph.schemas import (
    ContradictionResult,
    ExtractionResult,
    SynthesisResult,
)
from app.schemas.analysis import (
    EvidenceItem,
    RootCauseAssessment,
)
from app.llm.graph.confidence import calibrate_confidence

def _make_extraction(source_types: list[str]) -> ExtractionResult:
    return ExtractionResult(
        evidence=[
            EvidenceItem(
                source_type=t,
                source_id=f"src-{i}",
                excerpt="test",
                explanation="test"
            )
            for i, t in enumerate(source_types)
        ]
    )


def test_confidence_is_low_when_root_cause_missing():
    conf = calibrate_confidence(
        extraction=ExtractionResult(evidence=[]),
        contradiction=ContradictionResult(cross_checks=[], contradictions_detected=None),
        synthesis=SynthesisResult(
            incident_summary="test",
            likely_root_cause="test",
            root_cause=None,
            missing_information=[],
            supporting_evidence_ids=[],
            trigger_status="identified",
            contradiction_conflicts_with_mechanism=False
        )
    )
    assert conf == "low"


def test_confidence_is_low_on_contradiction():
    conf = calibrate_confidence(
        extraction=_make_extraction(["log"]),
        contradiction=ContradictionResult(cross_checks=[], contradictions_detected="test"),
        synthesis=SynthesisResult(
            incident_summary="test",
            likely_root_cause="test",
            root_cause=RootCauseAssessment(
                immediate_mechanism="test",
                suspected_trigger=None,
                causal_strength="confirmed"
            ),
            missing_information=[],
            supporting_evidence_ids=["src-0"],
            trigger_status="identified",
            contradiction_conflicts_with_mechanism=True
        )
    )
    assert conf == "low"


def test_confidence_is_low_when_causal_strength_unknown():
    conf = calibrate_confidence(
        extraction=_make_extraction(["log", "metric"]),
        contradiction=ContradictionResult(cross_checks=[], contradictions_detected=None),
        synthesis=SynthesisResult(
            incident_summary="test",
            likely_root_cause="test",
            root_cause=RootCauseAssessment(
                immediate_mechanism="test",
                suspected_trigger=None,
                causal_strength="unknown"
            ),
            missing_information=[],
            supporting_evidence_ids=["src-0", "src-1"],
            trigger_status="identified",
            contradiction_conflicts_with_mechanism=False
        )
    )
    assert conf == "low"


def test_confidence_is_high_when_confirmed_and_identified():
    conf = calibrate_confidence(
        extraction=_make_extraction(["log"]),
        contradiction=ContradictionResult(cross_checks=[], contradictions_detected=None),
        synthesis=SynthesisResult(
            incident_summary="test",
            likely_root_cause="test",
            root_cause=RootCauseAssessment(
                immediate_mechanism="test",
                suspected_trigger="test",
                causal_strength="confirmed"
            ),
            missing_information=[],
            supporting_evidence_ids=["src-0"],
            trigger_status="identified",
            contradiction_conflicts_with_mechanism=False
        )
    )
    assert conf == "high"


def test_confidence_caps_at_medium_when_external_unknown():
    conf = calibrate_confidence(
        extraction=_make_extraction(["log", "metric"]),
        contradiction=ContradictionResult(cross_checks=[], contradictions_detected=None),
        synthesis=SynthesisResult(
            incident_summary="test",
            likely_root_cause="test",
            root_cause=RootCauseAssessment(
                immediate_mechanism="test",
                suspected_trigger=None,
                causal_strength="confirmed"
            ),
            missing_information=[],
            supporting_evidence_ids=["src-0", "src-1"],
            trigger_status="external_unknown",
            contradiction_conflicts_with_mechanism=False
        )
    )
    assert conf == "medium"


def test_confidence_punishes_unsupported_deployment():
    # Trigger claims deployment ("recent deploy"), strength is confirmed, but no deployment evidence is cited
    conf = calibrate_confidence(
        extraction=_make_extraction(["log", "metric"]),
        contradiction=ContradictionResult(cross_checks=[], contradictions_detected=None),
        synthesis=SynthesisResult(
            incident_summary="test",
            likely_root_cause="test",
            root_cause=RootCauseAssessment(
                immediate_mechanism="test",
                suspected_trigger="The recent deploy broke it",
                causal_strength="confirmed"
            ),
            missing_information=["Missing deployment config"],
            supporting_evidence_ids=["src-0", "src-1"],
            trigger_status="identified",
            contradiction_conflicts_with_mechanism=False
        )
    )
    assert conf == "low"
