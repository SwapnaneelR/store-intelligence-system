from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Store Intelligence API"
    app_version: str = "1.0.0"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/store_intelligence"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"

    log_level: str = "INFO"
    log_format: str = "json"  # json | console

    pagination_default_limit: int = 50
    pagination_max_limit: int = 500

    dwell_threshold_seconds: int = 10
    anomaly_loiter_threshold_seconds: int = 300
    group_proximity_px: int = 80
    group_time_window_seconds: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
