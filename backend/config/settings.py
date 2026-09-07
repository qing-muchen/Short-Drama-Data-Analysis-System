"""Typed configuration loaded from environment variables and backend/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Infrastructure settings; values may be overridden by environment variables."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Short Drama Data Management and Analysis System"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = (
        "mysql+pymysql://YOUR_USERNAME:YOUR_PASSWORD@127.0.0.1:3306/"
        "short_drama_analysis?charset=utf8mb4"
    )
    secret_key_placeholder: str = "replace-with-a-local-secret"


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""

    return Settings()
