import hashlib
import json
from typing import Any

from app.core.config import settings
from app.core.versions import (
    PIPELINE_VERSION,
    RCA_PROMPT_VERSION,
    RCA_SCHEMA_VERSION,
)
from app.llm.prompts import RCA_SYSTEM_PROMPT
from app.rag.chunking import (
    DEFAULT_MAX_WORDS,
    DEFAULT_OVERLAP_WORDS,
)
from app.schemas.analysis import RCAReport


def _sha256_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def build_analysis_run_metadata() -> dict[str, Any]:
    schema = RCAReport.model_json_schema()

    run_config = {
        "pipeline_version": PIPELINE_VERSION,
        "schema_version": RCA_SCHEMA_VERSION,
        "prompt_version": RCA_PROMPT_VERSION,
        "llm": {
            "runtime": "ollama",
            "model": settings.ollama_model,
            "temperature": settings.ollama_temperature,
            "num_ctx": settings.ollama_num_ctx,
            "num_predict": settings.ollama_num_predict,
            "seed": settings.ollama_seed,
        },
        "retrieval": {
            "embedding_model": (
                settings.embedding_model_name
            ),
            "embedding_dimensions": (
                settings.embedding_dimensions
            ),
            "runbook_top_k": (
                settings.rca_runbook_top_k
            ),
            "chunk_max_words": DEFAULT_MAX_WORDS,
            "chunk_overlap_words": (
                DEFAULT_OVERLAP_WORDS
            ),
        },
        "evidence_limits": {
            "logs": settings.rca_max_logs,
            "metrics": settings.rca_max_metrics,
            "deployments": (
                settings.rca_max_deployments
            ),
            "runbook_chunks": (
                settings.rca_runbook_top_k
            ),
        },
        "integrity": {
            "prompt_sha256": _sha256_text(
                RCA_SYSTEM_PROMPT
            ),
            "schema_sha256": _sha256_text(
                _stable_json(schema)
            ),
        },
    }

    return {
        "pipeline_version": PIPELINE_VERSION,
        "schema_version": RCA_SCHEMA_VERSION,
        "prompt_version": RCA_PROMPT_VERSION,
        "run_config": run_config,
    }