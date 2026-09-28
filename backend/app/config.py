from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="JQA_", extra="ignore")

    # Defaults to a local SQLite file so the app runs without Docker/Postgres
    # for development and tests. docker-compose overrides this to Postgres.
    database_url: str = "sqlite:///./jqa_dev.db"

    data_dir: Path = Path("./data")

    # Azure OpenAI (used by the AI orchestration layer; unset = AI stage is skipped)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment_fast: str = ""
    azure_openai_deployment_reasoning: str = ""

    worker_poll_interval_seconds: float = 2.0
    ai_circuit_breaker_failure_rate: float = 0.2

    retention_days: int = 90


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
