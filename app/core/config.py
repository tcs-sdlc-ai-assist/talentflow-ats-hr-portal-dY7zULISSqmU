import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SECRET_KEY: str = "change-me-in-production-use-a-real-secret-key"
    DATABASE_URL: str = "sqlite+aiosqlite:///./talentflow.db"
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    SESSION_MAX_AGE: int = 3600
    ENVIRONMENT: str = "development"
    APP_NAME: str = "TalentFlow ATS"
    DEBUG: bool = False


settings = Settings()