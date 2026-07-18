from functools import lru_cache

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

    # Retrieval settings
    embedding_model_name: str = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    embedding_dimensions: int = 384
    embedding_cache_dir: str = "/cache/sentence-transformers"

    # Local Ollama settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: float = 240.0
    ollama_keep_alive: str = "10m"
    ollama_num_ctx: int = 8192
    ollama_temperature: float = 0.0
    ollama_num_predict: int = 1800
    ollama_seed: int = 42

    # Limit the evidence sent to the small local model
    rca_max_logs: int = 20
    rca_max_metrics: int = 20
    rca_max_deployments: int = 10
    rca_runbook_top_k: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
