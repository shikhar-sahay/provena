"""Deployment configuration validation tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def settings(**values):
    return Settings(_env_file=None, **values)


def test_local_defaults_remain_development_compatible():
    configured = settings()
    assert configured.evidence_storage_backend == "local"
    assert configured.llm_enabled is False


def test_s3_requires_bucket_and_region():
    with pytest.raises(ValidationError):
        settings(evidence_storage_backend="s3")
    configured = settings(
        evidence_storage_backend="s3",
        s3_evidence_bucket="private-evidence",
        aws_region="us-east-1",
    )
    assert configured.s3_evidence_bucket == "private-evidence"


@pytest.mark.parametrize(
    "values",
    [
        {"app_env": "production"},
        {"app_env": "production", "database_url": "postgresql://db"},
        {
            "app_env": "production",
            "database_url": "postgresql://db",
            "secret_key": "a-production-secret-that-is-long-enough",
            "cors_origins": "*",
        },
        {
            "app_env": "production",
            "database_url": "postgresql://db",
            "secret_key": "short",
        },
        {
            "app_env": "production",
            "database_url": "postgresql://db",
            "secret_key": "a-production-secret-that-is-long-enough",
            "trusted_proxy_ips": "*",
        },
    ],
)
def test_production_rejects_missing_or_permissive_configuration(values):
    with pytest.raises(ValidationError):
        settings(**values)


def test_valid_production_configuration_loads():
    configured = settings(
        app_env="production",
        database_url="postgresql://db",
        secret_key="a-production-secret-that-is-not-the-default",
        cors_origins="https://example.cloudfront.net",
    )
    assert configured.app_env == "production"


def test_unknown_environment_is_rejected():
    with pytest.raises(ValidationError):
        settings(app_env="prod")
