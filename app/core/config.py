from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IncidentPilot AI"
    app_version: str = "0.9.0"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg://incidentpilot:incidentpilot@localhost:5432/incidentpilot"
    )
    test_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    log_level: str = "INFO"

    # LLM provider
    llm_provider: str = "mistral"

    # Retrieval settings
    embedding_model_name: str = (
        "BAAI/bge-small-en-v1.5"
    )
    embedding_dimensions: int = 384
    embedding_cache_dir: str = "/cache/sentence-transformers"

    # Hosted Mistral settings
    mistral_api_key: SecretStr | None = None
    mistral_base_url: str = "https://api.mistral.ai"
    mistral_model: str = "mistral-small-latest"
    mistral_timeout_seconds: float = 240.0
    mistral_temperature: float = 0.0
    mistral_max_tokens: int = 1800
    mistral_random_seed: int = 42

    # Web Search settings (Tavily)
    tavily_api_key: SecretStr | None = None

    # Limit the evidence sent to the small local model
    rca_max_logs: int = 20
    rca_max_metrics: int = 20
    rca_max_deployments: int = 10
    rca_runbook_top_k: int = 5

    # RCA generation pipeline uses a LangGraph multi-node graph (extraction -> 
    # cross-validation -> synthesis -> action recommendation), with deterministic 
    # confidence calibration and a shared, bounded schema-repair budget.

    # Max total node-level schema-validation repairs shared across one graph
    # run. Nominal calls = 4 (one per node); worst case = 4 + this value.
    rca_graph_max_repairs: int = 3

    # Max tool-call investigation rounds before the agent is forced to synthesise.
    # Each round costs 0 extra LLM calls (tool selection is deterministic).
    rca_agent_max_rounds: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
