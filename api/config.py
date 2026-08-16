"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # min_length=1 so a blank JWT_SECRET_KEY= (as shipped in .env.example) fails
    # fast at startup instead of signing tokens with an empty secret.
    jwt_secret_key: str = Field(..., min_length=1)
    jwt_expiry_hours: int = 48
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "openai/gpt-4.1"
    deepgram_api_key: str = ""
    database_path: str = "database/english_tutor.db"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8501"]
    )
    retention_days: int = 5
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    daily_message_limit: int = 20
    daily_voice_call_limit: int = 20

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def apply_to_environ(self) -> None:
        """Sync settings into os.environ for legacy service modules."""
        import os

        os.environ["OPENROUTER_API_KEY"] = self.openrouter_api_key
        os.environ["OPENROUTER_BASE_URL"] = self.openrouter_base_url
        os.environ["DEFAULT_MODEL"] = self.default_model
        os.environ["DEEPGRAM_API_KEY"] = self.deepgram_api_key
        os.environ["DATABASE_PATH"] = self.database_path
        os.environ["RETENTION_DAYS"] = str(self.retention_days)


@lru_cache
def get_settings() -> Settings:
    return Settings()
