from pathlib import Path

from app.evals.rca_dataset import (
    load_rca_eval_dataset,
)
import pytest

pytestmark = pytest.mark.no_db


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_ROOT = (
    PROJECT_ROOT
    / "data"
    / "rca_eval"
    / "v1"
)


def test_rca_eval_dataset_is_valid():
    manifest, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    assert manifest.dataset_version == (
        "rca-eval/2.0.0"
    )

    assert len(cases) == 40


def test_all_original_cases_present():
    _, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    case_ids = {
        case.id
        for case in cases
    }

    # Original 3 cases
    assert "rca-001" in case_ids
    assert "rca-002" in case_ids
    assert "rca-003" in case_ids

    # Phase-2 additions
    assert "rca-004" in case_ids
    assert "rca-010" in case_ids
    assert "rca-015" in case_ids
    assert "rca-017" in case_ids
    assert "rca-020" in case_ids
    assert "rca-022" in case_ids
    assert "rca-024" in case_ids
    assert "rca-025" in case_ids


def test_dataset_covers_all_scenario_types():
    _, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    scenario_types = {
        case.scenario_type
        for case in cases
    }

    expected_types = {
        "clear_cause",
        "ambiguous",
        "insufficient_evidence",
        "conflicting_evidence",
        "false_correlation",
        "multi_cause",
        "numeric_edge_case",
        "temporal_edge_case",
        "noisy_evidence",
    }

    assert expected_types.issubset(
        scenario_types
    )


def test_dataset_contains_uncertain_case():
    _, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    uncertain_cases = [
        case
        for case in cases
        if case.scenario_type
        in {
            "insufficient_evidence",
            "ambiguous",
            "conflicting_evidence",
        }
    ]

    assert len(uncertain_cases) >= 6


def test_dataset_contains_false_correlation_case():
    _, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    assert (
        sum(
            1
            for case in cases
            if case.scenario_type
            == "false_correlation"
        )
        >= 2
    )


def test_all_evidence_source_ids_are_internally_consistent():
    """Every source ID referenced in expectations must exist in the evidence."""
    _, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    for case in cases:
        evidence_ids = {
            ev.id for ev in case.evidence
        }
        exp = case.expectations

        # Observation acceptable_source_ids
        for obs in exp.observations:
            for sid in obs.acceptable_source_ids:
                assert sid in evidence_ids, (
                    f"{case.id}: observation '{obs.id}' "
                    f"references unknown source_id '{sid}'"
                )

        # Numeric fact source_ids
        for fact in exp.numeric_facts:
            assert fact.source_id in evidence_ids, (
                f"{case.id}: numeric_fact '{fact.id}' "
                f"references unknown source_id '{fact.source_id}'"
            )

        # Temporal fact source_ids
        for tfact in exp.temporal_facts:
            for sid in (
                tfact.left_source_id,
                tfact.right_source_id,
            ):
                assert sid in evidence_ids, (
                    f"{case.id}: temporal_fact '{tfact.id}' "
                    f"references unknown source_id '{sid}'"
                )