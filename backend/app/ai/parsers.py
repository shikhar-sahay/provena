"""Format parsers: stored evidence bytes become normalized source units.

Every unit preserves provenance (line, row/column, JSON path, or PDF page)
and a bounded context excerpt. Parsers never execute content: they read text,
CSV rows, JSON values, and PDF text runs. Pathological inputs are bounded by
explicit limits; oversized or malformed inputs fail with structured errors
instead of consuming unbounded resources.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

# Parser resource limits. Registration still accepts up to 100 MiB; these cap
# what a single analysis pass will chew through, with explicit per-evidence
# failure instead of silent truncation.
MAX_LINE_CHARS = 10_000
MAX_TEXT_BYTES = 10 * 1024 * 1024
MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_JSON_DEPTH = 20
MAX_JSON_LEAVES = 50_000
MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 50
MIN_MEANINGFUL_TEXT_CHARS = 20
MAX_CONTEXT_CHARS = 280


class ParserError(Exception):
    """A file could not be parsed safely (malformed, oversized, unsupported)."""


class NoTextError(ParserError):
    """No machine-readable text could be extracted (e.g. scanned-only PDF)."""


@dataclass(frozen=True)
class SourceUnit:
    """One addressable slice of evidence content with provenance and context."""

    locator: dict[str, object]
    locator_key: str
    context: str


def _bound_context(text: str) -> str:
    single = " ".join(text.split())
    if len(single) > MAX_CONTEXT_CHARS:
        return single[:MAX_CONTEXT_CHARS].rstrip() + "..."
    return single


def _bound_line(line: str) -> str:
    if len(line) > MAX_LINE_CHARS:
        return line[:MAX_LINE_CHARS]
    return line


def parse_text(data: bytes) -> list[SourceUnit]:
    """Plain text: one unit per non-blank line, 1-based line numbers."""
    if len(data) > MAX_TEXT_BYTES:
        raise ParserError("Text exceeds the size limit for analysis.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    units = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _bound_line(raw)
        if not line.strip():
            continue
        units.append(
            SourceUnit(
                locator={"kind": "line", "line": number},
                locator_key=f"line:{number}",
                context=_bound_context(line),
            )
        )
    return units


def parse_log(data: bytes) -> list[SourceUnit]:
    """Log text: like plain text, but skips comment and blank lines."""
    if len(data) > MAX_TEXT_BYTES:
        raise ParserError("Log exceeds the size limit for analysis.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    units = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _bound_line(raw)
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        units.append(
            SourceUnit(
                locator={"kind": "line", "line": number},
                locator_key=f"line:{number}",
                context=_bound_context(line),
            )
        )
    return units


def parse_csv(data: bytes) -> list[SourceUnit]:
    """CSV: one unit per (data row, non-empty column). Rows are 1-based."""
    if len(data) > MAX_TEXT_BYTES:
        raise ParserError("CSV exceeds the size limit for analysis.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("utf-8-sig", errors="replace")
    try:
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames
        if not headers:
            raise ParserError("CSV has no header row.")
    except csv.Error as exc:
        raise ParserError(f"CSV could not be parsed: {exc}") from exc
    units = []
    try:
        for row_number, row in enumerate(reader, start=1):
            if row is None:
                continue
            for column, value in row.items():
                if column is None or value is None:
                    continue
                cell = _bound_line(str(value))
                if not cell.strip():
                    continue
                header = str(column).strip() or "column"
                units.append(
                    SourceUnit(
                        locator={"kind": "csv", "row": row_number, "column": header},
                        locator_key=f"csv:{row_number}:{header}",
                        context=_bound_context(f"{header}: {cell}"),
                    )
                )
    except csv.Error as exc:
        raise ParserError(f"CSV could not be parsed: {exc}") from exc
    if not units:
        raise ParserError("CSV contains no data cells.")
    return units


def _walk_json(node: object, path: str, depth: int, out: list[SourceUnit]) -> None:
    if len(out) >= MAX_JSON_LEAVES:
        raise ParserError("JSON exceeds the leaf limit for analysis.")
    if depth > MAX_JSON_DEPTH:
        raise ParserError("JSON exceeds the nesting limit for analysis.")
    if isinstance(node, dict):
        for key, value in node.items():
            _walk_json(value, f"{path}.{key}", depth + 1, out)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_json(value, f"{path}[{index}]", depth + 1, out)
    elif node is None or isinstance(node, bool):
        return
    elif isinstance(node, (str, int, float)):
        raw = _bound_line(str(node))
        if not raw.strip():
            return
        out.append(
            SourceUnit(
                locator={"kind": "json", "path": path},
                locator_key=f"json:{path}",
                context=_bound_context(f"{path} = {raw}"),
            )
        )


def parse_json(data: bytes) -> list[SourceUnit]:
    """JSON: one unit per scalar leaf with a JSONPath-like locator."""
    if len(data) > MAX_JSON_BYTES:
        raise ParserError("JSON exceeds the size limit for analysis.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParserError("JSON is not valid UTF-8 text.") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParserError(f"JSON could not be parsed: {exc}") from exc
    units: list[SourceUnit] = []
    _walk_json(document, "$", 0, units)
    if not units:
        raise ParserError("JSON contains no scalar values.")
    return units


def parse_pdf(data: bytes) -> list[SourceUnit]:
    """PDF: one unit per non-blank text line, with 1-based page numbers.

    Only machine-readable text is handled. Scanned or image-only PDFs yield
    NoTextError with guidance, never silent success. OCR is out of scope.
    """
    if len(data) > MAX_PDF_BYTES:
        raise ParserError("PDF exceeds the size limit for analysis.")
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        pages = reader.pages[:MAX_PDF_PAGES]
    except (PdfReadError, ValueError, IndexError) as exc:
        raise ParserError(f"PDF could not be read: {exc}") from exc
    units = []
    meaningful = 0
    for page_number, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except (PdfReadError, ValueError, IndexError):
            continue
        for line_number, raw in enumerate(text.splitlines(), start=1):
            line = _bound_line(raw)
            if not line.strip():
                continue
            meaningful += len(line.strip())
            units.append(
                SourceUnit(
                    locator={"kind": "pdf", "page": page_number, "line": line_number},
                    locator_key=f"pdf:{page_number}:{line_number}",
                    context=_bound_context(line),
                )
            )
    if meaningful < MIN_MEANINGFUL_TEXT_CHARS:
        raise NoTextError(
            "No machine-readable text was detected in this PDF. "
            "OCR processing is not currently supported."
        )
    return units


PARSERS = {
    "txt": parse_text,
    "log": parse_log,
    "csv": parse_csv,
    "json": parse_json,
    "pdf": parse_pdf,
}

NO_TEXT_MESSAGE = (
    "No machine-readable text was detected in this PDF. "
    "OCR processing is not currently supported."
)
