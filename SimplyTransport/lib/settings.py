from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Settings class for environment variables."""

    DEBUG: bool = False
    ENVIRONMENT: str = "DEV"
    NAME: str = "SimplyTransport"
    LOG_LEVEL: str = "DEBUG"

    VERSION: str = "1.1.2"  # Version bumping will cache bust static css/js files
    SECRET_KEY: str = "secret"
    LITESTAR_APP: str = "SimplyTransport.app:create_app"

    # Database
    DB_URL: str = "postgresql+asyncpg://user:password@localhost:5432/st_database"
    DB_URL_SYNC: str = "postgresql+psycopg2://user:password@localhost:5432/st_database"
    DB_ECHO: bool = False
    TIMESCALE_URL: str = "postgresql+asyncpg://user:password@localhost:5433/st_ts_database"

    POSTGRES_DB: str = "example"
    POSTGRES_USER: str = "example"
    POSTGRES_PASSWORD: str = "example"

    TIMESCALE_DB: str = "example"
    TIMESCALE_USER: str = "example"
    TIMESCALE_PASSWORD: str = "example"

    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None

    # OpenTelemetry (OTLP/HTTP base URL; paths /v1/traces, /v1/metrics, /v1/logs appended in code)
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://127.0.0.1:4318"

    # GTFS TFI Realtime
    GTFS_TFI_REALTIME_URL: str = "example"
    GTFS_TFI_REALTIME_VEHICLES_URL: str = "example"
    GTFS_TFI_API_KEY_1: str = "example"
    GTFS_TFI_API_KEY_2: str = "example"
    GTFS_TFI_DATASET: str = "example"

    @field_validator("NAME")
    def set_name(cls, v: str, values: ValidationInfo) -> str:  # noqa: N805
        # Appends the environment to the name if not in production
        return (
            v
            if values.data.get("ENVIRONMENT") == "PROD"
            else f"SimplyTransport {values.data.get('ENVIRONMENT')}"
        )

    @field_validator("LOG_LEVEL")
    def set_log_level(cls, v: str, values: ValidationInfo) -> str:  # noqa: N805
        # Sets the log level to DEBUG if in DEV else INFO
        return "DEBUG" if values.data.get("ENVIRONMENT") == "DEV" else "INFO"

    model_config = SettingsConfigDict(env_file=(".env"), extra="ignore")


_app: AppSettings | None = None


def get_settings() -> AppSettings:
    """Return cached settings, created on first use from the current environment."""
    global _app
    if _app is None:
        _app = AppSettings()
    return _app


def reset_settings() -> None:
    """Drop cached settings so the next access re-reads the environment."""
    global _app
    _app = None


def __getattr__(name: str) -> AppSettings:
    if name == "app":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    app = AppSettings()
