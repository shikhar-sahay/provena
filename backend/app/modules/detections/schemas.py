"""Validated bounded selection and deterministic rule configuration."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventSetCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=100)
    run_ids: list[int] = Field(min_length=1,max_length=50)

    @field_validator('run_ids')
    @classmethod
    def valid_ids(cls, values):
        if any(v <= 0 for v in values):
            raise ValueError('Run identifiers must be positive.')
        return sorted(set(values))

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        if not value.strip() or '\x00' in value:
            raise ValueError('A nonblank name without NUL bytes is required.')
        return value.strip()


class DetectionConfig(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False)
    window_seconds: int = Field(default=300,ge=10,le=86400)
    min_failures: int = Field(default=5,ge=2,le=1000)
    min_occurrences: int = Field(default=5,ge=2,le=1000)
    grouping: Literal['account_host','account_host_source','host'] = 'account_host'
    spray_min_accounts: int = Field(default=5,ge=2,le=1000)
    spray_max_per_account: int = Field(default=3,ge=1,le=100)
    lockout_min_events: int = Field(default=3,ge=2,le=1000)
    lockout_min_accounts: int = Field(default=2,ge=1,le=1000)
    burst_min_attempts: int = Field(default=20,ge=5,le=1000)
    burst_min_accounts: int = Field(default=3,ge=2,le=1000)
    burst_min_failure_fraction: float = Field(default=0.5,ge=0.1,le=1)
    allow_assumed_time: bool = False
    clock_uncertainty_seconds: int = Field(default=1,ge=0,le=300)
    result_limit: int = Field(default=100,ge=1,le=200)


class DetectionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_set_id: int = Field(gt=0)
    configuration: DetectionConfig = Field(default_factory=DetectionConfig)
