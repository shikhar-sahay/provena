"""Deterministic pipeline unit tests: parsers, extractors, normalization, correlation.

Pure functions only: no database, no network, no filesystem beyond tmp paths.
"""

import importlib.util
from pathlib import Path

import pytest

from app.ai import correlate, extractors, normalize, parsers
from app.ai.extractors import EXTRACTOR_VERSION, Extraction
from app.ai.parsers import NoTextError, ParserError, SourceUnit

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data"


def _pdf_builder():
    spec = importlib.util.spec_from_file_location(
        "make_access_report", SAMPLE_DATA / "make_access_report.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_text_pdf


def _unit(text: str) -> SourceUnit:
    return SourceUnit(
        locator={"kind": "line", "line": 1}, locator_key="line:1", context=text
    )


def _extracted(text: str) -> set[tuple[str, str, str]]:
    """{(type, raw, normalized)} for valid normalizations of one line."""
    found = set()
    for extractor, extraction in extractors.extract_all(_unit(text)):
        normalized = normalize.normalize(extraction.artifact_type, extraction.raw_value)
        if normalized is not None:
            found.add((extraction.artifact_type, extraction.raw_value, normalized))
    return found


def test_parse_log_skips_comments_and_blanks():
    units = parsers.parse_log(b"# comment\n\n2026-01-12 x=1\n   \n2026-01-12 x=2\n")
    assert [u.locator_key for u in units] == ["line:3", "line:5"]
    assert len(units[0].context) <= parsers.MAX_CONTEXT_CHARS


def test_parse_text_keeps_all_lines():
    units = parsers.parse_text(b"# kept\na\n")
    assert [u.locator_key for u in units] == ["line:1", "line:2"]


def test_parse_csv_rows_and_columns():
    data = b"username,host,notes\nj.smith,WS-17,first\n"
    units = parsers.parse_csv(data)
    by_key = {u.locator_key: u for u in units}
    assert by_key["csv:1:username"].context == "username: j.smith"
    assert by_key["csv:1:host"].context == "host: WS-17"
    assert by_key["csv:1:notes"].context == "notes: first"


def test_parse_csv_rejects_headerless():
    with pytest.raises(ParserError):
        parsers.parse_csv(b"\n\n")


def test_parse_json_paths():
    data = b'{"events": [{"username": "j.smith", "port": 443}], "count": 2}'
    units = parsers.parse_json(data)
    by_key = {u.locator_key: u for u in units}
    assert by_key["json:$.events[0].username"].context == "$.events[0].username = j.smith"
    assert by_key["json:$.events[0].port"].context == "$.events[0].port = 443"
    assert by_key["json:$.count"].context == "$.count = 2"


def test_parse_json_rejects_malformed_and_oversized():
    with pytest.raises(ParserError):
        parsers.parse_json(b"{not json")
    with pytest.raises(ParserError):
        parsers.parse_json(b"x" * (parsers.MAX_JSON_BYTES + 1))


def test_parse_pdf_extracts_pages():
    data = (SAMPLE_DATA / "employee-access-report.pdf").read_bytes()
    units = parsers.parse_pdf(data)
    pages = {u.locator["page"] for u in units}
    assert pages == {1, 2}
    assert all(u.locator["kind"] == "pdf" for u in units)
    assert all(len(u.context) <= parsers.MAX_CONTEXT_CHARS for u in units)


def test_parse_pdf_rejects_scanned_only():
    build = _pdf_builder()
    with pytest.raises(NoTextError) as exc_info:
        parsers.parse_pdf(build([["   "]]))
    assert "OCR" in str(exc_info.value)


def test_parse_pdf_rejects_garbage():
    with pytest.raises(ParserError):
        parsers.parse_pdf(b"this is not a pdf")


def test_ip_extraction_and_canonicalization():
    found = _extracted("from 192.168.001.010 to 192.168.1.10 and 999.1.1.1")
    assert ("IP_ADDRESS", "192.168.1.10", "192.168.1.10") in found
    assert not any(raw in ("192.168.001.010", "999.1.1.1") for _, raw, _ in found)


def test_email_and_username_derivation():
    found = _extracted("contact a.lindqvist@example.com today")
    assert ("EMAIL_ADDRESS", "a.lindqvist@example.com", "a.lindqvist@example.com") in found
    assert ("USERNAME", "a.lindqvist", "a.lindqvist") in found


def test_domain_guards_against_usernames_and_filenames():
    found = _extracted("m.okafor read Q4-roadmap.docx then visited filesync.example.com")
    values = {raw for typ, raw, _ in found if typ == "DOMAIN"}
    assert "m.okafor" not in values
    assert "Q4-roadmap.docx" not in values
    assert "filesync.example.com" in values


def test_workstation_pattern_avoids_filename_fragments():
    found = _extracted("copied vendor-pricing-2026.xlsx on ws-114")
    hosts = {raw for typ, raw, _ in found if typ == "HOSTNAME"}
    assert "pricing-2026" not in hosts
    assert "ws-114" in hosts


def test_key_aware_username_hostname_device():
    found = _extracted("session user=j.smith host=WS-17 device=KINGSTON-USB serial=4C5300X1")
    assert ("USERNAME", "j.smith", "j.smith") in found
    assert ("HOSTNAME", "WS-17", "ws-17") in found
    assert ("USB_DEVICE", "KINGSTON-USB", "KINGSTON-USB") in found
    assert ("USB_DEVICE", "4C5300X1", "4C5300X1") in found


def test_key_aware_rejects_bare_words():
    found = _extracted("usb: device inserted, volume mounted")
    assert not any(typ == "USB_DEVICE" for typ, _, _ in found)


def test_hash_mac_port_timestamp_file_process():
    found = _extracted(
        "hash d41d8cd98f00b204e9800998ecf8427e mac AA-BB-CC-DD-EE-FF "
        "host=db:5432 proc svchost.exe at 2026-01-13 02:15:01 file Q4-Forecast.xlsx"
    )
    assert ("HASH", "d41d8cd98f00b204e9800998ecf8427e", "d41d8cd98f00b204e9800998ecf8427e") in found
    assert ("MAC_ADDRESS", "AA-BB-CC-DD-EE-FF", "aa:bb:cc:dd:ee:ff") in found
    assert ("PORT", "5432", "5432") in found
    assert ("PROCESS_NAME", "svchost.exe", "svchost.exe") in found
    assert ("TIMESTAMP", "2026-01-13 02:15:01", "2026-01-13T02:15:01+00:00") in found
    assert ("FILE_NAME", "Q4-Forecast.xlsx", "Q4-Forecast.xlsx") in found


def test_time_like_text_is_not_a_port():
    found = _extracted("at 12:30 the job ran")
    assert not any(typ == "PORT" for typ, _, _ in found)


def test_url_conservative_normalization():
    found = _extracted("see https://Example.COM/Path?q=1.")
    assert ("URL", "https://Example.COM/Path?q=1.", "https://example.com/Path?q=1") in found


def test_normalize_rejects_invalid():
    assert normalize.normalize("IP_ADDRESS", "999.1.1.1") is None
    assert normalize.normalize("HASH", "xyz") is None
    assert normalize.normalize("PORT", "70000") is None
    assert normalize.normalize("TIMESTAMP", "not a date") is None
    assert normalize.normalize("MAC_ADDRESS", "AA:BB:CC") is None
    assert normalize.normalize("UNKNOWN_TYPE", "x") is None


def test_extractor_version_pinned():
    assert EXTRACTOR_VERSION == "1"
    assert all(e.name for e in extractors.EXTRACTORS)


def test_correlation_requires_distinct_evidence():
    rows = [
        (1, 10, "USERNAME", "j.smith"),
        (2, 10, "USERNAME", "j.smith"),
        (3, 11, "USERNAME", "j.smith"),
        (4, 12, "HOSTNAME", "ws-17"),
    ]
    result = correlate.build_correlations(rows)
    assert len(result) == 1
    entry = result[0]
    assert entry["artifact_type"] == "USERNAME"
    assert entry["normalized_value"] == "j.smith"
    assert entry["artifact_ids"] == [1, 2, 3]
    assert entry["evidence_ids"] == [10, 11]


def test_correlation_ordering_deterministic():
    rows = [
        (1, 10, "USERNAME", "b"),
        (2, 11, "USERNAME", "b"),
        (3, 10, "USERNAME", "a"),
        (4, 11, "USERNAME", "a"),
    ]
    result = correlate.build_correlations(rows)
    assert [(c["artifact_type"], c["normalized_value"]) for c in result] == [
        ("USERNAME", "a"),
        ("USERNAME", "b"),
    ]
