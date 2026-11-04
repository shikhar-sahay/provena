"""Semantic identity, decisions and historical links across reruns."""
from sqlalchemy import select
from app.ai import extractors, rules
from app.modules.intelligence.models import CorrelationArtifact, Correlation
from tests.conftest import login, auth_headers
from tests.test_evidence import make_investigation, upload


def test_stable_support_history_and_versions(client, investigator, storage_dir, db_session, monkeypatch):
    token = login(client, 'investigator')
    inv = make_investigation(client, token)
    base = f"/api/investigations/{inv['id']}"
    headers = auth_headers(token)
    ids = []
    def add(filename, data):
        item = upload(client, token, inv['id'], content=data, filename=filename).json()
        assert client.post(f"{base}/evidence/{item['id']}/verify", headers=headers).status_code == 200
        ids.append(item['id'])
        return item['id']
    def analyse(selected=None):
        result = client.post(f'{base}/analysis/runs', headers=headers, json={'evidence_ids': selected or ids})
        assert result.json()['status'] == 'completed', result.text
        return client.post(f'{base}/analysis/findings/generate', headers=headers).json()
    for name in ['a.log', 'b.log', 'c.log']:
        add(name, b'user=synthetic host=WS-17\n')
    first = analyse()
    target = next(f for f in first['findings'] if f['rule_id'] == 'identity-recurrence')
    cid = target['correlation_ids'][0]
    original_members = list(db_session.execute(select(CorrelationArtifact.artifact_id).where(CorrelationArtifact.correlation_id == cid)).scalars())
    first_key = db_session.get(Correlation, cid).semantic_key
    for status in ['accepted', 'rejected', 'accepted']:
        client.post(f"{base}/analysis/findings/{target['id']}/review", headers=headers, json={'status': status})
        again = analyse()
        assert again['new_count'] == 0
        assert next(f for f in again['findings'] if f['id'] == target['id'])['status'] == status
    report = client.post(f'{base}/analysis/reports', headers=headers).json()
    add('unrelated.log', b'ip=203.0.113.90\n')
    assert analyse()['new_count'] == 0
    relevant = add('relevant.log', b'user=synthetic host=WS-17\n')
    changed = analyse([relevant])
    new = [f for f in changed['findings'] if f['id'] != target['id'] and f['rule_id'] == target['rule_id']]
    assert len(new) == 1 and new[0]['status'] == 'pending_review'
    assert db_session.get(Correlation, cid).semantic_key == first_key
    assert list(db_session.execute(select(CorrelationArtifact.artifact_id).where(CorrelationArtifact.correlation_id == cid)).scalars()) == original_members
    assert client.get(f'{base}/analysis/correlations/{cid}', headers=headers).status_code == 200
    assert client.get(f"{base}/analysis/reports/{report['id']}", headers=headers).json()['content_sha256'] == report['content_sha256']
    monkeypatch.setattr(extractors, 'EXTRACTOR_VERSION', 'synthetic-3')
    versioned = analyse()
    assert versioned['new_count'] >= 1
    assert next(f for f in versioned['findings'] if f['id'] == target['id'])['support_current'] is False
    monkeypatch.setattr(rules, 'RULE_VERSION', 'synthetic-3')
    reruled = client.post(f'{base}/analysis/findings/generate', headers=headers).json()
    assert reruled['new_count'] >= 1
    assert all(f['status'] == 'pending_review' for f in reruled['findings'] if f['rule_version'] == 'synthetic-3')


def test_semantic_finding_key_ignores_database_sequences():
    args = dict(rule_id='test', rule_version='2', title='same', summary='same', severity='low', confidence=20,
                factors=[{'factor': 'support', 'weight': 20}], evidence_ids=[1], artifact_ids=[1],
                correlation_ids=[1], recommendations=[], support_keys=['stable-support'])
    first = rules.ProposedFinding(**args)
    second = rules.ProposedFinding(**{**args, 'artifact_ids': [900], 'correlation_ids': [999]})
    assert first.inputs_key() == second.inputs_key()
    second.support_keys = ['changed-support']
    assert first.inputs_key() != second.inputs_key()

def test_support_coverage_keys_survive_json_with_two_digit_evidence_ids(client, investigator, storage_dir):
    token = login(client, 'investigator')
    inv = make_investigation(client, token)
    base = f"/api/investigations/{inv['id']}"
    headers = auth_headers(token)
    ids = []
    for i in range(10):
        item = upload(client, token, inv['id'], content=b'user=synthetic\n', filename=f'{i}.log').json()
        client.post(f"{base}/evidence/{item['id']}/verify", headers=headers)
        ids.append(item['id'])
    client.post(f'{base}/analysis/runs', headers=headers, json={'evidence_ids': ids})
    first = client.post(f'{base}/analysis/findings/generate', headers=headers).json()
    assert first['findings'] and all(f['support_current'] for f in first['findings'])
    second = client.post(f'{base}/analysis/findings/generate', headers=headers).json()
    assert second['new_count'] == 0
    assert all(f['support_current'] for f in second['findings'])
