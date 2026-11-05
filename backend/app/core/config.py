"""Environment-based application configuration.

All settings come from environment variables (or a local ``.env`` file).
No secrets are hardcoded here; see ``.env.example`` at the repo root.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import ipaddress
from urllib.parse import urlsplit
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_name: str = "Provena API"
    # Environment label: development | test | production
    app_env: Literal["development", "test", "production"] = "development"
    # Empty means "no database configured" (health endpoint reports it,
    # the app still starts). Production deployments must set this.
    database_url: str = ""
    # Comma-separated origins allowed for browser CORS in development.
    cors_origins: str = "http://localhost:5173"
    # Signing key for JWT access tokens. The default is development-only:
    # set SECRET_KEY in real deployments (see .env.example).
    secret_key: str = "local-dev-only-secret-key-not-for-production"
    # Access token lifetime in minutes.
    access_token_expire_minutes: int = Field(default=480,ge=1,le=1440)
    # Root directory for stored evidence files. Runtime uploads only;
    # never inside the Git repository working tree that gets committed.
    evidence_storage_root: str = Field(default="./evidence-storage",min_length=1)
    evidence_storage_backend: Literal["local", "s3"] = "local"
    s3_evidence_bucket: str = ""
    aws_region: str = ""
    # Maximum accepted upload size in bytes (default 100 MiB).
    evidence_max_upload_bytes: int = Field(default=100 * 1024 * 1024,ge=1,le=2*1024*1024*1024)
    # Optional local narrative generation. Core analysis never depends on it.
    llm_enabled: bool = False
    llm_provider: str = "deterministic"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    llm_timeout_seconds: float = 30.0
    # Comma-separated proxy IPs or CIDRs allowed to supply forwarding headers.
    trusted_proxy_ips: str = ""
    export_storage_root: str = "./export-storage"
    export_max_bytes: int = Field(default=512 * 1024 * 1024,ge=4*1024*1024,le=2*1024*1024*1024)
    export_metadata_max_bytes: int = Field(default=32 * 1024 * 1024,ge=65536,le=128*1024*1024)
    export_retention_hours: int = Field(default=24,ge=1,le=168)
    build_id: str = Field(default="development",max_length=80,pattern=r'^[A-Za-z0-9._-]+$')

    @model_validator(mode="after")
    def validate_deployment(self):
        if not self.evidence_storage_root.strip() or not self.export_storage_root.strip():
            raise ValueError('Evidence and export roots must be nonempty private directories.')
        evidence,exports=Path(self.evidence_storage_root).resolve(),Path(self.export_storage_root).resolve()
        if self.evidence_storage_backend=='local' and (evidence==exports or evidence in exports.parents or exports in evidence.parents):
            raise ValueError('Evidence and export roots must be separate and non-nested.')
        if self.export_metadata_max_bytes>self.export_max_bytes:
            raise ValueError('Export metadata budget must fit the package budget.')
        if self.evidence_storage_backend not in {"local", "s3"}:
            raise ValueError("EVIDENCE_STORAGE_BACKEND must be local or s3.")
        if self.evidence_storage_backend == "s3" and (
            not self.s3_evidence_bucket or not self.aws_region
        ):
            raise ValueError("S3_EVIDENCE_BUCKET and AWS_REGION are required for S3 storage.")
        if self.app_env == "production":
            if not self.database_url or "replace-me" in self.database_url:
                raise ValueError("DATABASE_URL is required in production.")
            if (
                len(self.secret_key) < 32
                or len(set(self.secret_key)) < 12
                or self.secret_key == "local-dev-only-secret-key-not-for-production"
                or self.secret_key.startswith("replace-")
            ):
                raise ValueError("SECRET_KEY must be a non-placeholder value of at least 32 characters.")
            origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
            if "*" in origins or any("replace-" in item for item in origins):
                raise ValueError("Wildcard or placeholder CORS origins are not allowed in production.")
            for origin in origins:
                parsed=urlsplit(origin)
                if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                    raise ValueError('Production CORS origins require exact HTTPS origins without paths or credentials.')
            if not self.database_url.startswith(('postgresql://','postgresql+psycopg2://','postgresql+psycopg://')):
                raise ValueError('Production DATABASE_URL requires PostgreSQL.')
            if "*" in [item.strip() for item in self.trusted_proxy_ips.split(",")]:
                raise ValueError("TRUSTED_PROXY_IPS cannot trust every address in production.")
            for proxy in self.trusted_proxy_ips.split(','):
                if proxy.strip():
                    try: network=ipaddress.ip_network(proxy.strip(),strict=False)
                    except ValueError: raise ValueError('Trusted proxies require explicit IP addresses or CIDRs.') from None
                    if network.prefixlen==0: raise ValueError('Trusted proxies cannot trust all addresses.')
            if self.evidence_storage_backend == "s3" and self.s3_evidence_bucket.startswith(
                "replace-"
            ):
                raise ValueError("S3_EVIDENCE_BUCKET cannot be a placeholder in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
