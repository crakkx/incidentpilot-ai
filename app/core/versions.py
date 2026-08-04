BASELINE_RELEASE_TAG = "v0.1.0"

# Current development version — Phase 2: structured observations, root-cause
# assessment, and expanded eval dataset (25 cases).
PIPELINE_VERSION = "0.3.0-dev.1"

# LangGraph multi-node RCA pipeline: extraction -> cross-validation ->
# synthesis -> action recommendation, plus deterministic confidence
# calibration. Bump this when the node graph or its prompts change.
RCA_GRAPH_PIPELINE_VERSION = "rca-graph/1.0.0"

# Increment this only when the RCAReport structure changes.
# 2.0.0: Added optional `observations` (list[ObservationItem]) and
#        `root_cause` (RootCauseAssessment | None) to RCAReport.
RCA_SCHEMA_VERSION = "rca-report/2.0.0"

# Increment this when RCA prompt instructions meaningfully change.
RCA_PROMPT_VERSION = "rca-prompt/2.0.0"

# Increment this when the evaluation case format changes.
# 2.0.0: Expanded dataset to 25 cases covering all 9 scenario types.
RCA_EVAL_DATASET_VERSION = "rca-eval/2.0.0"
