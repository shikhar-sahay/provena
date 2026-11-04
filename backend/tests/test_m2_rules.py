"""Conservative record associations, scoring and explicit rule limits."""
from dataclasses import replace
from app.ai import rules
from app.ai.rules import ArtifactFact as A, FactView


def fact(i, evidence, typ, value, record='line:1', context='', **kw):
    return A(i, evidence, f'E-{evidence}', typ, value, record, context, **kw)


def test_removable_media_does_not_link_whole_file_or_ambiguous_records():
    members = [fact(1, 1, 'USB_DEVICE', 'USB-ONE', 'line:1'),
               fact(2, 1, 'USERNAME', 'alice', 'line:2'), fact(3, 1, 'HOSTNAME', 'WS-17', 'line:2')]
    result = rules.RemovableMediaSessionRule().evaluate(FactView(members, {}, True))
    assert len(result) == 1 and result[0].title == 'Ambiguous removable-media observation'
    assert result[0].artifact_ids == [1]
    linked = [replace(m, locator_key='line:1') for m in members]
    result = rules.RemovableMediaSessionRule().evaluate(FactView(linked, {}, True))
    assert len(result) == 1 and 'Co-recorded' in result[0].title
    assert 'not an established session' in result[0].summary
    assert sum(f['weight'] for f in result[0].factors) == result[0].confidence
    ambiguous = linked + [fact(4, 1, 'USERNAME', 'bob')]
    assert rules.RemovableMediaSessionRule().evaluate(FactView(ambiguous, {}, True))[0].title == 'Ambiguous removable-media observation'


def test_support_verification_and_duplicate_partitioned_logs_do_not_inflate_scores():
    initial = [fact(i, i, 'USERNAME', 'alice') for i in range(1, 4)]
    first = rules.IdentityRecurrenceRule().evaluate(FactView(initial, {}, True))[0]
    copied = initial + [fact(4, 4, 'USERNAME', 'alice')]
    second = rules.IdentityRecurrenceRule().evaluate(FactView(copied, {}, False))[0]
    assert first.confidence == second.confidence == sum(f['weight'] for f in first.factors)
    media = [fact(1, 1, 'USB_DEVICE', 'USB-ONE'), fact(2, 1, 'USERNAME', 'alice'), fact(3, 1, 'HOSTNAME', 'WS-17')]
    a = rules.RemovableMediaSessionRule().evaluate(FactView(media, {}, True))[0]
    b = rules.RemovableMediaSessionRule().evaluate(FactView(media + [fact(4, 2, 'IP_ADDRESS', '192.0.2.1', verified=False)], {}, False))[0]
    assert a.confidence == b.confidence
    c = rules.RemovableMediaSessionRule().evaluate(FactView([replace(m, verified=False) for m in media], {}, True))[0]
    assert c.confidence == a.confidence - 10


def test_rule_output_counts_and_larger_retrieval():
    members = [fact(n*3+e, e, 'USERNAME', f'user{n}') for n in range(30) for e in range(1,4)]
    facts = FactView(members, {}, True)
    result = rules.evaluate_all(facts)
    row = next(x for x in result.coverage if x['rule_id'] == 'identity-recurrence')
    assert row['proposed_count'] == 30 and row['emitted_count'] == 25 and row['omitted_count'] == 5
    expanded = rules.evaluate_all(facts, 200)
    assert len([f for f in expanded if f.rule_id == 'identity-recurrence']) == 30
    assert [f.inputs_key() for f in result] == [f.inputs_key() for f in rules.evaluate_all(facts)]

def test_external_score_support_and_evaluation_budget(monkeypatch):
    members = [fact(1,1,'FILE_NAME','a.csv','file','read a.csv'),
        fact(2,1,'TIMESTAMP','2026-01-01T01:00:00+00:00','file'),
        fact(3,1,'USERNAME','alice','file'),
        fact(4,2,'IP_ADDRESS','192.0.2.1','upload','upload to 192.0.2.1',span=(10,19)),
        fact(5,2,'TIMESTAMP','2026-01-01T02:00:00+00:00','upload'),
        fact(6,2,'USERNAME','alice','upload')]
    result = rules.ExternalTransferSequenceRule().evaluate(FactView(members, {}, False))
    assert len(result) == 1
    assert result[0].confidence == sum(f['weight'] for f in result[0].factors)
    assert {3,6}.issubset(result[0].artifact_ids)
    monkeypatch.setattr(rules, 'MAX_TRANSFER_PAIRS', 1)
    result = rules.evaluate_all(FactView(members, {}, True))
    coverage = next(x for x in result.coverage if x['rule_id'] == 'external-transfer-sequence')
    assert coverage['evaluation_complete'] is False
    assert coverage['candidate_pairs_checked'] == 1


def test_rule_coverage_is_persisted_and_expansion_retrieves_more(client, investigator, storage_dir):
    from tests.conftest import login, auth_headers
    from tests.test_evidence import make_investigation, upload
    token = login(client, 'investigator')
    inv = make_investigation(client, token)
    base = f"/api/investigations/{inv['id']}"
    headers = auth_headers(token)
    ids = []
    for i in range(3):
        item = upload(client, token, inv['id'], content=(' '.join(f'user=user{n}' for n in range(30))).encode(), filename=f'{i}.log').json()
        client.post(f"{base}/evidence/{item['id']}/verify", headers=headers)
        ids.append(item['id'])
    client.post(f'{base}/analysis/runs', headers=headers, json={'evidence_ids': ids})
    first = client.post(f'{base}/analysis/findings/generate', headers=headers).json()
    row = next(x for x in first['rule_coverage'] if x['rule_id'] == 'identity-recurrence')
    assert row['omitted_count'] == 5 and first['new_count'] == 25
    assert client.get(f'{base}/analysis/findings/coverage', headers=headers).json() == first['rule_coverage']
    expanded = client.post(f'{base}/analysis/findings/generate?per_rule_limit=200', headers=headers).json()
    assert expanded['new_count'] == 5
    assert len(expanded['findings']) == 30

def test_output_cap_selection_does_not_depend_on_artifact_sequence_allocation():
    first = [fact(i, 1, 'USB_DEVICE', f'USB-{i:03d}', record=f'line:{i}') for i in range(1,31)]
    second = [replace(m, id=1000-m.id) for m in first]
    a = rules.evaluate_all(FactView(first, {}, True))
    b = rules.evaluate_all(FactView(second, {}, True))
    assert len(a) == len(b) == 25
    assert [f.inputs_key() for f in a] == [f.inputs_key() for f in b]
