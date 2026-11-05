"""Synthetic end-to-end ingestion, integrity, provenance and case isolation."""
from contextlib import contextmanager
import pytest
from sqlalchemy import select, func
from app.modules.events.models import SecurityEvent, EventIngestionRun, EventRunMember, SourceProfile
from app.modules.evidence.models import Evidence
from tests.conftest import auth_headers, login, make_user
from tests.test_evidence import make_investigation, upload

DATA=b'2026-11-05T12:00:00Z lab-host sshd[123]: Failed password for mira from 192.0.2.1 port 2222 ssh2\n'


def setup(client,user,db):
    token=login(client,user.username)
    inv=make_investigation(client,token)
    headers=auth_headers(token)
    base=f"/api/investigations/{inv['id']}"
    profile=client.post(base+'/events/profiles',headers=headers,json={'name':'Synthetic Linux','configuration':{
        'adapter':'linux_auth','format':'syslog'}})
    assert profile.status_code==201,profile.text
    item=upload(client,token,inv['id'],content=DATA+DATA+b'unsupported record\n',filename='auth.log').json()
    assert client.post(f"{base}/evidence/{item['id']}/verify",headers=headers).status_code==200
    return base,headers,item,profile.json(),token,inv


def ingest(client,base,headers,item,profile):
    response=client.post(base+'/events/runs',headers=headers,json={'evidence_id':item['id'],'profile_id':profile['id']})
    assert response.status_code==201,response.text
    return response.json()


def test_ingestion_retry_filters_occurrences_and_profiles(client,investigator,db_session,storage_dir):
    base,headers,item,profile,token,inv=setup(client,investigator,db_session)
    first=ingest(client,base,headers,item,profile)
    assert first['status']=='partial' and first['coverage']['recognized']==2
    assert first['coverage']['unrecognized']==1 and first['verification_id']
    events=client.get(base+'/events?outcome=failure&username=mira&source_ip=192.0.2.1&host=lab-host',headers=headers).json()
    assert events['total']==2 and len({e['semantic_key'] for e in events['items']})==2
    keys=[e['semantic_key'] for e in events['items']]
    assert all(e['input_sha256']==item['sha256'] and e['support_verified'] for e in events['items'])
    assert {e['locator']['line'] for e in events['items']}=={1,2}
    assert len({e['record_fingerprint'] for e in events['items']})==1
    repeat=ingest(client,base,headers,item,profile)
    assert repeat['coverage']['events_created']==0
    assert client.get(base+f"/events?run_id={repeat['id']}",headers=headers).json()['total']==2
    assert client.get(base+'/events?limit=1&offset=1',headers=headers).json()['items'][0]['semantic_key']==keys[1]
    assert client.get(base+'/events/'+keys[0],headers=headers).json()['profile_snapshot']['semantic_key']==profile['semantic_key']
    assert client.get(base+'/events?start=2026-11-05T11:00:00Z&end=2026-11-05T13:00:00Z',headers=headers).json()['total']==2
    for query in ['start=2026-11-05T12:00:00','source_ip=invalid','limit=1000','offset=-1']:
        assert client.get(base+'/events?'+query,headers=headers).status_code==422
    changed=client.post(base+'/events/profiles',headers=headers,json={'name':'Explicit assumptions','configuration':{
        'adapter':'linux_auth','format':'syslog','year':2026,'timezone':'+05:30'}}).json()
    assert changed['semantic_key']!=profile['semantic_key']
    assert ingest(client,base,headers,item,changed)['coverage']['events_created']==2
    assert client.get(base+'/events',headers=headers).json()['total']==4
    assert client.get(base+f"/events?profile_id={profile['id']}",headers=headers).json()['total']==2


@pytest.mark.parametrize('failure',['missing','tampered','incomplete','unverified'])
def test_integrity_gate_and_historical_support(client,investigator,db_session,storage_dir,failure):
    from app.modules.evidence import storage
    base,headers,item,profile,_,_=setup(client,investigator,db_session)
    assert ingest(client,base,headers,item,profile)['coverage']['recognized']==2
    row=db_session.get(Evidence,item['id'])
    if failure=='missing': storage.resolve(row.storage_key).unlink()
    elif failure=='tampered': storage.resolve(row.storage_key).write_bytes(DATA.replace(b'mira',b'evil'))
    elif failure=='incomplete': row.registration_status='failed'
    else: row.integrity_status='not_verified'
    db_session.commit()
    result=ingest(client,base,headers,item,profile)
    assert result['status']=='blocked'
    assert all(not e['support_verified'] for e in client.get(base+'/events',headers=headers).json()['items'])
    assert db_session.scalar(select(func.count()).select_from(SecurityEvent))==2


def test_snapshot_not_mutable_reopen(client,investigator,db_session,storage_dir,monkeypatch):
    from app.modules.evidence import storage
    from app.modules.events import service
    base,headers,item,profile,_,_=setup(client,investigator,db_session)
    original=service.parse_records
    def replace_after_copy(data,config):
        storage.resolve(db_session.get(Evidence,item['id']).storage_key).write_bytes(b'changed during preparation')
        return original(data,config)
    monkeypatch.setattr(service,'parse_records',replace_after_copy)
    result=ingest(client,base,headers,item,profile)
    assert result['coverage']['recognized']==2
    assert client.get(base+'/events',headers=headers).json()['items'][0]['username']=='mira'


def test_failed_transaction_does_not_leave_partial_set(client,investigator,db_session,storage_dir,monkeypatch):
    base,headers,item,profile,_,_=setup(client,investigator,db_session)
    execute=db_session.execute
    attempted=[]
    def fail(statement,*args,**kwargs):
        if getattr(statement,'is_insert',False) and statement.table.name=='event_run_members' and not attempted:
            attempted.append(True)
            raise RuntimeError('synthetic private storage details')
        return execute(statement,*args,**kwargs)
    monkeypatch.setattr(db_session,'execute',fail)
    result=ingest(client,base,headers,item,profile)
    assert result['status']=='failed' and 'private' not in result['error']
    assert db_session.scalar(select(func.count()).select_from(SecurityEvent))==0
    assert db_session.scalar(select(func.count()).select_from(EventRunMember))==0
    assert ingest(client,base,headers,item,profile)['coverage']['recognized']==2


def test_profiles_access_and_recovery(client,investigator,db_session,storage_dir):
    base,headers,item,profile,_,inv=setup(client,investigator,db_session)
    outsider=make_user(db_session,'event-outsider')
    other_headers=auth_headers(login(client,outsider.username))
    for path in ['/events','/events/profiles','/events/runs','/events/'+'a'*64]:
        assert client.get(base+path,headers=other_headers).status_code==404
    assert client.post(base+'/events/runs',headers=other_headers,json={'evidence_id':item['id'],'profile_id':profile['id']}).status_code==404
    from app.modules.workspaces.models import WorkspaceMembership
    membership=db_session.scalar(select(WorkspaceMembership).where(WorkspaceMembership.user_id==investigator.id))
    membership.is_active=False;db_session.commit()
    assert client.get(base+'/events',headers=headers).status_code in (403,404)
    membership.is_active=True;db_session.commit()
    run=EventIngestionRun(investigation_id=inv['id'],evidence_id=item['id'],profile_id=profile['id'],
        initiated_by_id=investigator.id,status='running',adapter_version='1',normalization_version='1',coverage={})
    db_session.add(run);db_session.commit()
    assert client.post(base+f'/events/runs/{run.id}/recover',headers=headers).json()['status']=='failed'
    assert client.patch(base+f"/events/profiles/{profile['id']}",headers=headers,json={}).status_code in (404,405)


def test_structured_ingestion_and_uncertain_range(client,investigator,db_session,storage_dir):
    base,headers,_,_,token,inv=setup(client,investigator,db_session)
    profile=client.post(base+'/events/profiles',headers=headers,json={'name':'Windows','configuration':{
        'adapter':'windows_security','format':'jsonl'}}).json()
    raw=b'{"EventID":4625,"TargetUserName":"mira","TimeCreated":"2026-11-05 12:00:00"}\n{bad}\n{"EventID":99}\n'
    item=upload(client,token,inv['id'],content=raw,filename='security.jsonl').json()
    client.post(f"{base}/evidence/{item['id']}/verify",headers=headers)
    run=ingest(client,base,headers,item,profile)
    assert run['coverage']['recognized']==run['coverage']['rejected']==run['coverage']['unrecognized']==1
    assert client.get(base+'/events?start=2026-01-01T00:00:00Z',headers=headers).json()['total']==0
    assert client.get(base+'/events?event_id=4625',headers=headers).json()['total']==1
    bad=upload(client,token,inv['id'],content=b'{bad',filename='bad.json').json()
    client.post(f"{base}/evidence/{bad['id']}/verify",headers=headers)
    jsonprofile=client.post(base+'/events/profiles',headers=headers,json={'name':'JSON','configuration':{
        'adapter':'windows_security','format':'json'}}).json()
    assert ingest(client,base,headers,bad,jsonprofile)['status']=='rejected'


def test_partial_record_budget_is_persisted(client,investigator,db_session,storage_dir,monkeypatch):
    base,headers,item,profile,_,_=setup(client,investigator,db_session)
    monkeypatch.setattr('app.events.records.MAX_RECORDS',1)
    result=ingest(client,base,headers,item,profile)
    assert result['status']=='partial' and result['coverage']['omitted']==2
    assert result['coverage']['records_total']==3
    assert client.get(base+'/events',headers=headers).json()['total']==1

from tests.test_evidence_foundation import backend


def test_event_ingestion_storage_backends_and_source_tamper(backend,client,investigator,db_session):
    store,replace,remove=backend
    base,headers,item,profile,_,_=setup(client,investigator,db_session)
    assert ingest(client,base,headers,item,profile)['coverage']['recognized']==2
    row=db_session.get(Evidence,item['id'])
    replace(row.storage_key,DATA.replace(b'mira',b'evil'))
    assert ingest(client,base,headers,item,profile)['status']=='blocked'
    assert db_session.scalar(select(func.count()).select_from(SecurityEvent))==2


def test_missing_case_profile_and_invalid_configuration(client,investigator,db_session,storage_dir):
    base,headers,item,profile,token,_=setup(client,investigator,db_session)
    other=make_investigation(client,token)
    assert client.post(f"/api/investigations/{other['id']}/events/runs",headers=headers,
        json={'evidence_id':item['id'],'profile_id':profile['id']}).status_code==404
    assert client.post(base+'/events/profiles',headers=headers,json={'name':'Invalid','configuration':{
        'adapter':'windows_security','format':'syslog'}}).status_code==422
    assert client.post(base+'/events/profiles',headers=headers,json={'name':'Invalid','configuration':{
        'adapter':'linux_auth','format':'syslog','timezone':'Europe/Invalid'}}).status_code==422


def test_registration_commit_error_safe_and_lost_completion_ack_idempotent(client,investigator,db_session,storage_dir,monkeypatch):
    base,headers,item,profile,_,_=setup(client,investigator,db_session)
    commit=db_session.commit
    attempted=[]
    def fail_before():
        if not attempted:
            attempted.append(True)
            raise RuntimeError('synthetic secret details')
        return commit()
    monkeypatch.setattr(db_session,'commit',fail_before)
    response=client.post(base+'/events/runs',headers=headers,json={'evidence_id':item['id'],'profile_id':profile['id']})
    assert response.status_code==503 and 'secret' not in response.text
    counter=[]
    def lost_ack():
        commit()
        counter.append(True)
        if len(counter)==2:
            raise RuntimeError('synthetic lost acknowledgement')
    monkeypatch.setattr(db_session,'commit',lost_ack)
    result=ingest(client,base,headers,item,profile)
    assert result['status']=='partial'
    assert db_session.scalar(select(func.count()).select_from(SecurityEvent))==2
