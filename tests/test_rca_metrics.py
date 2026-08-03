from app.evals.rca_metrics import compute_metrics
from app.evals.rca_validators import CaseValidationResult, DimensionResult

def test_compute_metrics_with_agentic_stats():
    res1 = CaseValidationResult(
        case_id="case-1",
        dimensions=[
            DimensionResult(dimension="root_cause", passed=True, score=1.0),
        ]
    )
    res2 = CaseValidationResult(
        case_id="case-2",
        dimensions=[
            DimensionResult(dimension="root_cause", passed=False, score=0.5),
        ]
    )
    
    # 2 cases
    results = [res1, res2]
    rounds = [2, 4]      # mean = 3.0
    tool_calls = [5, 9]  # mean = 7.0
    
    metrics = compute_metrics(results, rounds_list=rounds, tool_calls_list=tool_calls)
    
    assert metrics.case_count == 2
    assert metrics.avg_investigation_rounds == 3.0
    assert metrics.avg_tool_calls == 7.0
    
def test_compute_metrics_without_agentic_stats():
    res1 = CaseValidationResult(
        case_id="case-1",
        dimensions=[
            DimensionResult(dimension="root_cause", passed=True, score=1.0),
        ]
    )
    
    metrics = compute_metrics([res1])
    assert metrics.avg_investigation_rounds == 0.0
    assert metrics.avg_tool_calls == 0.0
