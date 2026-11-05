"""Validated immutable source interpretations and bounded event responses."""
import re
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    adapter: Literal['linux_auth', 'windows_security', 'sysmon']
    format: Literal['syslog', 'json', 'jsonl', 'csv']
    encoding: Literal['utf-8', 'utf-8-sig', 'latin-1'] = 'utf-8'
    source_host: str | None = Field(default=None, min_length=1, max_length=256)
    timezone: str | None = Field(default=None, max_length=64)
    year: int | None = Field(default=None, ge=1970, le=2100)
    timestamp_convention: Literal['source', 'iso8601', 'syslog'] = 'source'

    @field_validator('source_host')
    @classmethod
    def host_value(cls, value):
        if value is not None and (not value.strip() or '\x00' in value):
            raise ValueError('Source host must be nonblank without NUL bytes.')
        return value.strip() if value is not None else None

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        if value is None:
            return value
        if re.fullmatch(r'[+-](?:0\d|1\d|2[0-3]):[0-5]\d', value):
            if value == '-00:00':
                raise ValueError('Negative zero is unknown, not a configured timezone.')
            return value
        try:
            if not re.fullmatch(r'[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*', value):
                raise ValueError('Invalid timezone name.')
            from importlib.resources import files
            with files('tzdata.zoneinfo').joinpath(*value.split('/')).open('rb') as zonefile:
                ZoneInfo.from_file(zonefile, key=value)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError('Unknown IANA timezone or fixed offset.') from exc
        return value

    @model_validator(mode='after')
    def compatible(self):
        if (self.adapter == 'linux_auth') != (self.format == 'syslog'):
            raise ValueError('Linux authentication uses syslog; Windows and Sysmon use structured exports.')
        if self.adapter != 'linux_auth' and self.year is not None:
            raise ValueError('Year assumptions apply only to yearless syslog.')
        if self.adapter != 'linux_auth' and self.timestamp_convention == 'syslog':
            raise ValueError('Structured exports require source or ISO timestamp conventions.')
        return self


class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    configuration: ProfileConfig

    @field_validator('name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or '\x00' in value:
            raise ValueError('Profile name is required.')
        return value.strip()


class ProfileRead(ProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    investigation_id: int
    semantic_key: str
    version: str
    created_at: datetime


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    evidence_id: int = Field(gt=0)
    profile_id: int = Field(gt=0)


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    evidence_id: int
    profile_id: int
    status: str
    input_sha256: str | None
    verification_id: int | None
    adapter_version: str
    normalization_version: str
    coverage: dict
    error: str | None
    created_at: datetime
    completed_at: datetime | None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    investigation_id: int
    evidence_id: int
    first_run_id: int
    profile_id: int
    semantic_key: str
    input_sha256: str
    record_fingerprint: str
    locator: dict
    profile_snapshot: dict
    adapter_version: str
    normalization_version: str
    coverage_status: str
    source_format: str
    provider: str
    category: str
    event_type: str
    outcome: str
    event_id: str | None
    username: str | None
    account_domain: str | None
    hostname: str | None
    source_ip: str | None
    destination_ip: str | None
    source_port: int | None
    destination_port: int | None
    original_timestamp: str | None
    timestamp_utc: datetime | None
    time_semantics: dict
    attributes: dict
    warnings: list[str]
