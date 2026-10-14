"""Typed configuration loaded from environment variables and backend/.env."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
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
    data_quality_legacy_revision_database: str | None = None
    data_quality_legacy_revision_max_id: int | None = Field(default=None, ge=1)
    data_quality_legacy_revision_expected_count: int | None = Field(
        default=None,
        ge=1,
    )
    data_quality_legacy_revision_expected_min_changed_at: datetime | None = None
    data_quality_legacy_revision_expected_max_changed_at: datetime | None = None
    secret_key: SecretStr = Field(min_length=32)
    token_expire_minutes: int = Field(default=30, ge=1, le=1440)

    @model_validator(mode="after")
    def validate_legacy_revision_policy(self) -> "Settings":
        """Require one complete, UTC-naive deployment-specific cutover bundle."""

        values = (
            self.data_quality_legacy_revision_database,
            self.data_quality_legacy_revision_max_id,
            self.data_quality_legacy_revision_expected_count,
            self.data_quality_legacy_revision_expected_min_changed_at,
            self.data_quality_legacy_revision_expected_max_changed_at,
        )
        if all(value is None for value in values):
            return self
        if any(value is None for value in values):
            raise ValueError(
                "all Data Quality legacy revision policy fields are required"
            )
        timestamps = values[-2:]
        if any(value.tzinfo is not None for value in timestamps):  # type: ignore[union-attr]
            raise ValueError(
                "Data Quality legacy revision fingerprint timestamps must be naive"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""

    return Settings()
