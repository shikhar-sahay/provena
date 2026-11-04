"""Synthetic coverage and decoded source coordinate regression tests."""
import json
import pytest
from app.ai import parsers, extractors
from app.ai.normalize import normalize


def ips(unit):
    return [x for _, x in extractors.extract_all(unit) if x.artifact_type == "IP_ADDRESS" and normalize("IP_ADDRESS", x.raw_value)]


@pytest.mark.parametrize('ending', ['\n', '\r\n'])
def test_long_unicode_line_repeated_occurrences(ending):
    text = '界é '*120 + '192.0.2.1 then 192.0.2.1 and 203.0.113.5'
    result = parsers.parse_text((text + ending).encode())
    found = ips(result[0])
    assert len(found) == 3
    assert all(text[x.span[0]:x.span[1]] == x.raw_value for x in found)
    assert found[0].span[0] > 280
    assert len(result[0].context) <= 280
    assert result[0].locator['offset_basis'] == 'decoded_line_codepoints'
    assert result.coverage['status'] == 'complete'


def test_structured_coordinates_are_decoded_values_not_file_offsets():
    csv = parsers.parse_csv('username,notes\nalice,"éé, 192.0.2.1"\n'.encode())
    unit = csv[1]
    item = ips(unit)[0]
    assert item.span == (4, 13)
    assert unit.locator['column_index'] == 2
    assert unit.locator['exact_file_offsets'] is False
    assert unit.locator['record_key'] == csv[0].locator['record_key']
    result = parsers.parse_json(json.dumps({'events': [{'ip': 'é 192.0.2.1'}]}).encode())
    unit = result[0]
    assert ips(unit)[0].span == (2, 11)
    assert unit.locator['pointer'] == '/events/0/ip'
    assert unit.locator['offset_basis'] == 'decoded_scalar_codepoints'


def test_explicit_line_and_record_limits(monkeypatch):
    monkeypatch.setattr(parsers, 'MAX_SOURCE_UNITS', 2)
    result = parsers.parse_text(b'a\nb\nc\n')
    assert len(result) == 2 and result.coverage['status'] == 'partial'
    result = parsers.parse_text(('x' * 10001 + ' 192.0.2.1').encode())
    assert len(result[0].scan_text) == 10000
    assert result.coverage['status'] == 'partial'
    assert result[0].locator['source_characters'] > result[0].locator['scanned_characters']
    with pytest.raises(parsers.ParserError):
        parsers.parse_text(b'x' * (parsers.MAX_TEXT_BYTES + 1))
    with pytest.raises(parsers.ParserError):
        parsers.parse_text(b'')


def test_invalid_encoding_is_explicit():
    result = parsers.parse_text(b'\xff ip=192.0.2.1')
    assert result.coverage['status'] == 'partial'
    assert result.coverage['decoding_replacements'] is True
    assert ips(result[0])


def test_pdf_page_limit_and_failure_are_explicit(monkeypatch):
    class Page:
        def get_contents(self):
            return None
        def extract_text(self):
            return 'Synthetic machine-readable evidence ip=192.0.2.1'
    class BadPage(Page):
        def extract_text(self):
            raise ValueError('synthetic failure')
    class Reader:
        pages = [Page(), BadPage(), Page(), Page()]
        def __init__(self, *a, **kw):
            pass
    monkeypatch.setattr('pypdf.PdfReader', Reader)
    monkeypatch.setattr(parsers, 'MAX_PDF_PAGES', 3)
    result = parsers.parse_pdf(b'synthetic mocked document')
    assert result.coverage['total_pages'] == 4
    assert result.coverage['processed_pages'] == [1, 3]
    assert result.coverage['skipped_pages'][0]['page'] == 2
    assert result.coverage['unprocessed_page_count'] == 1
    assert result.coverage['status'] == 'partial'
    Reader.pages = [Page()]
    result = parsers.parse_pdf(b'synthetic mocked document')
    assert result.coverage['status'] == 'complete'


def test_run_persists_partial_coverage_and_repeated_source_spans(client, investigator, storage_dir):
    from tests.conftest import login, auth_headers
    from tests.test_evidence import make_investigation, upload
    token = login(client, 'investigator')
    inv = make_investigation(client, token)
    headers = auth_headers(token)
    content = ('x ' * 160 + '192.0.2.1 192.0.2.1 ' + 'x' * 10001).encode()
    item = upload(client, token, inv['id'], content=content, filename='long.log').json()
    base = f"/api/investigations/{inv['id']}"
    assert client.post(f"{base}/evidence/{item['id']}/verify", headers=headers).status_code == 200
    run = client.post(f'{base}/analysis/runs', headers=headers, json={'evidence_ids': [item['id']]}).json()
    assert run['status'] == 'completed'
    outcome = run['evidence_outcomes'][0]
    assert outcome['status'] == 'partial'
    assert outcome['coverage']['status'] == 'partial'
    assert outcome['input_sha256'] == item['sha256'] and outcome['verification_id']
    rows = client.get(f'{base}/analysis/artifacts?artifact_type=IP_ADDRESS', headers=headers).json()['items']
    ips = [a for a in rows if a['extractor_name'] == 'ip-pattern']
    assert len(ips) == 2
    assert ips[0]['source_key'] != ips[1]['source_key']
    assert all(a['locator']['span'][0] >= 320 and len(a['context']) <= 280 for a in ips)
