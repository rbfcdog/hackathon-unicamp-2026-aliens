from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EnterOS"
    environment: str = "development"
    api_prefix: str = "/v1"
    database_url: str = "postgresql+asyncpg://enter-os:enter-os@localhost:5432/EnterOS"
    cors_origins: str = "http://localhost:5173"
    openai_api_key: str = Field(min_length=1)
    openai_model: str = "gpt-5.4-mini"
    model_artifact_path: str = "artifacts/judicial-risk-v5.joblib"
    document_root: str = "../data"
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "enter-os"
    langsmith_endpoint: str | None = None
    langsmith_workspace_id: str | None = None

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def require_openai_api_key(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("OPENAI_API_KEY is required")
        return value.strip()

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def langsmith_enabled(self) -> bool:
        return self.langsmith_tracing and bool(self.langsmith_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
