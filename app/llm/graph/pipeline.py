"""LangGraph wiring for the RCA multi-node pipeline.

Graph shape::

    extract -> cross_validate -> synthesize -> validate -> recommend_actions -> END

Nominal cost is 5 Mistral calls per report. The ``validate`` node runs an
adversarial pass over the synthesized root cause and re-judges its
``causal_strength`` / ``trigger_status`` before confidence is calibrated;
it skips its call (4 calls that report) when synthesis produced no
root_cause to attack. Each node may additionally trigger a targeted
schema-repair re-prompt of itself (see ``app.llm.graph.nodes``), charged
against a run-wide ``repairs_used`` budget capped at
``settings.rca_graph_max_repairs`` (default 3) — so the worst case for one
report is ``5 + rca_graph_max_repairs`` calls (8 with defaults).

``GraphRCAClient`` implements the same :class:`~app.llm.client.RCAClient`
interface as :class:`~app.llm.client.MistralRCAClient`, so it is a drop-in
replacement wherever an ``RCAClient`` is used (``analysis_service``,
``rca_eval_runner``, the dev dashboard) — see ``get_rca_client`` in
``app.llm.client``.
"""

import json
from typing import Any

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from app.core.config import settings
from app.llm.client import RCAClient, RCAGenerationResult
from app.llm.errors import InvalidRCAOutputError
from app.llm.graph.confidence import calibrate_confidence
from app.llm.graph.nodes import (
    run_action_node,
    run_contradiction_node,
    run_extraction_node,
    run_synthesis_node,
    run_validation_node,
)
from app.llm.graph.state import GraphState
from app.schemas.analysis import RCAReport


def _build_graph(*, model_name: str, max_repairs: int):
    graph = StateGraph(GraphState)

    graph.add_node(
        "extract",
        lambda state: run_extraction_node(
            state, model_name=model_name, max_repairs=max_repairs
        ),
    )
    graph.add_node(
        "cross_validate",
        lambda state: run_contradiction_node(
            state, model_name=model_name, max_repairs=max_repairs
        ),
    )
    graph.add_node(
        "synthesize",
        lambda state: run_synthesis_node(
            state, model_name=model_name, max_repairs=max_repairs
        ),
    )
    graph.add_node(
        "validate",
        lambda state: run_validation_node(
            state, model_name=model_name, max_repairs=max_repairs
        ),
    )
    graph.add_node(
        "recommend_actions",
        lambda state: run_action_node(
            state, model_name=model_name, max_repairs=max_repairs
        ),
    )

    graph.set_entry_point("extract")
    graph.add_edge("extract", "cross_validate")
    graph.add_edge("cross_validate", "synthesize")
    graph.add_edge("synthesize", "validate")
    graph.add_edge("validate", "recommend_actions")
    graph.add_edge("recommend_actions", END)

    return graph.compile()


class GraphRCAClient(RCAClient):
    provider = "mistral"
    pipeline_mode = "graph"

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.mistral_model
        self.max_repairs = settings.rca_graph_max_repairs
        self._graph = _build_graph(
            model_name=self.model_name,
            max_repairs=self.max_repairs,
        )

    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        return self.generate_rca_with_debug(evidence_payload).report

    def generate_rca_with_debug(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAGenerationResult:
        initial_state: GraphState = {
            "evidence_payload": evidence_payload,
            "repairs_used": 0,
            "call_log": [],
        }

        import os
        import mlflow
        _mlflow_enabled = bool(os.environ.get("MLFLOW_TRACKING_URI"))
        trace_req_id = None
        if _mlflow_enabled:
            with mlflow.start_span(name=f"GraphRCA_{self.model_name}") as span:
                trace_req_id = span.request_id
                final_state = self._graph.invoke(initial_state)
        else:
            final_state = self._graph.invoke(initial_state)

        extraction = final_state["extraction"]
        contradiction = final_state["contradiction"]
        synthesis = final_state["synthesis"]
        actions = final_state["actions"]
        call_log = final_state.get("call_log", [])

        confidence = calibrate_confidence(
            extraction=extraction,
            contradiction=contradiction,
            synthesis=synthesis,
        )

        report_payload = {
            "evidence": [
                item.model_dump(mode="json") for item in extraction.evidence
            ],
            "observations": [
                item.model_dump(mode="json") for item in synthesis.observations
            ],
            "log_anomalies": extraction.log_anomalies,
            "metric_anomalies": extraction.metric_anomalies,
            "contradictions_detected": contradiction.contradictions_detected,
            "incident_summary": synthesis.incident_summary,
            "likely_root_cause": synthesis.likely_root_cause,
            "root_cause": (
                synthesis.root_cause.model_dump(mode="json")
                if synthesis.root_cause
                else None
            ),
            "recommended_actions": actions.recommended_actions,
            "confidence": confidence,
            "missing_information": synthesis.missing_information,
        }

        try:
            report = RCAReport.model_validate(report_payload)

        except ValidationError as exc:
            errors = exc.errors(include_url=False)

            raise InvalidRCAOutputError(
                "Graph pipeline output failed final RCAReport schema "
                "validation after assembling all node outputs.",
                debug={
                    "attempts": call_log,
                    "final_raw_output": json.dumps(
                        report_payload, default=str
                    ),
                    "final_metadata": {},
                    "final_validation_errors": errors,
                },
            ) from exc

        raw_output = report.model_dump_json(indent=2)
        # Trigger-Based Tracing:
        # The user only wants to see FAILED cases in MLflow.
        # Since we reached the end of the pipeline without exceptions, delete the trace.
        if trace_req_id:
            try:
                import mlflow
                client = mlflow.MlflowClient()
                exp = client.get_experiment_by_name("IncidentPilot-RCA")
                if exp:
                    client.delete_traces(
                        experiment_id=exp.experiment_id,
                        trace_ids=[trace_req_id]
                    )
            except Exception:
                pass

        attempts = [
            {
                "attempt": index + 1,
                "raw_output": entry["raw_output"],
                "metadata": entry["metadata"],
                "validation_errors": entry["validation_errors"],
            }
            for index, entry in enumerate(call_log)
        ]

        metadata = {
            "source": "graph_rca_client",
            "provider": self.provider,
            "node_calls": len(call_log),
            "repairs_used": final_state.get("repairs_used", 0),
            "validation": final_state.get("validation_debug"),
        }

        return RCAGenerationResult(
            report=report,
            raw_output=raw_output,
            metadata=metadata,
            attempts=attempts,
        )
