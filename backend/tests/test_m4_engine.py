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
    assert 'lockout_concentration' in kinds(run([event(i,user=f'user{i}',provider='Microsoft-Windows-Security-Auditing',category='account',event_id='4740',outcome='unknown',event_type='account_lockout') for i in range(3)])[0])
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
    assert coverage['rules']['repeated_failures']=={'candidates':3,'returned':1,'omitted':2,'eligible_required_fields':15,'excluded_required_fields':0}
    with pytest.raises(ValueError,match='budget'):
        run([event(0)]*10001)


def test_spray_per_account_limit_and_window():
    concentrated=[event(i,user='mira' if i<10 else f'user{i}') for i in range(14)]
    assert 'password_spray' not in kinds(run(concentrated)[0])
    assert not run([event(i*100) for i in range(5)],window_seconds=10)[0]


def test_missing_ip_and_host_grouping_do_not_invent_accounts():
    failures=[event(i,source_ip=None) for i in range(5)]
    assert kinds(run(failures)[0])=={'repeated_failures'}
    assert not run(failures,grouping='account_host_source')[0]
    nameless=[event(i,username=None,source_ip=None) for i in range(5)]
    assert not run(nameless)[0]
    assert kinds(run(nameless,grouping='host')[0])=={'repeated_failures'}


def test_nat_pattern_is_qualified_not_actor_attribution():
    results,_=run([event(i,user=f'user{i}') for i in range(5)])
    spray=next(r for r in results if r['rule_id']=='auth.password_spray')
    assert 'Shared NAT' in spray['summary'] and 'actor identity' in str(spray['limitations'])


@pytest.mark.parametrize('certainty',['unknown','ambiguous','nonexistent','missing'])
def test_unknown_chronology_cannot_produce_success_after_failures(certainty):
    events=[event(i,time_semantics={'certainty':certainty,'precision':'second'}) for i in range(5)]
    assert 'success_after_failures' not in kinds(run(events+[event(10,outcome='success')],allow_assumed_time=True)[0])


def test_fractional_precision_and_window_boundaries():
    semantics={'certainty':'source_offset','precision':'fraction_3'}
    failures=[event(i,timestamp_utc=f'2026-11-05T00:00:00.00{i}Z',time_semantics=semantics) for i in range(2)]
    equal_edge=event(3,outcome='success',timestamp_utc='2026-11-05T00:00:00.002Z',time_semantics=semantics)
    assert 'success_after_failures' not in kinds(run(failures+[equal_edge],min_failures=2,min_occurrences=2,clock_uncertainty_seconds=0)[0])
    later={**equal_edge,'timestamp_utc':'2026-11-05T00:00:00.003Z'}
    assert 'success_after_failures' in kinds(run(failures+[later],min_failures=2,min_occurrences=2,clock_uncertainty_seconds=0)[0])
    assert not run([event(i*10) for i in range(2)],window_seconds=30,min_failures=2,min_occurrences=2)[0]


def test_linux_explicit_lockouts_and_ordinary_denials_are_distinct():
    lockouts=[event(i,user=f'user{i}',event_type='account_denied',attributes={'denial_reason':'source reports account locked'}) for i in range(3)]
    assert 'lockout_concentration' in kinds(run(lockouts)[0])
    assert 'lockout_concentration' not in kinds(run([{**e,'attributes':{}} for e in lockouts])[0])
    numeric=[event(i,user=f'user{i}',event_id='4740',event_type='logon') for i in range(3)]
    assert 'lockout_concentration' not in kinds(run(numeric)[0])


def test_pure_failures_are_not_mixed_outcome_activity_bursts():
    failures=[event(i,user=f'user{i%4}') for i in range(40)]
    assert 'activity_burst' not in kinds(run(failures)[0])


def test_versions_and_material_parameters_change_identities():
    original=run([event(i) for i in range(5)])[0]
    changed=run([event(i) for i in range(5)],window_seconds=400)[0]
    assert original[0]['semantic_key']!=changed[0]['semantic_key']


def test_ssh_companion_messages_are_not_independent_attempts():
    events=[]
    for i in range(3):
        events.extend([event(i),event(i+10,event_type='invalid_user'),event(i+20,event_type='pam_authentication')])
    results,coverage=run(events)
    assert not results and coverage['excluded']['secondary_authentication_context']==6
    assert 'repeated_failures' in kinds(run([event(i,provider='sudo',event_type='pam_authentication') for i in range(5)])[0])


def test_varying_precision_does_not_expire_relevant_failures_prematurely():
    events=[event(0),event(1,outcome='success',timestamp_utc='2026-11-05T00:00:09.5Z'),
        event(2,timestamp_utc='2026-11-05T00:00:09.6Z',time_semantics={'certainty':'source_offset','precision':'fraction_1'})]
    assert 'repeated_failures' in kinds(run(events,window_seconds=10,min_failures=2,min_occurrences=2)[0])
