"""Node functions for the RCA LangGraph pipeline.

Each ``run_*_node`` function reads its inputs from ``GraphState``, calls
Mistral with a schema scoped to exactly that node's job, and writes its
parsed result back into the state. Schema-validation failures are repaired
by re-prompting the *same node only* with the validation error appended —
never the whole pipeline — and are charged against a run-wide
``repairs_used`` budget (see ``GraphState``) so the total call count for a
report stays bounded at ``4 + max_repairs``.
"""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.redaction import redact_string, redact_value
from app.llm.errors import InvalidRCAOutputError
from app.llm.graph.prompts import (
    ACTION_SYSTEM_PROMPT,
    CONTRADICTION_SYSTEM_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    VALIDATION_SYSTEM_PROMPT,
)
from app.llm.graph.schemas import (
    ActionResult,
    ContradictionResult,
    ExtractionResult,
    SynthesisResult,
    ValidationResult,
)
from app.llm.graph.state import GraphState
from app.llm.mistral_http import call_mistral_chat


def _compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def _record_call(
    state: GraphState,
    node_name: str,
    raw_output: str,
    metadata: dict[str, Any],
    validation_errors: list[Any] | None = None,
) -> None:
    state.setdefault("call_log", []).append(
        {
            "node": node_name,
            "raw_output": redact_string(raw_output),
            "metadata": redact_value(metadata),
            "validation_errors": redact_value(validation_errors or []),
        }
    )


def _invoke_node(
    *,
    state: GraphState,
    node_name: str,
    system_prompt: str,
    user_prompt: str,
    schema_model: type[BaseModel],
    schema_name: str,
    model_name: str,
    max_tokens: int,
    max_repairs: int,
) -> BaseModel:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    while True:
        content, metadata = call_mistral_chat(
            messages=messages,
            response_schema=schema_model.model_json_schema(),
            schema_name=schema_name,
            model_name=model_name,
            max_tokens=max_tokens,
        )

        try:
            parsed = schema_model.model_validate_json(content)
            _record_call(state, node_name, content, metadata)
            return parsed

        except ValidationError as exc:
            errors = exc.errors(include_url=False)
            _record_call(state, node_name, content, metadata, errors)

            repairs_used = state.get("repairs_used", 0)

            if repairs_used >= max_repairs:
                raise InvalidRCAOutputError(
                    f"Graph node '{node_name}' failed schema validation "
                    f"after {repairs_used} repair attempt(s).",
                    debug={
                        "attempts": state.get("call_log", []),
                        "final_raw_output": redact_string(content),
                        "final_metadata": redact_value(metadata),
                        "final_validation_errors": redact_value(errors),
                    },
                ) from exc

            state["repairs_used"] = repairs_used + 1

            messages = messages + [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        "The previous response failed schema validation. "
                        "Return the complete corrected JSON object only, "
                        "matching the schema exactly.\n\n"
                        f"Validation errors:\n{_compact(errors)}"
                    ),
                },
            ]


from app.llm.tracing import mlflow_trace

@mlflow_trace(span_type="CHAIN")
def run_extraction_node(
    state: GraphState,
    *,
    model_name: str,
    max_repairs: int,
) -> GraphState:
    evidence_payload = state["evidence_payload"]

    user_prompt = (
        "Extract anomalies from the incident evidence below. Only use "
        "what is supplied — do not invent anything.\n\n"
        "Return only JSON matching this schema:\n"
        f"{_compact(ExtractionResult.model_json_schema())}\n\n"
        f"Supplied evidence:\n{_compact(evidence_payload)}"
    )

    state["extraction"] = _invoke_node(
        state=state,
        node_name="extraction",
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_model=ExtractionResult,
        schema_name="rca_extraction",
        model_name=model_name,
        max_tokens=1200,
        max_repairs=max_repairs,
    )

    return state


@mlflow_trace(span_type="CHAIN")
def run_contradiction_node(
    state: GraphState,
    *,
    model_name: str,
    max_repairs: int,
) -> GraphState:
    extraction: ExtractionResult = state["extraction"]

    payload = {
        "log_anomalies": extraction.log_anomalies,
        "metric_anomalies": extraction.metric_anomalies,
    }

    user_prompt = (
        "Cross-check the log anomalies against the metric anomalies "
        "below.\n\n"
        "Return only JSON matching this schema:\n"
        f"{_compact(ContradictionResult.model_json_schema())}\n\n"
        f"Anomalies:\n{_compact(payload)}"
    )

    state["contradiction"] = _invoke_node(
        state=state,
        node_name="contradiction",
        system_prompt=CONTRADICTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_model=ContradictionResult,
        schema_name="rca_contradiction",
        model_name=model_name,
        max_tokens=900,
        max_repairs=max_repairs,
    )

    return state


@mlflow_trace(span_type="CHAIN")
def run_synthesis_node(
    state: GraphState,
    *,
    model_name: str,
    max_repairs: int,
) -> GraphState:
    extraction: ExtractionResult = state["extraction"]
    contradiction: ContradictionResult = state["contradiction"]
    evidence_payload = state["evidence_payload"]

    payload = {
        "incident": evidence_payload.get("incident", {}),
        "log_anomalies": extraction.log_anomalies,
        "metric_anomalies": extraction.metric_anomalies,
        "deployment_events": extraction.deployment_events,
        "evidence": [
            item.model_dump(mode="json") for item in extraction.evidence
        ],
        "cross_validation": contradiction.model_dump(mode="json"),
        "runbook_chunks": evidence_payload.get("runbook_chunks", []),
    }

    user_prompt = (
        "Determine the root cause using the extracted anomalies, "
        "evidence, and cross-validation verdicts below.\n\n"
        "Return only JSON matching this schema:\n"
        f"{_compact(SynthesisResult.model_json_schema())}\n\n"
        f"Input:\n{_compact(payload)}"
    )

    state["synthesis"] = _invoke_node(
        state=state,
        node_name="synthesis",
        system_prompt=SYNTHESIS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_model=SynthesisResult,
        schema_name="rca_synthesis",
        model_name=model_name,
        max_tokens=1400,
        max_repairs=max_repairs,
    )

    return state


@mlflow_trace(span_type="CHAIN")
def run_validation_node(
    state: GraphState,
    *,
    model_name: str,
    max_repairs: int,
) -> GraphState:
    extraction: ExtractionResult = state["extraction"]
    contradiction: ContradictionResult = state["contradiction"]
    synthesis: SynthesisResult = state["synthesis"]

    if synthesis.root_cause is None:
        # No hypothesis to attack — skip the call entirely and leave the
        # synthesis verdict (already "unknown"/absent) untouched.
        return state

    payload = {
        "proposed_root_cause": synthesis.root_cause.model_dump(mode="json"),
        "trigger_status": synthesis.trigger_status,
        "supporting_evidence_ids": synthesis.supporting_evidence_ids,
        "missing_information": synthesis.missing_information,
        "evidence": [
            item.model_dump(mode="json") for item in extraction.evidence
        ],
        "cross_validation": contradiction.model_dump(mode="json"),
    }

    user_prompt = (
        "Try to refute the proposed root cause below, then re-judge its "
        "causal_strength and trigger_status.\n\n"
        "Return only JSON matching this schema:\n"
        f"{_compact(ValidationResult.model_json_schema())}\n\n"
        f"Input:\n{_compact(payload)}"
    )

    validation: ValidationResult = _invoke_node(
        state=state,
        node_name="validation",
        system_prompt=VALIDATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_model=ValidationResult,
        schema_name="rca_validation",
        model_name=model_name,
        max_tokens=900,
        max_repairs=max_repairs,
    )

    state["validation"] = validation

    # Capture the before/after verdict and the validator's reasoning so it is
    # observable downstream (surfaced in RCAGenerationResult.metadata and the
    # eval report) rather than being a black box inside the pipeline.
    state["validation_debug"] = {
        "before_causal_strength": synthesis.root_cause.causal_strength,
        "after_causal_strength": validation.adjusted_causal_strength,
        "before_trigger_status": synthesis.trigger_status,
        "after_trigger_status": validation.adjusted_trigger_status,
        "strongest_objection": validation.strongest_objection,
        "rationale": validation.rationale,
        "contradiction_conflicts_with_mechanism": (
            validation.contradiction_conflicts_with_mechanism
        ),
    }

    # The validator is the final authority on how strong the causal claim
    # is: fold its adjusted verdict back into the synthesis result so the
    # downstream confidence calibration and the final report both reflect
    # the post-refutation judgment. Kept immutable via model_copy.
    adjusted_root_cause = synthesis.root_cause.model_copy(
        update={"causal_strength": validation.adjusted_causal_strength}
    )

    state["synthesis"] = synthesis.model_copy(
        update={
            "root_cause": adjusted_root_cause,
            "trigger_status": validation.adjusted_trigger_status,
            "contradiction_conflicts_with_mechanism": (
                synthesis.contradiction_conflicts_with_mechanism
                or validation.contradiction_conflicts_with_mechanism
            ),
        }
    )

    return state


@mlflow_trace(span_type="CHAIN")
def run_action_node(
    state: GraphState,
    *,
    model_name: str,
    max_repairs: int,
) -> GraphState:
    extraction: ExtractionResult = state["extraction"]
    synthesis: SynthesisResult = state["synthesis"]

    payload = {
        "root_cause": (
            synthesis.root_cause.model_dump(mode="json")
            if synthesis.root_cause
            else None
        ),
        "likely_root_cause": synthesis.likely_root_cause,
        "entity_glossary": extraction.entity_glossary,
        "missing_information": synthesis.missing_information,
    }

    user_prompt = (
        "Write recommended remediation actions for the root cause "
        "below.\n\n"
        "Return only JSON matching this schema:\n"
        f"{_compact(ActionResult.model_json_schema())}\n\n"
        f"Input:\n{_compact(payload)}"
    )

    state["actions"] = _invoke_node(
        state=state,
        node_name="actions",
        system_prompt=ACTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_model=ActionResult,
        schema_name="rca_actions",
        model_name=model_name,
        max_tokens=700,
        max_repairs=max_repairs,
    )

    return state
