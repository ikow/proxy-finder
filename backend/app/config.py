from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./proxies.db"

    # Validation settings
    validation_timeout: int = 10  # seconds
    validation_concurrency: int = 200  # concurrent validations
    validation_test_url: str = "http://httpbin.org/ip"

    # Scheduler settings
    auto_refresh_interval: int = 30  # minutes
    auto_validate_interval: int = 15  # minutes

    # API settings
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5180", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
