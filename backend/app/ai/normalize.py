"""Artifact normalization: type-specific, conservative canonical forms.

Correlation matches on normalized values, so normalization must never merge
distinct entities. Rules per type:

- USERNAME: casefold. ``J.SMITH`` and ``j.smith`` are the same account.
- HOSTNAME: casefold. ``WS-17`` and ``ws-17`` are the same machine.
- EMAIL_ADDRESS / DOMAIN: casefold the whole value. DNS and mailbox domains
  are case-insensitive; local parts are casefolded as a documented,
  conservative choice for correlation (distinct-case local parts are
  vanishingly rare in investigative data).
- IP_ADDRESS: canonical ``ipaddress`` form. Octets with leading zeros are
  rejected (the standard library treats them as ambiguous), as is any other
  invalid input.
- URL: lowercase scheme and host only; path, query, and fragment keep their
  case and content. Trailing sentence punctuation is stripped.
- FILE_PATH: strip only. Platform and case semantics vary, so paths are
  never casefolded or separator-rewritten.
- FILE_NAME: strip only, for the same reason as paths.
- HASH: lowercase hexadecimal. Non-hex or wrong-length input is rejected.
- USB_DEVICE: strip only. Serial and vendor strings are opaque identifiers.
- TIMESTAMP: UTC only when the source explicitly states an offset. Naive
  values retain local wall time without an offset; original precision and
  timezone uncertainty are recorded separately. Unparseable input is rejected.
- PORT: integer 1-65535 as a string. Out-of-range input is rejected.
- MAC_ADDRESS: lowercase colon-separated octets. Invalid input is rejected.
- PROCESS_NAME: casefold the basename. ``SVCHOST.EXE`` and ``svchost.exe``
  are the same binary name on the platforms Provena targets.

``normalize`` returns ``None`` for values that fail validation, and the
pipeline skips them instead of persisting junk.
"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone


def _strip(raw: str) -> str:
    return raw.strip()


def _lower(raw: str) -> str | None:
    value = raw.strip().casefold()
    return value or None


def _normalize_ip(raw: str) -> str | None:
    try:
        return str(ipaddress.ip_address(raw.strip()))
    except ValueError:
        return None


def _normalize_url(raw: str) -> str | None:
    value = raw.strip().rstrip(".,;:!?)]}")
    scheme, separator, rest = value.partition("://")
    if not separator or not rest:
        return None
    host, slash, remainder = rest.partition("/")
    host = host.casefold()
    if not host:
        return None
    normalized = f"{scheme.casefold()}://{host}"
    if slash:
        normalized += f"/{remainder}"
    return normalized or None


def _normalize_hash(raw: str) -> str | None:
    value = raw.strip().casefold()
    if len(value) not in (32, 40, 64):
        return None
    if any(char not in "0123456789abcdef" for char in value):
        return None
    return value


TIMESTAMP_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M%z",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S %z",
)


def timestamp_details(raw: str) -> dict | None:
    """Preserve wall-clock uncertainty; never infer a source timezone or DST fold."""
    original = raw.strip()
    fraction = re.search(r"\d{2}:\d{2}:\d{2}\.(\d+)", original)
    if fraction and len(fraction[1]) > 6:
        return None  # No silent nanosecond-to-microsecond truncation.
    value = re.sub(r"[Zz]$", "+00:00", original)
    parsed = None
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            pass
    if parsed is None:
        for fmt in TIMESTAMP_FORMATS:
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    offset = re.search(r"(Z|z|[+-]\d{2}:?\d{2})$", original)
    # RFC 3339 negative zero explicitly means an unknown local offset.
    known = parsed.tzinfo is not None and not original.endswith(("-00:00", "-0000"))
    utc = parsed.astimezone(timezone.utc).isoformat() if known else None
    normalized = utc if known else parsed.replace(tzinfo=None).isoformat()
    return {"original": original, "timezone_status": "explicit_offset" if known else "unknown",
        "source_offset": offset[0] if offset else None, "utc": utc,
        "normalized_value": normalized, "precision": (f"fraction_{len(fraction[1])}" if fraction
            else "second" if re.search(r"\d{2}:\d{2}:\d{2}", original) else "minute"),
        "normalization_version": "2"}


def _normalize_timestamp(raw: str) -> str | None:
    details = timestamp_details(raw)
    return details["normalized_value"] if details else None


def _normalize_port(raw: str) -> str | None:
    value = raw.strip()
    if not value.isdigit():
        return None
    number = int(value)
    if not 1 <= number <= 65535:
        return None
    return str(number)


def _normalize_mac(raw: str) -> str | None:
    value = raw.strip().casefold().replace("-", ":")
    octets = value.split(":")
    if len(octets) != 6:
        return None
    if any(len(part) != 2 or any(c not in "0123456789abcdef" for c in part) for part in octets):
        return None
    return value


NORMALIZERS = {
    "IP_ADDRESS": _normalize_ip,
    "EMAIL_ADDRESS": _lower,
    "USERNAME": _lower,
    "HOSTNAME": _lower,
    "DOMAIN": _lower,
    "FILE_PATH": _strip,
    "FILE_NAME": _strip,
    "HASH": _normalize_hash,
    "USB_DEVICE": _strip,
    "TIMESTAMP": _normalize_timestamp,
    "URL": _normalize_url,
    "PORT": _normalize_port,
    "MAC_ADDRESS": _normalize_mac,
    "PROCESS_NAME": _lower,
}


def normalize(artifact_type: str, raw: str) -> str | None:
    """Canonical form for an artifact value, or None when invalid."""
    normalizer = NORMALIZERS.get(artifact_type)
    if normalizer is None:
        return None
    result = normalizer(raw)
    if not result or len(result) > 500:
        return None
    return result
