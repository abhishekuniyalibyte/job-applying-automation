from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Job Assistant"
    database_url: str = "postgresql+psycopg://jobs:jobs@localhost:5432/jobs"

    # LLM
    llm_provider: Literal["openai", "gemini", "fake"] = "openai"
    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str | None = None
    gemini_chat_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"
    embedding_dim: int = 768

    # Adzuna
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    adzuna_country: str = "gb"

    # Tuning
    api_cache_ttl_hours: int = 6
    shortlist_size: int = 25
    stale_job_days: int = 14


@lru_cache
def get_settings() -> Settings:
    return Settings()
