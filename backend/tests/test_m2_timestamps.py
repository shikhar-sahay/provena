"""Explicit-offset normalization and unknown wall-time safeguards."""
import pytest
from app.ai import extractors, parsers, rules
from app.ai.normalize import normalize, timestamp_details


@pytest.mark.parametrize('raw,utc,offset', [
    ('2026-01-13T02:15:01+05:30', '2026-01-12T20:45:01+00:00', '+05:30'),
    ('2026-01-13T02:15:01Z', '2026-01-13T02:15:01+00:00', 'Z'),
    ('2026-11-01T01:30:00-04:00', '2026-11-01T05:30:00+00:00', '-04:00'),
    ('2026-11-01T01:30:00-05:00', '2026-11-01T06:30:00+00:00', '-05:00'),
    ('13/Jan/2026:02:15:01 +0530', '2026-01-12T20:45:01+00:00', '+0530'),
])
def test_explicit_offset_preserved_and_normalized(raw, utc, offset):
    details = timestamp_details(raw)
    assert details['original'] == raw and details['source_offset'] == offset
    assert details['utc'] == utc == normalize('TIMESTAMP', raw)


@pytest.mark.parametrize('raw', ['2026-01-13 02:15:01', '2026-11-01T01:30:00',
                                 '2026-03-08 02:30:00', '2026-01-13T02:15:01-00:00'])
def test_unknown_timezone_never_becomes_utc(raw):
    details = timestamp_details(raw)
    assert details['timezone_status'] == 'unknown' and details['utc'] is None
    assert '+' not in details['normalized_value']
    fact = rules.ArtifactFact(1, 1, 'E-1', 'TIMESTAMP', details['normalized_value'], 'line:1', raw)
    assert rules.FactView([fact], {}, True).timestamps_on_unit(1, 'line:1') == []


def test_fractional_precision_and_repeated_instants():
    raw = '2026-01-13T02:15:01.123456+05:30'
    unit = parsers.parse_log(raw.encode())[0]
    values = [x.raw_value for _, x in extractors.extract_all(unit) if x.artifact_type == 'TIMESTAMP']
    assert raw in values
    assert normalize('TIMESTAMP', raw) == '2026-01-12T20:45:01.123456+00:00'
    assert timestamp_details(raw)['precision'] == 'fraction_6'
    assert normalize('TIMESTAMP', '2026-01-13T02:15:01.123456789Z') is None
    assert normalize('TIMESTAMP', '2026-02-30T01:00:00Z') is None


def test_unknown_times_cannot_propose_temporal_transfer():
    from tests.test_m2_rules import fact
    rows = [fact(1,1,'FILE_NAME','a.csv','file','read a.csv'),
            fact(2,1,'TIMESTAMP','2026-01-13T01:00:00','file'), fact(3,1,'USERNAME','alice','file'),
            fact(4,2,'IP_ADDRESS','192.0.2.1','upload','upload to 192.0.2.1',span=(10,19)),
            fact(5,2,'TIMESTAMP','2026-01-13T02:00:00','upload'), fact(6,2,'USERNAME','alice','upload')]
    assert rules.ExternalTransferSequenceRule().evaluate(rules.FactView(rows, {}, True)) == []

def test_minute_precision_and_same_instant_do_not_imply_order():
    fact = rules.ArtifactFact(1, 1, 'E-1', 'TIMESTAMP', '2026-01-01T01:00:00+00:00',
                              'line:1', '', time_precision='minute')
    assert rules.FactView([fact], {}, True).timestamps_on_unit(1, 'line:1') == []


def test_timestamp_metadata_round_trips_with_artifact(client, investigator, storage_dir):
    from tests.conftest import login, auth_headers
    from tests.test_evidence import make_investigation, upload
    token = login(client, 'investigator')
    inv = make_investigation(client, token)
    headers = auth_headers(token)
    item = upload(client, token, inv['id'], content=b'2026-01-13T02:15:01+05:30 user=synthetic\n2026-11-01 01:30:00 user=synthetic', filename='times.log').json()
    base = f"/api/investigations/{inv['id']}"
    client.post(f"{base}/evidence/{item['id']}/verify", headers=headers)
    client.post(f'{base}/analysis/runs', headers=headers, json={'evidence_ids': [item['id']]})
    rows = client.get(f'{base}/analysis/artifacts?artifact_type=TIMESTAMP', headers=headers).json()['items']
    by_raw = {a['raw_value']: a for a in rows}
    assert by_raw['2026-01-13T02:15:01+05:30']['locator']['timestamp']['source_offset'] == '+05:30'
    assert by_raw['2026-11-01 01:30:00']['locator']['timestamp']['utc'] is None
    assert by_raw['2026-11-01 01:30:00']['normalized_value'] == '2026-11-01T01:30:00'
