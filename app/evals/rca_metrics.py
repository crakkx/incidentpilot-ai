"""Aggregate RCA evaluation metrics.

Takes a list of :class:`~app.evals.rca_validators.CaseValidationResult`
objects (one per eval case) and returns a single
:class:`RCAEvalMetrics` summary suitable for reporting.

Eight domain-specific metrics are computed:

* ``observation_recall``       — fraction of required observations satisfied.
* ``root_cause_accuracy``      — cases where mechanism keywords matched.
* ``action_coverage``          — fraction of required keyword groups covered.
* ``source_type_precision``    — 1 − (source-type violations / checked items).
* ``numeric_fact_accuracy``    — numeric values within tolerance.
* ``temporal_accuracy``        — temporal relations correctly satisfied.
* ``causal_language_compliance`` — cases with no forbidden phrase/policy violation.
* ``overall_pass_rate``        — cases passing **all** dimensions.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass

from app.evals.rca_validators import CaseValidationResult


# ---------------------------------------------------------------------------
# Metrics dataclass
# ---------------------------------------------------------------------------


@dataclass
class RCAEvalMetrics:
    """Aggregate metrics across all evaluated cases."""

    case_count: int
    """Total number of cases evaluated."""

    # Per-dimension averages (0.0 – 1.0 unless noted)
    observation_recall: float
    root_cause_accuracy: float
    action_coverage: float
    source_type_precision: float
    numeric_fact_accuracy: float
    temporal_accuracy: float
    causal_language_compliance: float

    # Overall
    overall_pass_rate: float
    """Fraction of cases that passed every dimension."""

    mean_overall_score: float
    """Mean of per-case :attr:`~CaseValidationResult.overall_score`."""

    avg_investigation_rounds: float = 0.0
    """Average investigation rounds per case."""

    avg_tool_calls: float = 0.0
    """Average tool calls per case."""

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


    def __str__(self) -> str:  # noqa: D401
        return (
            f"Cases:                      {self.case_count}\n"
            f"Observation recall:         {self.observation_recall:.2%}\n"
            f"Root-cause accuracy:        {self.root_cause_accuracy:.2%}\n"
            f"Action coverage:            {self.action_coverage:.2%}\n"
            f"Source-type precision:      {self.source_type_precision:.2%}\n"
            f"Numeric fact accuracy:      {self.numeric_fact_accuracy:.2%}\n"
            f"Temporal accuracy:          {self.temporal_accuracy:.2%}\n"
            f"Causal-language compliance: {self.causal_language_compliance:.2%}\n"
            f"Overall pass rate:          {self.overall_pass_rate:.2%}\n"
            f"Mean overall score:         {self.mean_overall_score:.4f}"
        )


# ---------------------------------------------------------------------------
# Per-dimension score extractor
# ---------------------------------------------------------------------------


def _dimension_scores(
    results: list[CaseValidationResult],
    dimension: str,
) -> list[float]:
    """Return per-case scores for the named dimension.

    Cases that did not produce a result for that dimension (e.g. because
    there were no temporal facts) return ``1.0`` (neutral / not tested).
    """
    scores: list[float] = []
    for result in results:
        for dim in result.dimensions:
            if dim.dimension == dimension:
                scores.append(dim.score)
                break
        else:
            # Dimension not present → treat as fully passing.
            scores.append(1.0)
    return scores


def _dimension_pass_rate(
    results: list[CaseValidationResult],
    dimension: str,
) -> float:
    """Return the fraction of cases that passed the named dimension."""
    passed = 0
    for result in results:
        for dim in result.dimensions:
            if dim.dimension == dimension:
                if dim.passed:
                    passed += 1
                break
        else:
            passed += 1  # Dimension absent → not tested → pass.
    return passed / len(results)


# ---------------------------------------------------------------------------
# Public compute function
# ---------------------------------------------------------------------------


def compute_metrics(
    results: list[CaseValidationResult],
    rounds_list: list[int] | None = None,
    tool_calls_list: list[int] | None = None,
) -> RCAEvalMetrics:
    """Compute :class:`RCAEvalMetrics` from a list of case results."""
    if not results:
        raise ValueError("Cannot compute metrics from an empty result list.")

    n = len(results)

    overall_pass_rate = sum(1 for r in results if r.passed) / n
    mean_overall_score = statistics.fmean(r.overall_score for r in results)

    avg_rounds = statistics.fmean(rounds_list) if rounds_list else 0.0
    avg_tools = statistics.fmean(tool_calls_list) if tool_calls_list else 0.0

    return RCAEvalMetrics(
        case_count=n,
        observation_recall=statistics.fmean(
            _dimension_scores(results, "observations")
        ),
        root_cause_accuracy=_dimension_pass_rate(results, "root_cause"),
        action_coverage=statistics.fmean(
            _dimension_scores(results, "actions")
        ),
        source_type_precision=statistics.fmean(
            _dimension_scores(results, "source_types")
        ),
        numeric_fact_accuracy=statistics.fmean(
            _dimension_scores(results, "numeric_facts")
        ),
        temporal_accuracy=statistics.fmean(
            _dimension_scores(results, "temporal_facts")
        ),
        causal_language_compliance=_dimension_pass_rate(
            results, "causal_language"
        ),
        overall_pass_rate=overall_pass_rate,
        mean_overall_score=mean_overall_score,
        avg_investigation_rounds=avg_rounds,
        avg_tool_calls=avg_tools,
    )



# ---------------------------------------------------------------------------
# Markdown report renderer
# ---------------------------------------------------------------------------


def render_metrics_markdown(
    metrics: RCAEvalMetrics,
    generated_at: str,
    model_name: str,
    provider: str,
) -> str:
    """Render a Markdown summary table for the given metrics."""
    return f"""\
# RCA Evaluation Report

Generated: `{generated_at}`

Model: `{model_name}` via `{provider}`

Cases evaluated: `{metrics.case_count}`

| Metric | Result |
|---|---:|
| Observation recall | {metrics.observation_recall:.2%} |
| Root-cause accuracy | {metrics.root_cause_accuracy:.2%} |
| Action coverage | {metrics.action_coverage:.2%} |
| Source-type precision | {metrics.source_type_precision:.2%} |
| Numeric fact accuracy | {metrics.numeric_fact_accuracy:.2%} |
| Temporal accuracy | {metrics.temporal_accuracy:.2%} |
| Causal-language compliance | {metrics.causal_language_compliance:.2%} |
| **Overall pass rate** | **{metrics.overall_pass_rate:.2%}** |
| Mean overall score | {metrics.mean_overall_score:.4f} |

These results use the offline eval dataset and rule-based validators.
They are not a production benchmark.
"""
