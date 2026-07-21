from pathlib import Path

from app.evals.rca_dataset import (
    load_rca_eval_dataset,
)


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
        "rca-eval/1.0.0"
    )

    assert len(cases) >= 3

    case_ids = {
        case.id
        for case in cases
    }

    assert "rca-001" in case_ids
    assert "rca-002" in case_ids
    assert "rca-003" in case_ids


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

    assert uncertain_cases


def test_dataset_contains_false_correlation_case():
    _, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    assert any(
        case.scenario_type
        == "false_correlation"
        for case in cases
    )