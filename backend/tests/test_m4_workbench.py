"""Real API synthetic selection, detection, review, timeline and report workflow."""
import pytest
from sqlalchemy import select, func
from app.modules.detections.models import AuthenticationDetectionRun, EventSetMember
from app.modules.intelligence.models import Finding, Report
from app.modules.events.models import EventIngestionRun
from app.modules.evidence.models import Evidence
from tests.conftest import login, auth_headers, make_user
from tests.test_evidence import make_investigation, upload
from tests.test_m3_events import ingest


def scenario(client,user):
    token=login(client,user.username)
    inv=make_investigation(client,token)
    headers=auth_headers(token)
    base=f"/api/investigations/{inv['id']}"
    data=''.join(f'2026-11-05T12:00:{i*3:02d}Z lab sshd[123]: Failed password for mira from 192.0.2.1 port {2200+i} ssh2\n' for i in range(5))
    data+='2026-11-05T12:00:30Z lab sshd[123]: Accepted password for mira from 192.0.2.1 port 2300 ssh2\n'
    item=upload(client,token,inv['id'],content=data.encode(),filename='synthetic.log').json()
    client.post(f"{base}/evidence/{item['id']}/verify",headers=headers).raise_for_status()
    profile=client.post(base+'/events/profiles',headers=headers,json={'name':'UTC Linux','configuration':{'adapter':'linux_auth','format':'syslog'}}).json()
    run=ingest(client,base,headers,item,profile)
    return base,headers,item,profile,run,token,data


def selection(client,base,headers,ids):
    response=client.post(base+'/authentication/sets',headers=headers,json={'name':'Explicit selection','run_ids':ids})
    assert response.status_code==201,response.text
    return response.json()


def execute(client,base,headers,set_id,**config):
    response=client.post(base+'/authentication/runs',headers=headers,json={'event_set_id':set_id,'configuration':config})
    assert response.status_code==201,response.text
    return response.json()


def test_complete_review_report_and_identical_rerun(client,investigator,db_session,storage_dir):
    base,h,item,profile,run,token,_=scenario(client,investigator)
    selected=selection(client,base,h,[run['id']])
    assert selected['coverage']['included_events']==6
    result=execute(client,base,h,selected['id'])
    assert result['status']=='completed'
    findings=client.get(base+f"/authentication/findings?event_set_id={selected['id']}",headers=h).json()
    assert findings['total']==2
    finding=findings['items'][0]
    assert finding['support_current']
    review=client.post(base+f"/analysis/findings/{finding['id']}/review",headers=h,json={'status':'accepted','note':'Synthetic review: source records checked.'})
    assert review.status_code==200,review.text
    first=client.post(base+'/analysis/reports',headers=h)
    assert first.status_code==201,first.text
    report=first.json()
    assert report['content']['authentication_investigation']['sets'][0]['semantic_key']==selected['semantic_key']
    accepted=report['content']['accepted_findings']
    assert len(accepted)==1 and accepted[0]['support_snapshot']['event_keys']
    assert '0/100' not in str(report['content']['narrative'])
    again=ingest(client,base,h,item,profile)
    same=selection(client,base,h,[again['id'],run['id']])
    assert same['semantic_key']==selected['semantic_key'] and same['id']==selected['id']
    execute(client,base,h,same['id'])
    assert db_session.scalar(select(func.count()).select_from(Finding))==2
    assert db_session.get(Finding,finding['id']).status=='accepted'
    assert db_session.get(Report,report['id']).content_sha256==report['content_sha256']
    history=client.get(base+f"/authentication/findings/{finding['id']}/history",headers=h).json()
    assert history[0]['decision']['previous_decision']['status']=='pending_review'
    timeline=client.get(base+f"/authentication/timeline?event_set_id={selected['id']}&username=mira&host=lab&source_ip=192.0.2.1&limit=2",headers=h).json()
    assert timeline['total']==6 and len(timeline['items'])==2
    support=client.get(base+f"/authentication/timeline?event_set_id={selected['id']}&finding_id={finding['id']}",headers=h).json()
    assert support['total']==len(finding['support_snapshot']['event_keys'])
    changed=execute(client,base,h,selected['id'],min_failures=4,min_occurrences=4)
    assert changed['status']=='completed'
    assert db_session.scalar(select(func.count()).select_from(Finding).where(Finding.status=='pending_review'))>1


def test_copies_alternative_profiles_and_partition_overlap(client,investigator,db_session,storage_dir):
    base,h,item,profile,run,token,data=scenario(client,investigator)
    copy=upload(client,token,int(base.rsplit('/',1)[1]),content=data.encode(),filename='copy.log').json()
    client.post(base+f"/evidence/{copy['id']}/verify",headers=h)
    copyrun=ingest(client,base,h,copy,profile)
    selected=selection(client,base,h,[run['id'],copyrun['id']])
    assert selected['coverage']['selected_events']==12
    assert selected['coverage']['included_events']==6
    assert db_session.scalar(select(func.count()).select_from(EventSetMember).where(EventSetMember.set_id==selected['id']))==12
    result=execute(client,base,h,selected['id'])
    assert result['coverage']['eligible']==6
    other=client.post(base+'/events/profiles',headers=h,json={'name':'Alternative','configuration':{'adapter':'linux_auth','format':'syslog','timezone':'+05:30'}}).json()
    alt=ingest(client,base,h,item,other)
    response=client.post(base+'/authentication/sets',headers=h,json={'name':'Invalid mix','run_ids':[run['id'],alt['id']]})
    assert response.status_code==409


@pytest.mark.parametrize('failure',['tampered','missing','incomplete'])
def test_current_integrity_blocks_detection_and_report(client,investigator,db_session,storage_dir,failure):
    from app.modules.evidence import storage
    base,h,item,_,run,_,_=scenario(client,investigator)
    selected=selection(client,base,h,[run['id']])
    execute(client,base,h,selected['id'])
    evidence=db_session.get(Evidence,item['id'])
    if failure=='tampered': storage.resolve(evidence.storage_key).write_bytes(b'tampered')
    elif failure=='missing': storage.resolve(evidence.storage_key).unlink()
    else:
        evidence.registration_status='failed'
        db_session.commit()
    blocked=execute(client,base,h,selected['id'])
    assert blocked['status']=='blocked'
    findings=client.get(base+f"/authentication/findings?event_set_id={selected['id']}",headers=h).json()['items']
    assert findings and all(not f['support_current'] for f in findings)


def test_authorization_validation_and_interrupted_recovery(client,investigator,db_session,storage_dir):
    base,h,_,_,run,_,_=scenario(client,investigator)
    selected=selection(client,base,h,[run['id']])
    stranger=make_user(db_session,'unrelated')
    unrelated=auth_headers(login(client,stranger.username))
    for path in ['/sets','/runs',f"/findings?event_set_id={selected['id']}",f"/timeline?event_set_id={selected['id']}"]:
        assert client.get(base+'/authentication'+path,headers=unrelated).status_code in (403,404)
    assert client.post(base+'/authentication/runs',headers=unrelated,json={'event_set_id':selected['id']}).status_code in (403,404)
    for query in ['start=2026-11-05T12:00:00','source_ip=bad','limit=999','lane=uncertain&start=2026-11-05T00:00:00Z']:
        assert client.get(base+f"/authentication/timeline?event_set_id={selected['id']}&{query}",headers=h).status_code==422
    assert client.post(base+'/authentication/runs',headers=h,json={'event_set_id':selected['id'],'configuration':{'window_seconds':0}}).status_code==422
    pending=AuthenticationDetectionRun(investigation_id=int(base.rsplit('/',1)[1]),event_set_id=selected['id'],configuration={},status='running')
    db_session.add(pending);db_session.commit()
    response=client.post(base+f'/authentication/runs/{pending.id}/recover',headers=h)
    assert response.json()['status']=='failed'


def test_rollback_no_partial_findings(client,investigator,db_session,storage_dir,monkeypatch):
    from app.events import detections
    base,h,_,_,run,_,_=scenario(client,investigator)
    selected=selection(client,base,h,[run['id']])
    def fail(*args): raise RuntimeError('synthetic failure')
    monkeypatch.setattr(detections,'evaluate',fail)
    response=client.post(base+'/authentication/runs',headers=h,json={'event_set_id':selected['id']})
    assert response.status_code==503
    assert db_session.scalar(select(func.count()).select_from(Finding))==0
    assert db_session.scalar(select(AuthenticationDetectionRun)).status=='failed'
