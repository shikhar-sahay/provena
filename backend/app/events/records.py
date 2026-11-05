"""Record-aware bounded parsing. Scalar artifacts are never reconstructed as events."""
import csv
import hashlib
import io
import json
from dataclasses import dataclass

PARSER_VERSION = '1'
MAX_BYTES = 10 * 1024 * 1024
MAX_RECORDS = 20_000
MAX_RECORD_CHARS = 32_768
MAX_DEPTH = 16
MAX_NODES = 200_000


class RecordError(ValueError):
    pass


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RecordError('Duplicate structured keys.')
        result[key] = value
    return result


def load_json(text):
    return json.loads(text, object_pairs_hook=unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(RecordError('Non-standard JSON constant.')))


def bounded_shape(document):
    pending = [(document, 0)]
    nodes = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > MAX_DEPTH or nodes > MAX_NODES:
            raise RecordError('Structured nesting or node budget exceeded.')
        if isinstance(value, dict):
            pending.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            pending.extend((v, depth + 1) for v in value)


@dataclass
class SourceRecord:
    value: object
    locator: dict
    fingerprint: str
    error: str | None = None


@dataclass
class RecordBatch:
    records: list[SourceRecord]
    coverage: dict


def parse_records(data: bytes, config: dict) -> RecordBatch:
    if len(data) > MAX_BYTES:
        raise RecordError('Input exceeds the 10 MiB event ingestion budget.')
    try:
        text = data.decode(config['encoding'], errors='strict')
    except UnicodeError as exc:
        raise RecordError('Input does not match the selected encoding.') from exc
    if not text.strip():
        raise RecordError('No source records.')
    fmt = config['format']
    records = []
    coverage = dict(parser_version=PARSER_VERSION, status='complete', records_total=0,
        recognized=0, unrecognized=0, rejected=0, omitted=0, warnings=[],
        limits=dict(bytes=MAX_BYTES, records=MAX_RECORDS, record_characters=MAX_RECORD_CHARS,
                    depth=MAX_DEPTH, nodes=MAX_NODES), encoding=config['encoding'])

    def add(value, locator, raw, error=None):
        coverage['records_total'] += 1
        if len(records) >= MAX_RECORDS:
            coverage['omitted'] += 1
            return
        if len(raw) > MAX_RECORD_CHARS:
            value, error = None, 'Record exceeds the character budget.'
        records.append(SourceRecord(value, {**locator, 'parser_version': PARSER_VERSION,
            'encoding': config['encoding'], 'offset_basis': 'record; exact original byte offsets unavailable'},
            hashlib.sha256(raw.encode('utf-8')).hexdigest(), error))

    try:
        if fmt in ('syslog', 'jsonl'):
            for line_no, line in enumerate(io.StringIO(text), 1):
                raw = line.rstrip('\r\n')
                if not raw.strip() or (fmt == 'syslog' and raw.lstrip().startswith('#')):
                    continue
                if fmt == 'syslog':
                    add(raw, {'kind': 'line', 'line': line_no}, raw)
                elif len(raw) > MAX_RECORD_CHARS:
                    add(None, {'kind': 'line', 'line': line_no}, raw)
                else:
                    try:
                        value = load_json(raw)
                        bounded_shape(value)
                        add(value, {'kind': 'jsonl', 'line': line_no}, raw)
                    except (ValueError, RecursionError):
                        add(None, {'kind': 'jsonl', 'line': line_no}, raw, 'Malformed structured record.')
        elif fmt == 'json':
            doc = load_json(text)
            bounded_shape(doc)
            if isinstance(doc, list):
                values, pointer = doc, ''
            elif isinstance(doc, dict) and set(doc) == {'Events'} and isinstance(doc['Events'], list):
                values, pointer = doc['Events'], '/Events'
            elif isinstance(doc, dict):
                values, pointer = [doc], None
            else:
                raise RecordError('Expected a structured event object or event array.')
            for index, value in enumerate(values):
                add(value, {'kind': 'json', 'pointer': f'{pointer}/{index}' if pointer is not None else ''},
                    json.dumps(value, sort_keys=True, ensure_ascii=True))
        else:
            reader = csv.reader(io.StringIO(text), strict=True)
            headers = next(reader, None)
            if not headers or len(set(headers)) != len(headers) or len(headers) > 100:
                raise RecordError('CSV requires unique headers, at most 100 columns.')
            for index, row in enumerate(reader, 1):
                raw = json.dumps(row, ensure_ascii=True)
                add(dict(zip(headers, row)) if len(row) == len(headers) else None,
                    {'kind': 'csv', 'row': index, 'physical_line_end': reader.line_num}, raw,
                    None if len(row) == len(headers) else 'CSV row width differs from headers.')
    except (ValueError, RecursionError, csv.Error, StopIteration) as exc:
        raise RecordError('Malformed structured input or parser budget exceeded.') from exc
    if not records:
        raise RecordError('No source records.')
    if coverage['omitted']:
        coverage['status'] = 'partial'
        coverage['warnings'].append('Record budget reached; remaining records were omitted.')
    return RecordBatch(records, coverage)
