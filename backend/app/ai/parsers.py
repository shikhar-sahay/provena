"""Bounded parsers with separate scan text, display excerpts and coverage."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

PARSER_VERSION = "2.2"
MAX_LINE_CHARS = 10_000
MAX_TEXT_BYTES = MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_JSON_DEPTH = 20
MAX_JSON_LEAVES = MAX_SOURCE_UNITS = 50_000
MAX_SCAN_CHARS = 2_000_000
MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 50
MAX_PDF_STREAM_BYTES = 2 * 1024 * 1024
MAX_PDF_TOTAL_STREAM_BYTES = 10 * 1024 * 1024
MIN_MEANINGFUL_TEXT_CHARS = 20
MAX_CONTEXT_CHARS = 280


class ParserError(Exception):
    """Malformed, oversized or unsupported input, with no usable parse."""
    def __init__(self, message: str, coverage=None):
        super().__init__(message)
        self.coverage = coverage


class NoTextError(ParserError):
    """No machine-readable text; OCR is not implemented."""


@dataclass(frozen=True)
class SourceUnit:
    locator: dict[str, object]
    locator_key: str
    context: str
    text: str | None = None
    field_name: str | None = None
    identity_key: str | None = None

    @property
    def scan_text(self) -> str:
        return self.context if self.text is None else self.text


class ParsedSource(list[SourceUnit]):
    """List-compatible parser result; coverage is persisted with the run."""

    def __init__(self, format_name: str):
        super().__init__()
        self.coverage = {
            "parser_version": PARSER_VERSION, "format": format_name,
            "status": "complete", "units_processed": 0, "characters_scanned": 0,
            "warnings": [], "limits": {"unit_characters": MAX_LINE_CHARS,
                "source_units": MAX_SOURCE_UNITS, "scan_characters": MAX_SCAN_CHARS},
        }

    def warn(self, reason: str) -> None:
        self.coverage["status"] = "partial"
        if reason not in self.coverage["warnings"]:
            self.coverage["warnings"].append(reason)

    def add(self, text: str, locator: dict, key: str, prefix: str = "", field_name=None, identity_key=None) -> bool:
        remaining = MAX_SCAN_CHARS - self.coverage["characters_scanned"]
        if len(self) >= MAX_SOURCE_UNITS or remaining <= 0:
            self.warn("Source unit or total character budget reached; remaining records were not scanned.")
            return False
        scan = text[:min(MAX_LINE_CHARS, remaining)]
        if len(scan) < len(text):
            self.warn("One or more source values exceeded the character budget; only declared prefixes were scanned.")
        locator = {**locator, "scanned_characters": len(scan), "source_characters": len(text),
                   "parser_version": PARSER_VERSION}
        self.append(SourceUnit(locator, key, _bound_context(prefix + scan), scan, field_name, identity_key))
        self.coverage["units_processed"] = len(self)
        self.coverage["characters_scanned"] += len(scan)
        return True


def _bound_context(text: str) -> str:
    single = " ".join(text.split())
    return single if len(single) <= MAX_CONTEXT_CHARS else single[:MAX_CONTEXT_CHARS - 3].rstrip() + "..."


def _decode(data: bytes, out: ParsedSource, encoding="utf-8") -> str:
    out.coverage["encoding"] = encoding
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        out.warn("Invalid UTF-8 bytes replaced; offsets refer to decoded text, not original byte offsets.")
        out.coverage["decoding_replacements"] = True
        return data.decode(encoding, errors="replace")


def _parse_lines(data: bytes, log: bool) -> ParsedSource:
    if len(data) > MAX_TEXT_BYTES:
        raise ParserError("Text exceeds the size limit for analysis.")
    out = ParsedSource("log" if log else "txt")
    text = _decode(data, out)
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or (log and raw.lstrip().startswith("#")):
            continue
        if not out.add(raw, {"kind": "line", "line": number, "record_key": f"line:{number}",
                "offset_basis": "decoded_line_codepoints", "encoding": "utf-8"}, f"line:{number}"):
            break
    if not out:
        raise ParserError("Input contains no non-empty supported records.")
    return out


def parse_text(data: bytes) -> ParsedSource:
    return _parse_lines(data, False)


def parse_log(data: bytes) -> ParsedSource:
    return _parse_lines(data, True)


def parse_csv(data: bytes) -> ParsedSource:
    if len(data) > MAX_TEXT_BYTES:
        raise ParserError("CSV exceeds the size limit for analysis.")
    out = ParsedSource("csv")
    text = _decode(data, out, "utf-8-sig")
    try:
        reader = csv.reader(io.StringIO(text), strict=True)
        headers = next(reader, None)
        if not headers:
            raise ParserError("CSV has no header row.")
        for row_number, row in enumerate(reader, 1):
            if len(row) != len(headers):
                out.warn("CSV row width differs from headers; extra cells have ordinal locators.")
            for index, value in enumerate(row):
                if not value.strip():
                    continue
                header = headers[index] if index < len(headers) else f"column_{index + 1}"
                locator = {"kind": "csv", "row": row_number, "column": header[:100],
                    "column_index": index + 1, "physical_line_end": reader.line_num,
                    "record_key": f"csv:{row_number}", "offset_basis": "decoded_cell_codepoints",
                    "exact_file_offsets": False, "encoding": "utf-8-sig"}
                if not out.add(value, locator, f"csv:{row_number}:{header}", f"{header}: ", header, f"csv:{row_number}:{index + 1}"):
                    return out
    except (csv.Error, OverflowError) as exc:
        raise ParserError("CSV could not be parsed within supported limits.") from exc
    if not out:
        raise ParserError("CSV contains no data cells.")
    return out


def parse_json(data: bytes) -> ParsedSource:
    if len(data) > MAX_JSON_BYTES:
        raise ParserError("JSON exceeds the size limit for analysis.")
    out = ParsedSource("json")
    try:
        def unique_object(pairs):
            out = {}
            for key, value in pairs:
                if key in out:
                    raise ValueError("Duplicate JSON keys")
                out[key] = value
            return out
        def reject_constant(value):
            raise ValueError("Non-standard JSON constant")
        document = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ParserError("JSON is malformed or exceeds supported nesting.") from exc

    def walk(node, path, pointer, depth, parent, field_name=None):
        if len(pointer) > 1000:
            out.warn("JSON path length budget reached; deeper values were not scanned.")
            return True
        if depth > MAX_JSON_DEPTH:
            out.warn("JSON nesting budget reached; deeper values were not scanned.")
            return True
        if isinstance(node, dict):
            for key, value in node.items():
                escaped = key.replace("~", "~0").replace("/", "~1")
                if not walk(value, f"{path}.{key}", f"{pointer}/{escaped}", depth + 1, pointer, key):
                    return False
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if not walk(value, f"{path}[{index}]", f"{pointer}/{index}", depth + 1, pointer):
                    return False
        elif node is not None and not isinstance(node, bool):
            value = str(node)
            if value.strip():
                return out.add(value, {"kind": "json", "path": path[:500], "pointer": pointer[:1000],
                    "record_key": f"json:{parent}", "offset_basis": "decoded_scalar_codepoints",
                    "exact_file_offsets": False, "encoding": "utf-8"},
                    f"json:{path}", f"{path} = ", field_name, f"json:{pointer}")
        return True

    walk(document, "$", "", 0, "")
    if not out:
        raise ParserError("JSON contains no supported scalar values within processing limits.")
    return out


def parse_pdf(data: bytes) -> ParsedSource:
    from pypdf import apply_configuration
    # Public context-local limits, never process-global monkeypatches.
    with apply_configuration(maximum_declared_stream_length=MAX_PDF_BYTES,
            array_based_stream_maximum_output_length=MAX_PDF_STREAM_BYTES,
            zlib_maximum_output_length=MAX_PDF_STREAM_BYTES, lzw_maximum_output_length=MAX_PDF_STREAM_BYTES,
            run_length_maximum_output_length=MAX_PDF_STREAM_BYTES, brotli_maximum_output_length=MAX_PDF_STREAM_BYTES,
            jbig2_maximum_output_length=MAX_PDF_STREAM_BYTES, image_maximum_buffer_size=MAX_PDF_STREAM_BYTES,
            stream_decoding_work_maximum_length=MAX_PDF_TOTAL_STREAM_BYTES,
            stream_parsing_work_maximum_count=100_000, stream_filters_maximum_length=8,
            page_tree_maximum_entries=1_000, page_tree_maximum_depth=30,
            page_tree_maximum_page_entries=20_000, dictionary_maximum_element_count=10_000,
            array_maximum_element_count=50_000, xform_maximum_invocations_per_extraction=10,
            jbig2dec_binary=None, disable_legacy_handling=True):
        return _parse_pdf(data)


def _parse_pdf(data: bytes) -> ParsedSource:
    if len(data) > MAX_PDF_BYTES:
        raise ParserError("PDF exceeds the size limit for analysis.")
    from pypdf import PdfReader
    out = ParsedSource("pdf")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        total = len(reader.pages)
    except Exception as exc:
        raise ParserError("PDF could not be read.") from exc
    out.coverage.update(total_pages=total, page_limit=MAX_PDF_PAGES, processed_pages=[],
                        skipped_pages=[], unprocessed_page_count=max(total - MAX_PDF_PAGES, 0))
    if total > MAX_PDF_PAGES:
        out.warn("PDF page budget reached; pages after the declared limit were not examined.")
    decoded_total = 0
    out.coverage["limits"].update(pdf_stream_bytes=MAX_PDF_STREAM_BYTES, pdf_total_page_stream_bytes=MAX_PDF_TOTAL_STREAM_BYTES)
    for number in range(1, min(total, MAX_PDF_PAGES) + 1):
        try:
            page = reader.pages[number - 1]
            contents = page.get_contents()
            content_size = len(contents.get_data()) if contents is not None else 0
            if content_size > MAX_PDF_STREAM_BYTES:
                raise ValueError("Page content budget exceeded")
            decoded_total += content_size
            if decoded_total > MAX_PDF_TOTAL_STREAM_BYTES:
                out.warn("Total PDF page content budget reached; remaining pages were not examined.")
                out.coverage["unprocessed_page_count"] += min(total, MAX_PDF_PAGES) - number + 1
                if not out:
                    raise NoTextError(NO_TEXT_MESSAGE, coverage=out.coverage)
                return out
            text = page.extract_text() or ""
        except NoTextError:
            raise
        except Exception:
            out.warn("One or more PDF pages could not be extracted within supported limits.")
            out.coverage["skipped_pages"].append({"page": number, "reason": "Page extraction failed or content budget exceeded."})
            continue
        if not text.strip():
            out.warn("One or more PDF pages contain no extractable text; image content was not examined.")
            out.coverage["skipped_pages"].append({"page": number, "reason": "No extractable text; OCR unavailable."})
            continue
        out.coverage["processed_pages"].append(number)
        for line_number, raw in enumerate(text.splitlines(), 1):
            if raw.strip() and not out.add(raw, {"kind": "pdf", "page": number, "line": line_number,
                    "record_key": f"pdf:{number}:{line_number}", "offset_basis": "extracted_line_codepoints",
                    "exact_file_offsets": False}, f"pdf:{number}:{line_number}"):
                out.coverage["unprocessed_page_count"] += min(total, MAX_PDF_PAGES) - number
                return out
    if sum(len(u.scan_text.strip()) for u in out) < MIN_MEANINGFUL_TEXT_CHARS:
        raise NoTextError(NO_TEXT_MESSAGE, coverage=out.coverage)
    return out


PARSERS = {"txt": parse_text, "log": parse_log, "csv": parse_csv, "json": parse_json, "pdf": parse_pdf}
PARSER_BYTE_LIMITS = {"txt": MAX_TEXT_BYTES, "log": MAX_TEXT_BYTES, "csv": MAX_TEXT_BYTES,
                      "json": MAX_JSON_BYTES, "pdf": MAX_PDF_BYTES}
NO_TEXT_MESSAGE = "No machine-readable text was detected in this PDF. OCR processing is not currently supported."
