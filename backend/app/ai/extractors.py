"""Deterministic artifact extractors: regexes plus key-aware structured rules.

Every extractor is conservative by design: it prefers false negatives over a
flood of false positives. Usernames, hostnames, and device identifiers are
never guessed from arbitrary tokens; they come from explicit ``key=value``
semantics, structured field names, email local parts, or narrow
workstation-style patterns. No probabilities are attached to matches:
``method`` records ``regex`` or ``structured`` so provenance stays honest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai.parsers import SourceUnit

MAX_RAW_CHARS = 500

# File extensions treated as file names, not DNS domains, when a
# domain-pattern match ends in one of these (e.g. ``report.pdf``).
FILE_EXTENSIONS = frozenset(
    "log txt csv json pdf xml html doc docx xls xlsx ppt pptx "
    "zip 7z rar tar gz msi ps1 bat dll sys evtx ics".split()
)

# Single-label domains (exactly one dot) require a plausible public suffix or
# a substantial first label; otherwise ``m.okafor`` style usernames pollute
# DOMAIN results. Multi-label names pass through (file extensions excluded).
COMMON_TLDS = frozenset(
    "com net org edu gov mil int io co dev app info biz xyz online site tech".split()
)

IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\bhttps?://[^\s<>\"')\]]+")
DOMAIN_RE = re.compile(r"\b(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}\b")
FILE_RE = re.compile(
    r"\b[\w.-]+\.(?:"
    + "|".join(sorted(FILE_EXTENSIONS - {"exe", "dll", "sys", "msi", "ps1", "bat", "evtx"}))
    + r")\b",
    re.IGNORECASE,
)
PROCESS_RE = re.compile(r"\b([A-Za-z][\w-]{1,60})\.exe\b", re.IGNORECASE)
HASH_RE = re.compile(r"\b(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{40}|[0-9a-fA-F]{32})\b")
MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?\b"
    r"|\b\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}\b"
)
WORKSTATION_RE = re.compile(r"(?<![\w.-])[A-Za-z]{1,12}-\d{1,4}\b")
USB_TOKEN_RE = re.compile(r"\b[A-Z0-9-]*USB[A-Z0-9-]*\b", re.IGNORECASE)
PORT_RE = re.compile(r"([\w.\]-]+):(\d{2,5})\b")
KEYVALUE_RE = re.compile(
    r"(?:^|[\s,;])([$A-Za-z_][\w.$\[\]-]*)\s*[:=]\s*(?:\"([^\"]{1,100})\"|'([^']{1,100})'|([^\s,;\"']{1,100}))"
)

# Structured field names mapped to artifact types. Only these keys classify
# values; everything else is ignored (false negatives preferred).
KEY_MAP = {
    "user": "USERNAME",
    "username": "USERNAME",
    "login": "USERNAME",
    "account": "USERNAME",
    "host": "HOSTNAME",
    "hostname": "HOSTNAME",
    "workstation": "HOSTNAME",
    "server": "HOSTNAME",
    "machine": "HOSTNAME",
    "computer": "HOSTNAME",
    "device": "USB_DEVICE",
    "usb": "USB_DEVICE",
    "usb_device": "USB_DEVICE",
    "serial": "USB_DEVICE",
    "serial_number": "USB_DEVICE",
    "serialnumber": "USB_DEVICE",
    "port": "PORT",
    "process": "PROCESS_NAME",
    "process_name": "PROCESS_NAME",
    "image": "PROCESS_NAME",
    "command": "PROCESS_NAME",
    "email": "EMAIL_ADDRESS",
    "mail": "EMAIL_ADDRESS",
    "url": "URL",
    "link": "URL",
    "domain": "DOMAIN",
    "ip": "IP_ADDRESS",
    "ip_address": "IP_ADDRESS",
    "src_ip": "IP_ADDRESS",
    "dst_ip": "IP_ADDRESS",
    "src": "IP_ADDRESS",
    "dst": "IP_ADDRESS",
    "mac": "MAC_ADDRESS",
    "mac_address": "MAC_ADDRESS",
    "file": "FILE_NAME",
    "filename": "FILE_NAME",
    "file_name": "FILE_NAME",
    "path": "FILE_PATH",
    "filepath": "FILE_PATH",
    "file_path": "FILE_PATH",
    "hash": "HASH",
    "md5": "HASH",
    "sha1": "HASH",
    "sha256": "HASH",
    "checksum": "HASH",
    "time": "TIMESTAMP",
    "date": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "datetime": "TIMESTAMP",
}

USERNAME_VALUE_RE = re.compile(r"^[A-Za-z0-9._-]{2,64}$")
HOSTNAME_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{1,63}$")
USB_VALUE_RE = re.compile(r"^[A-Za-z0-9._-]{4,64}$")


def _usb_value_ok(value: str) -> bool:
    """Bare words like ``device`` or ``volume`` are not device identifiers."""
    if not USB_VALUE_RE.match(value):
        return False
    lowered = value.casefold()
    return any(c.isdigit() or c in "-_." for c in lowered) or len(lowered) >= 8


def _field_name(key: str) -> str:
    """Last dotted segment of a key or JSON path, without array indices."""
    segment = key.split(".")[-1]
    segment = re.sub(r"\[\d+\]$", "", segment)
    return segment.casefold().lstrip("$")


def _key_aware_extractions(text: str) -> list[tuple[str, str, tuple[int, int] | None]]:
    found = []
    for match in KEYVALUE_RE.finditer(text):
        key = match.group(1)
        group_index = next(i for i, g in enumerate(match.groups()[1:], start=2) if g is not None)
        value = match.group(group_index).strip()
        span = match.span(group_index)
        if not value:
            continue
        artifact_type = KEY_MAP.get(_field_name(key))
        if artifact_type is None:
            continue
        if artifact_type == "USERNAME" and not USERNAME_VALUE_RE.match(value):
            continue
        if artifact_type == "HOSTNAME":
            if not HOSTNAME_VALUE_RE.match(value):
                continue
            lowered = value.casefold()
            if not any(c.isdigit() or c in ".-" for c in lowered):
                continue
        if artifact_type == "USB_DEVICE" and not _usb_value_ok(value):
            continue
        if artifact_type == "FILE_PATH" and "/" not in value and "\\" not in value:
            artifact_type = "FILE_NAME"
        found.append((artifact_type, value, span))
    return found


@dataclass(frozen=True)
class Extraction:
    artifact_type: str
    raw_value: str
    # Character offsets of the raw value within the unit context, where
    # available. Used for positional checks (e.g. upload destinations); the
    # locator_key remains the stable dedup identity.
    span: tuple[int, int] | None = None


@dataclass(frozen=True)
class Extractor:
    name: str
    method: str
    run: object = field(repr=False)

    def extract(self, unit: SourceUnit) -> list[Extraction]:
        seen: set[tuple[str, str]] = set()
        out = []
        for item in self.run(unit):  # type: ignore[operator]
            if len(item) == 3:
                artifact_type, raw, span = item
            else:
                artifact_type, raw = item
                span = None
            raw = raw.strip()
            if not raw or len(raw) > MAX_RAW_CHARS:
                continue
            key = (artifact_type, raw)
            if key in seen:
                continue
            seen.add(key)
            out.append(Extraction(artifact_type, raw, span))
        return out


def _regex_extractor(pattern: re.Pattern[str], artifact_type: str):
    def run(unit: SourceUnit):
        return [
            (artifact_type, m.group(0), (m.start(), m.end()))
            for m in pattern.finditer(unit.context)
        ]

    return run


def _domain_run(unit: SourceUnit):
    for match in DOMAIN_RE.finditer(unit.context):
        value = match.group(0)
        labels = value.split(".")
        tld = labels[-1].casefold()
        if tld in FILE_EXTENSIONS:
            continue
        if len(labels) == 2 and len(labels[0]) < 3 and tld not in COMMON_TLDS:
            continue
        yield ("DOMAIN", value, (match.start(), match.end()))


def _usb_token_run(unit: SourceUnit):
    for match in USB_TOKEN_RE.finditer(unit.context):
        value = match.group(0)
        if len(value) < 5:
            continue
        yield ("USB_DEVICE", value, (match.start(), match.end()))


def _port_run(unit: SourceUnit):
    for match in PORT_RE.finditer(unit.context):
        host, port = match.group(1), match.group(2)
        if not any(c.isalpha() or c in ".-" for c in host):
            continue
        start, end = match.span(2)
        yield ("PORT", port, (start, end))


def _email_username_run(unit: SourceUnit):
    for match in EMAIL_RE.finditer(unit.context):
        local = match.group(0).split("@", 1)[0]
        if USERNAME_VALUE_RE.match(local):
            end = match.start() + len(local)
            yield ("USERNAME", local, (match.start(), end))


def _keyvalue_run(unit: SourceUnit):
    yield from _key_aware_extractions(unit.context)


EXTRACTORS: list[Extractor] = [
    Extractor("ip-pattern", "regex", _regex_extractor(IP_RE, "IP_ADDRESS")),
    Extractor("email-pattern", "regex", _regex_extractor(EMAIL_RE, "EMAIL_ADDRESS")),
    Extractor("email-username", "structured", _email_username_run),
    Extractor("url-pattern", "regex", _regex_extractor(URL_RE, "URL")),
    Extractor("domain-pattern", "regex", _domain_run),
    Extractor("file-pattern", "regex", _regex_extractor(FILE_RE, "FILE_NAME")),
    Extractor("process-pattern", "regex", _regex_extractor(PROCESS_RE, "PROCESS_NAME")),
    Extractor("hash-pattern", "regex", _regex_extractor(HASH_RE, "HASH")),
    Extractor("mac-pattern", "regex", _regex_extractor(MAC_RE, "MAC_ADDRESS")),
    Extractor("timestamp-pattern", "regex", _regex_extractor(TIMESTAMP_RE, "TIMESTAMP")),
    Extractor("workstation-pattern", "regex", _regex_extractor(WORKSTATION_RE, "HOSTNAME")),
    Extractor("usb-token-pattern", "regex", _usb_token_run),
    Extractor("port-pattern", "regex", _port_run),
    Extractor("keyvalue-pattern", "structured", _keyvalue_run),
]

EXTRACTOR_VERSION = "1"


def extract_all(unit: SourceUnit) -> list[tuple[Extractor, Extraction]]:
    """Run every extractor over one source unit."""
    results = []
    for extractor in EXTRACTORS:
        for extraction in extractor.extract(unit):
            results.append((extractor, extraction))
    return results
