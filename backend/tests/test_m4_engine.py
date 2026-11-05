"""Synthetic positive and adversarial detection boundaries."""
from datetime import datetime, timedelta, timezone
import pytest
from app.events.detections import evaluate, digest
from app.modules.detections.schemas import DetectionConfig


def event(i, user='mira', outcome='failure', **changes):
    value=dict(semantic_key=digest(i),provider='sshd',category='authentication',event_type='logon',
        outcome=outcome,username=user,account_domain=None,hostname='lab',source_ip='192.0.2.1',
        timestamp_utc=(datetime(2026,11,5,tzinfo=timezone.utc)+timedelta(seconds=i*3)).isoformat(),
        original_timestamp=str(i),attributes={},time_semantics={'certainty':'source_offset','precision':'second'})
    value.update(changes)
    return value


def run(events,**config):
    return evaluate(events,DetectionConfig(**config).model_dump())


def kinds(results):
    return {r['rule_id'].removeprefix('auth.') for r in results}


def test_all_families_and_reproducibility():
    failures=[event(i) for i in range(5)]
    assert 'repeated_failures' in kinds(run(failures)[0])
    assert 'success_after_failures' in kinds(run(failures+[event(10,outcome='success')])[0])
    assert 'password_spray' in kinds(run([event(i,user=f'user{i}') for i in range(5)])[0])
    assert 'lockout_concentration' in kinds(run([event(i,user=f'user{i}',event_id='4740',outcome='unknown',event_type='account_lockout') for i in range(3)])[0])
    burst=[event(i,user=f'user{i%4}',outcome='success' if i%3==0 else 'failure') for i in range(24)]
    results,coverage=run(burst)
    assert 'activity_burst' in kinds(results)
    assert run(list(reversed(burst)))==(results,coverage)
    assert all(r['event_keys'] and r['severity_rationale'] and r['configuration'] for r in results)


@pytest.mark.parametrize('change',[
    {'time_semantics':{'certainty':'unknown','precision':'second'},'timestamp_utc':None},
    {'time_semantics':{'certainty':'ambiguous','precision':'second'}},
    {'time_semantics':{'certainty':'profile_zone','precision':'second'}},
    {'time_semantics':{'certainty':'source_offset','precision':'minute'}},
    {'hostname':None},
])
def test_unsupported_temporal_and_identity_inputs(change):
    assert not run([event(i,**change) for i in range(5)])[0]


def test_assumptions_must_be_opted_in():
    events=[event(i,time_semantics={'certainty':'profile_zone','precision':'second'}) for i in range(5)]
    assert not run(events)[0]
    assert 'repeated_failures' in kinds(run(events,allow_assumed_time=True)[0])


def test_isolated_benign_successes_unknown_hosts_and_domains():
    assert not run([event(0)])[0]
    assert not run([event(i,outcome='success',user=f'user{i%5}') for i in range(100)])[0]
    assert 'password_spray' not in kinds(run([event(i,user='same',account_domain=f'DOMAIN{i}') for i in range(6)])[0])
    assert 'lockout_concentration' not in kinds(run([event(i) for i in range(30)])[0])


def test_duplicates_and_equal_or_out_of_order_times():
    originals=[event(i) for i in range(5)]
    copies=[{**originals[0],'semantic_key':digest(('copy',i))} for i in range(10)]
    results,coverage=run(copies)
    assert not results and coverage['excluded']['duplicate_observation']==9
    success=event(10,outcome='success',timestamp_utc=originals[-1]['timestamp_utc'])
    assert 'success_after_failures' not in kinds(run(originals+[success])[0])
    earlier=event(-1,outcome='success')
    assert 'success_after_failures' not in kinds(run(originals+[earlier])[0])
    other_source=event(10,outcome='success',source_ip='192.0.2.2')
    assert 'success_after_failures' not in kinds(run(originals+[other_source])[0])


def test_limits_are_explicit():
    results,coverage=run([event(i) for i in range(15)],result_limit=1)
    assert len(results)==1
    assert coverage['rules']['repeated_failures']=={'candidates':3,'returned':1,'omitted':2}
    with pytest.raises(ValueError,match='budget'):
        run([event(0)]*10001)


def test_spray_per_account_limit_and_window():
    concentrated=[event(i,user='mira' if i<10 else f'user{i}') for i in range(14)]
    assert 'password_spray' not in kinds(run(concentrated)[0])
    assert not run([event(i*100) for i in range(5)],window_seconds=10)[0]
