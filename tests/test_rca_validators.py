"""Unit tests for app/evals/rca_validators.py.

Each test constructs a minimal :class:`~app.evals.rca_dataset.RCAEvalCase`
and a hand-crafted :class:`~app.schemas.analysis.RCAReport`, then asserts
the expected pass/fail outcome for each validator dimension.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.evals.rca_dataset import (
    ActionExpectation,
    CaseExpectations,
    CausalLanguagePolicy,
    EvalEvidenceItem,
    EvalIncident,
    NumericFactExpectation,
    ObservationExpectation,
    RCAEvalCase,
    RootCauseExpectation,
    TemporalFactExpectation,
)
from app.evals.rca_validators import (
    validate_actions,
    validate_causal_language,
    validate_case,
    validate_numeric_facts,
    validate_observations,
    validate_root_cause,
    validate_source_types,
    validate_temporal_facts,
)
from app.schemas.analysis import EvidenceItem, RCAReport

pytestmark = pytest.mark.no_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _make_incident() -> EvalIncident:
    return EvalIncident(
        id="incident-test",
        title="Test Incident",
        description="A test incident.",
        service_name="test-service",
        severity="high",
        started_at=_ts("2026-07-20T10:00:00"),
    )


def _make_evidence() -> list[EvalEvidenceItem]:
    return [
        EvalEvidenceItem(
            id="log-001",
            source_type="log",
            timestamp=_ts("2026-07-20T10:01:00"),
            content="database connection pool exhausted",
            data={"level": "ERROR"},
        ),
        EvalEvidenceItem(
            id="metric-001",
            source_type="metric",
            timestamp=_ts("2026-07-20T10:02:00"),
            content="db_connections = 95 count",
            data={"metric_name": "db_connections", "value": 95, "unit": "count"},
        ),
        EvalEvidenceItem(
            id="deployment-001",
            source_type="deployment",
            timestamp=_ts("2026-07-20T09:00:00"),
            content="app version 2.0.0 deployed",
            data={"version": "2.0.0"},
        ),
    ]


def _minimal_expectations(
    *,
    mechanism_keywords: list[str] = None,
    causal_strength: str = "unknown",
    acceptable_confidence: list[str] = None,
    dep_causality: str = "not_applicable",
) -> CaseExpectations:
    return CaseExpectations(
        observations=[],
        root_cause=RootCauseExpectation(
            immediate_mechanism_keywords_any=mechanism_keywords or ["pool exhausted"],
            causal_strength=causal_strength,
            acceptable_confidence=acceptable_confidence or ["medium"],
        ),
        actions=ActionExpectation(),
        numeric_facts=[],
        temporal_facts=[],
        causal_language=CausalLanguagePolicy(
            deployment_causality=dep_causality,
        ),
    )


def _make_case(expectations: CaseExpectations) -> RCAEvalCase:
    return RCAEvalCase(
        id="rca-test",
        title="Test case",
        scenario_type="clear_cause",
        difficulty="easy",
        incident=_make_incident(),
        evidence=_make_evidence(),
        expectations=expectations,
    )


def _make_report(
    *,
    summary: str = "The database connection pool was exhausted.",
    root_cause_text: str = "Database connection pool exhausted.",
    confidence: str = "medium",
    evidence_items: list[EvidenceItem] | None = None,
    actions: list[str] | None = None,
    missing: list[str] | None = None,
) -> RCAReport:
    return RCAReport(
        evidence=evidence_items or [
            EvidenceItem(
                excerpt="database connection pool exhausted",
                explanation="Pool reached its limit.",
                source_type="log",
                source_id="log-001",
            )
        ],
        incident_summary=summary,
        likely_root_cause=root_cause_text,
        recommended_actions=actions or ["Investigate connection leaks."],
        confidence=confidence,
        missing_information=missing or [],
    )


# ---------------------------------------------------------------------------
# 1. Observation validator
# ---------------------------------------------------------------------------


class TestValidateObservations:
    def test_no_required_observations_passes(self):
        exp = _minimal_expectations()
        case = _make_case(exp)
        report = _make_report()
        result = validate_observations(case, report)
        assert result.passed
        assert result.score == 1.0

    def test_keyword_match_passes(self):
        exp = CaseExpectations(
            observations=[
                ObservationExpectation(
                    id="obs-1",
                    concept="Pool exhausted.",
                    keywords_any=["pool exhausted"],
                    required=True,
                )
            ],
            root_cause=RootCauseExpectation(
                immediate_mechanism_keywords_any=["pool exhausted"],
                causal_strength="unknown",
                acceptable_confidence=["medium"],
            ),
            actions=ActionExpectation(),
            numeric_facts=[],
            temporal_facts=[],
            causal_language=CausalLanguagePolicy(deployment_causality="not_applicable"),
        )
        case = _make_case(exp)
        report = _make_report()
        result = validate_observations(case, report)
        assert result.passed
        assert result.score == 1.0

    def test_missing_required_observation_fails(self):
        exp = CaseExpectations(
            observations=[
                ObservationExpectation(
                    id="obs-1",
                    concept="OOM kill detected.",
                    keywords_any=["oomkilled", "out of memory"],
                    required=True,
                )
            ],
            root_cause=RootCauseExpectation(
                immediate_mechanism_keywords_any=["pool exhausted"],
                causal_strength="unknown",
                acceptable_confidence=["medium"],
            ),
            actions=ActionExpectation(),
            numeric_facts=[],
            temporal_facts=[],
            causal_language=CausalLanguagePolicy(deployment_causality="not_applicable"),
        )
        case = _make_case(exp)
        report = _make_report()
        result = validate_observations(case, report)
        assert not result.passed
        assert result.score == 0.0
        assert any("obs-1" in issue for issue in result.issues)

    def test_source_id_cite_satisfies_observation(self):
        exp = CaseExpectations(
            observations=[
                ObservationExpectation(
                    id="obs-1",
                    concept="Pool exhausted.",
                    acceptable_source_ids=["log-001"],
                    keywords_any=["oomkilled"],  # keyword won't match
                    required=True,
                )
            ],
            root_cause=RootCauseExpectation(
                immediate_mechanism_keywords_any=["pool exhausted"],
                causal_strength="unknown",
                acceptable_confidence=["medium"],
            ),
            actions=ActionExpectation(),
            numeric_facts=[],
            temporal_facts=[],
            causal_language=CausalLanguagePolicy(deployment_causality="not_applicable"),
        )
        case = _make_case(exp)
        report = _make_report()
        result = validate_observations(case, report)
        assert result.passed  # Source ID is cited even though keyword doesn't match


# ---------------------------------------------------------------------------
# 2. Root-cause validator
# ---------------------------------------------------------------------------


class TestValidateRootCause:
    def test_mechanism_found_correct_confidence_passes(self):
        exp = _minimal_expectations(
            mechanism_keywords=["pool exhausted"],
            acceptable_confidence=["medium"],
        )
        case = _make_case(exp)
        report = _make_report(confidence="medium")
        result = validate_root_cause(case, report)
        assert result.passed
        assert result.score > 0.8

    def test_missing_mechanism_fails(self):
        exp = _minimal_expectations(
            mechanism_keywords=["oomkilled", "out of memory"],
            acceptable_confidence=["medium"],
        )
        case = _make_case(exp)
        report = _make_report(confidence="medium")
        result = validate_root_cause(case, report)
        assert not result.passed

    def test_wrong_confidence_fails(self):
        exp = _minimal_expectations(
            mechanism_keywords=["pool exhausted"],
            acceptable_confidence=["low"],
        )
        case = _make_case(exp)
        report = _make_report(confidence="high")
        result = validate_root_cause(case, report)
        assert not result.passed


# ---------------------------------------------------------------------------
# 3. Actions validator
# ---------------------------------------------------------------------------


class TestValidateActions:
    def test_keyword_group_covered_passes(self):
        exp = _minimal_expectations()
        exp.actions = ActionExpectation(
            required_keyword_groups=[["investigate", "analyse"]],
        )
        case = _make_case(exp)
        report = _make_report(actions=["Investigate connection leaks."])
        result = validate_actions(case, report)
        assert result.passed

    def test_keyword_group_missing_fails(self):
        exp = _minimal_expectations()
        exp.actions = ActionExpectation(
            required_keyword_groups=[["rollback", "roll back"]],
        )
        case = _make_case(exp)
        report = _make_report(actions=["Check database logs."])
        result = validate_actions(case, report)
        assert not result.passed

    def test_forbidden_keyword_fails(self):
        exp = _minimal_expectations()
        exp.actions = ActionExpectation(
            forbidden_keywords=["disable all limits"],
        )
        case = _make_case(exp)
        report = _make_report(actions=["Disable all limits immediately."])
        result = validate_actions(case, report)
        assert not result.passed

    def test_no_constraints_passes(self):
        exp = _minimal_expectations()
        case = _make_case(exp)
        report = _make_report()
        result = validate_actions(case, report)
        assert result.passed
        assert result.score == 1.0


# ---------------------------------------------------------------------------
# 4. Source-type validator
# ---------------------------------------------------------------------------


class TestValidateSourceTypes:
    def test_correct_source_type_passes(self):
        exp = _minimal_expectations()
        case = _make_case(exp)
        report = _make_report(
            evidence_items=[
                EvidenceItem(
                    excerpt="database connection pool exhausted",
                    explanation="Pool reached limit.",
                    source_type="log",  # correct — log-001 is a log
                    source_id="log-001",
                )
            ]
        )
        result = validate_source_types(case, report)
        assert result.passed
        assert result.score == 1.0

    def test_wrong_source_type_fails(self):
        exp = _minimal_expectations()
        case = _make_case(exp)
        report = _make_report(
            evidence_items=[
                EvidenceItem(
                    excerpt="database connection pool exhausted",
                    explanation="Pool reached limit.",
                    source_type="metric",  # wrong — log-001 is a log, not metric
                    source_id="log-001",
                )
            ]
        )
        result = validate_source_types(case, report)
        assert not result.passed
        assert result.score == 0.0

    def test_unknown_source_id_not_penalised(self):
        """IDs outside the eval case are not penalised by this validator."""
        exp = _minimal_expectations()
        case = _make_case(exp)
        report = _make_report(
            evidence_items=[
                EvidenceItem(
                    excerpt="some other thing",
                    explanation="Whatever.",
                    source_type="runbook",
                    source_id="external-id-not-in-case",
                )
            ]
        )
        result = validate_source_types(case, report)
        assert result.passed  # No eval-case IDs were checked
        assert result.score == 1.0


# ---------------------------------------------------------------------------
# 5. Numeric validator
# ---------------------------------------------------------------------------


class TestValidateNumericFacts:
    def test_no_facts_passes(self):
        exp = _minimal_expectations()
        case = _make_case(exp)
        result = validate_numeric_facts(case, _make_report())
        assert result.passed

    def test_value_in_report_text_passes(self):
        exp = _minimal_expectations()
        exp.numeric_facts = [
            NumericFactExpectation(
                id="num-1",
                source_id="metric-001",
                name="db_connections",
                value=95,
                unit="count",
                tolerance=0,
            )
        ]
        case = _make_case(exp)
        report = _make_report(
            evidence_items=[
                EvidenceItem(
                    excerpt="db_connections = 95 count",
                    explanation="Connection count at 95.",
                    source_type="metric",
                    source_id="metric-001",
                )
            ]
        )
        result = validate_numeric_facts(case, report)
        assert result.passed

    def test_value_not_in_report_fails(self):
        exp = _minimal_expectations()
        exp.numeric_facts = [
            NumericFactExpectation(
                id="num-1",
                source_id="metric-001",
                name="db_connections",
                value=95,
                unit="count",
                tolerance=0,
            )
        ]
        case = _make_case(exp)
        # Report does not mention 95
        report = _make_report(
            summary="Something happened.",
            root_cause_text="Unknown cause.",
        )
        result = validate_numeric_facts(case, report)
        assert not result.passed

    def test_tolerance_allows_nearby_value(self):
        exp = _minimal_expectations()
        exp.numeric_facts = [
            NumericFactExpectation(
                id="num-1",
                source_id="metric-001",
                name="db_connections",
                value=95,
                unit="count",
                tolerance=5,
            )
        ]
        case = _make_case(exp)
        # Report mentions 98, which is within tolerance 5 of 95
        report = _make_report(
            summary="db_connections reached 98 which is near the limit.",
            root_cause_text="Near-limit connections.",
        )
        result = validate_numeric_facts(case, report)
        assert result.passed


# ---------------------------------------------------------------------------
# 6. Temporal validator
# ---------------------------------------------------------------------------


class TestValidateTemporalFacts:
    def test_no_facts_passes(self):
        exp = _minimal_expectations()
        case = _make_case(exp)
        result = validate_temporal_facts(case, _make_report())
        assert result.passed

    def test_before_relation_both_cited_passes(self):
        exp = _minimal_expectations()
        exp.temporal_facts = [
            TemporalFactExpectation(
                id="t-1",
                left_source_id="deployment-001",  # 09:00
                right_source_id="log-001",         # 10:01
                relation="before",
                max_gap_seconds=7200,
            )
        ]
        case = _make_case(exp)
        report = _make_report(
            evidence_items=[
                EvidenceItem(
                    excerpt="app version 2.0.0 deployed",
                    explanation="Deployment.",
                    source_type="deployment",
                    source_id="deployment-001",
                ),
                EvidenceItem(
                    excerpt="database connection pool exhausted",
                    explanation="Pool limit reached.",
                    source_type="log",
                    source_id="log-001",
                ),
            ]
        )
        result = validate_temporal_facts(case, report)
        assert result.passed

    def test_before_relation_gap_too_large_fails(self):
        exp = _minimal_expectations()
        exp.temporal_facts = [
            TemporalFactExpectation(
                id="t-1",
                left_source_id="deployment-001",  # 09:00
                right_source_id="log-001",         # 10:01 (61 min gap)
                relation="before",
                max_gap_seconds=60,  # only 60s allowed
            )
        ]
        case = _make_case(exp)
        report = _make_report(
            evidence_items=[
                EvidenceItem(
                    excerpt="deployed",
                    explanation="Deployment.",
                    source_type="deployment",
                    source_id="deployment-001",
                ),
                EvidenceItem(
                    excerpt="pool exhausted",
                    explanation="Pool limit.",
                    source_type="log",
                    source_id="log-001",
                ),
            ]
        )
        result = validate_temporal_facts(case, report)
        assert not result.passed

    def test_source_not_cited_fails(self):
        exp = _minimal_expectations()
        exp.temporal_facts = [
            TemporalFactExpectation(
                id="t-1",
                left_source_id="deployment-001",
                right_source_id="log-001",
                relation="before",
            )
        ]
        case = _make_case(exp)
        # Report only cites one of the two sources
        report = _make_report(
            evidence_items=[
                EvidenceItem(
                    excerpt="pool exhausted",
                    explanation="Pool limit.",
                    source_type="log",
                    source_id="log-001",
                )
            ]
        )
        result = validate_temporal_facts(case, report)
        assert not result.passed


# ---------------------------------------------------------------------------
# 7. Causal-language validator
# ---------------------------------------------------------------------------


class TestValidateCausalLanguage:
    def test_no_forbidden_phrases_passes(self):
        exp = _minimal_expectations(dep_causality="not_applicable")
        case = _make_case(exp)
        report = _make_report()
        result = validate_causal_language(case, report)
        assert result.passed

    def test_forbidden_phrase_fails(self):
        exp = _minimal_expectations(dep_causality="not_applicable")
        exp.causal_language.forbidden_phrases = ["deployment definitely caused"]
        case = _make_case(exp)
        report = _make_report(
            root_cause_text="The deployment definitely caused the failure."
        )
        result = validate_causal_language(case, report)
        assert not result.passed

    def test_forbidden_deployment_causality_fails(self):
        exp = _minimal_expectations(dep_causality="forbidden")
        case = _make_case(exp)
        report = _make_report(
            root_cause_text="The deployment caused the service to fail."
        )
        result = validate_causal_language(case, report)
        assert not result.passed

    def test_correlation_only_strong_claim_fails(self):
        exp = _minimal_expectations(dep_causality="correlation_only")
        case = _make_case(exp)
        report = _make_report(
            root_cause_text="The deployment definitely caused the outage."
        )
        result = validate_causal_language(case, report)
        assert not result.passed

    def test_required_deployment_citation_missing_fails(self):
        exp = _minimal_expectations(dep_causality="confirmed")
        case = _make_case(exp)
        # Report evidence does not include any deployment source
        report = _make_report()
        result = validate_causal_language(case, report)
        assert not result.passed

    def test_required_deployment_citation_present_passes(self):
        exp = _minimal_expectations(dep_causality="supported")
        case = _make_case(exp)
        report = _make_report(
            evidence_items=[
                EvidenceItem(
                    excerpt="app version 2.0.0 deployed",
                    explanation="Deployment triggered the incident.",
                    source_type="deployment",
                    source_id="deployment-001",
                )
            ]
        )
        result = validate_causal_language(case, report)
        assert result.passed

    def test_forbidden_claim_fails(self):
        exp = _minimal_expectations(dep_causality="not_applicable")
        exp.causal_language.forbidden_phrases = []
        exp.forbidden_claims = ["external payment provider outage"]
        case = _make_case(exp)
        report = _make_report(
            root_cause_text="Caused by external payment provider outage."
        )
        result = validate_causal_language(case, report)
        assert not result.passed


# ---------------------------------------------------------------------------
# 8. Full validate_case
# ---------------------------------------------------------------------------


class TestValidateCase:
    def test_all_passing_returns_passed(self):
        exp = CaseExpectations(
            observations=[
                ObservationExpectation(
                    id="obs-1",
                    concept="Pool exhausted.",
                    keywords_any=["pool exhausted"],
                    required=True,
                )
            ],
            root_cause=RootCauseExpectation(
                immediate_mechanism_keywords_any=["pool exhausted"],
                causal_strength="correlated",
                acceptable_confidence=["medium"],
            ),
            actions=ActionExpectation(
                required_keyword_groups=[["investigate"]],
            ),
            numeric_facts=[],
            temporal_facts=[],
            causal_language=CausalLanguagePolicy(
                deployment_causality="not_applicable",
            ),
        )
        case = _make_case(exp)
        report = _make_report(
            confidence="medium",
            actions=["Investigate connection leaks."],
        )
        result = validate_case(case, report)
        assert result.passed
        assert result.overall_score > 0.8
        assert result.case_id == "rca-test"

    def test_one_failing_dimension_fails_overall(self):
        exp = _minimal_expectations(
            mechanism_keywords=["oomkilled"],  # won't be in report
            acceptable_confidence=["medium"],
        )
        case = _make_case(exp)
        report = _make_report(confidence="medium")
        result = validate_case(case, report)
        assert not result.passed
