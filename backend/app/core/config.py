"""Environment-based application configuration.

All settings come from environment variables (or a local ``.env`` file).
No secrets are hardcoded here; see ``.env.example`` at the repo root.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Provena API"
    # Environment label: development | test | production
    app_env: str = "development"
    # Empty means "no database configured" (health endpoint reports it,
    # the app still starts). Production deployments must set this.
    database_url: str = ""
    # Comma-separated origins allowed for browser CORS in development.
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
