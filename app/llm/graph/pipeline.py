"""LangGraph wiring for the RCA multi-node pipeline.

v0 (straight pipeline) graph shape::

    extract -> cross_validate -> synthesize -> validate -> recommend_actions -> END

v1 (agentic) graph shape::

    extract -> hypothesis -> investigate_gap ──→ (loop if gaps remain AND rounds < max)
                                            └──→ cross_validate -> synthesize -> validate
                                                  -> recommend_actions -> END

Nominal LLM call count
-----------------------
- v0 : 5 calls (extract, cross_validate, synthesize, validate, recommend_actions)
- v1 : 7 calls (+ hypothesis = 6, tool calls are DB-only = 0 extra, same final 5)
- Worst case v1: 7 + rca_graph_max_repairs = 10

The ``validate`` node runs an adversarial pass and may be skipped (4 calls
that report) when synthesis produced no root_cause to attack.  Each node may
also trigger schema-repair re-prompts charged against a run-wide
``repairs_used`` budget capped at ``settings.rca_graph_max_repairs`` (default 3).

``GraphRCAClient`` implements the same :class:`~app.llm.client.RCAClient`
interface as :class:`~app.llm.client.MistralRCAClient`, so it is a drop-in
replacement wherever an ``RCAClient`` is used (``analysis_service``,
``rca_eval_runner``, the dev dashboard) — see ``get_rca_client`` in
``app.llm.client``.

PostgreSQL checkpointer (Group 2)
-----------------------------------
When ``LANGGRAPH_CHECKPOINT_URL`` is set in the environment, the graph is
compiled with a ``PostgresSaver`` checkpointer that persists full graph state
after every node. The Celery task passes ``analysis_run_id`` as the LangGraph
``thread_id``, so:

- On first run → starts fresh.
- On worker crash / retry → resumes from the last successful node rather than
  restarting from scratch.
- ``PostgresSaver.setup()`` is called once at pipeline instantiation so the
  checkpoint tables are created automatically (no separate Alembic migration
  needed — LangGraph owns these tables).
"""

import json
import os
from typing import Any
from uuid import uuid4

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from app.core.config import settings
from app.core.redaction import redact_value
from app.llm.client import RCAClient, RCAGenerationResult
from app.llm.errors import InvalidRCAOutputError
from app.llm.graph.agent_nodes import run_gap_tool_node, run_hypothesis_node
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


# ── loop router ───────────────────────────────────────────────────────────────

def _should_investigate(state: GraphState) -> str:
    """Conditional edge: keep investigating if gaps remain AND under the round cap."""
    gap_queries: list[str] = state.get("gap_queries", [])
    rounds: int = state.get("investigation_rounds", 0)

    if gap_queries and rounds < settings.rca_agent_max_rounds:
        return "investigate"
    return "synthesise"


# ── graph builder ─────────────────────────────────────────────────────────────

def _build_graph(*, model_name: str, max_repairs: int, checkpointer=None):
    graph = StateGraph(GraphState)

    # ── node registration ──────────────────────────────────────────────────────
    graph.add_node(
        "extract",
        lambda state: run_extraction_node(
            state, model_name=model_name, max_repairs=max_repairs
        ),
    )
    graph.add_node(
        "hypothesis",
        lambda state: run_hypothesis_node(
            state, model_name=model_name, max_repairs=max_repairs
        ),
    )
    graph.add_node(
        "investigate_gap",
        lambda state: run_gap_tool_node(
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

    # ── edges ──────────────────────────────────────────────────────────────────
    graph.set_entry_point("extract")
    graph.add_edge("extract", "hypothesis")

    # Agentic investigation loop
    graph.add_conditional_edges(
        "hypothesis",
        _should_investigate,
        {"investigate": "investigate_gap", "synthesise": "cross_validate"},
    )
    graph.add_conditional_edges(
        "investigate_gap",
        _should_investigate,
        {"investigate": "investigate_gap", "synthesise": "cross_validate"},
    )

    graph.add_edge("cross_validate", "synthesize")
    graph.add_edge("synthesize", "validate")
    graph.add_edge("validate", "recommend_actions")
    graph.add_edge("recommend_actions", END)

    return graph.compile(checkpointer=checkpointer)


# ── client ────────────────────────────────────────────────────────────────────

class GraphRCAClient(RCAClient):
    provider = "mistral"
    pipeline_mode = "graph"

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.mistral_model
        self.max_repairs = settings.rca_graph_max_repairs

        checkpointer = self._init_checkpointer()
        self._graph = _build_graph(
            model_name=self.model_name,
            max_repairs=self.max_repairs,
            checkpointer=checkpointer,
        )

    def _init_checkpointer(self):
        """Initialise the Postgres checkpointer if configured.

        Returns None when ``LANGGRAPH_CHECKPOINT_URL`` is not set (CI / tests),
        in which case the graph runs without persistence (existing behaviour).
        """
        checkpoint_url = os.environ.get("LANGGRAPH_CHECKPOINT_URL")
        if not checkpoint_url:
            return None

        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            # Convert SQLAlchemy URL scheme to raw psycopg DSN
            dsn = checkpoint_url.replace(
                "postgresql+psycopg://", "postgresql://"
            ).replace(
                "postgresql+psycopg2://", "postgresql://"
            )
            conn = __import__("psycopg").connect(
                dsn, autocommit=True, prepare_threshold=0
            )
            saver = PostgresSaver(conn)
            saver.setup()  # creates checkpoint tables if they don't exist
            return saver
        except Exception as exc:
            # Gracefully degrade — the pipeline still works, just without
            # crash-recovery.
            import logging
            logging.getLogger(__name__).warning(
                "LangGraph checkpointer unavailable — running without "
                "persistence. Error: %s", exc
            )
            return None

    def generate_rca(
        self,
        evidence_payload: dict[str, Any],
    ) -> RCAReport:
        return self.generate_rca_with_debug(evidence_payload).report

    def generate_rca_with_debug(
        self,
        evidence_payload: dict[str, Any],
        thread_id: str | None = None,
    ) -> RCAGenerationResult:
        initial_state: GraphState = {
            "evidence_payload": evidence_payload,
            "repairs_used": 0,
            "call_log": [],
        }

        # LangGraph config — thread_id scopes the checkpoint to this analysis run
        invoke_config: dict[str, Any] = {}
        if self._graph.checkpointer is not None:
            effective_thread_id = thread_id or uuid4().hex
            invoke_config = {"configurable": {"thread_id": effective_thread_id}}

        import os as _os
        import mlflow as _mlflow
        _mlflow_enabled = bool(_os.environ.get("MLFLOW_TRACKING_URI"))
        trace_req_id = None

        if _mlflow_enabled:
            with _mlflow.start_span(name=f"GraphRCA_{self.model_name}") as span:
                trace_req_id = span.request_id
                final_state = self._graph.invoke(initial_state, config=invoke_config)
        else:
            final_state = self._graph.invoke(initial_state, config=invoke_config)

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
        # Only keep MLflow traces for FAILED cases — delete this one on success.
        if trace_req_id:
            try:
                client = _mlflow.MlflowClient()
                exp = client.get_experiment_by_name("IncidentPilot-RCA")
                if exp:
                    client.delete_traces(
                        experiment_id=exp.experiment_id,
                        trace_ids=[trace_req_id],
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

        # Include agentic metadata in the result
        tool_results = final_state.get("tool_results", [])
        hypothesis = final_state.get("hypothesis")

        metadata = {
            "source": "graph_rca_client",
            "provider": self.provider,
            "node_calls": len(call_log),
            "repairs_used": final_state.get("repairs_used", 0),
            "validation": final_state.get("validation_debug"),
            # Phase 5 agentic fields
            "investigation_rounds": final_state.get("investigation_rounds", 0),
            "tool_results": tool_results,
            "initial_hypothesis": hypothesis.hypothesis if hypothesis else None,
            "initial_confidence": hypothesis.confidence_so_far if hypothesis else None,
        }

        return RCAGenerationResult(
            report=report,
            raw_output=raw_output,
            metadata=redact_value(metadata),
            attempts=attempts,
        )
