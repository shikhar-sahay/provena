"""Checked-in synthetic evidence exercises the whole authentication workbench."""
from pathlib import Path
from tests.conftest import login, auth_headers
from tests.test_evidence import make_investigation, upload
from tests.test_m3_events import ingest
from tests.test_m4_workbench import selection, execute

DATA=Path(__file__).resolve().parents[2]/'sample-data'/'m4-authentication'


def test_synthetic_authentication_investigation(client,investigator,db_session,storage_dir):
    token=login(client,investigator.username)
    inv=make_investigation(client,token)
    base=f"/api/investigations/{inv['id']}"
    h=auth_headers(token)
    runs=[]
    inputs=[]
    for filename,adapter,fmt in [('linux-auth.txt','linux_auth','syslog'),('windows-security.jsonl','windows_security','jsonl'),('sysmon-context.jsonl','sysmon','jsonl')]:
        item=upload(client,token,inv['id'],content=(DATA/filename).read_bytes(),filename=filename).json()
        client.post(base+f"/evidence/{item['id']}/verify",headers=h).raise_for_status()
        profile=client.post(base+'/events/profiles',headers=h,json={'name':adapter,'configuration':{'adapter':adapter,'format':fmt}}).json()
        run=ingest(client,base,h,item,profile)
        runs.append(run['id']);inputs.append((item,profile))
    selected=selection(client,base,h,runs)
    assert selected['coverage']['partial']
    result=execute(client,base,h,selected['id'])
    assert result['status']=='completed'
    findings=client.get(base+f"/authentication/findings?event_set_id={selected['id']}",headers=h).json()
    assert {f['rule_id'] for f in findings['items']}=={'auth.repeated_failures','auth.password_spray','auth.success_after_failures','auth.lockout_concentration','auth.activity_burst'}
    assert findings['total']==5
    assert result['coverage']['excluded']=={'unsupported_time':6,'duplicate_observation':1,'non_authentication':2}
    uncertain=client.get(base+f"/authentication/timeline?event_set_id={selected['id']}&lane=uncertain",headers=h).json()
    assert uncertain['total']==6
    spraying=next(f for f in findings['items'] if f['rule_id']=='auth.password_spray')
    pivot=client.get(base+f"/authentication/timeline?event_set_id={selected['id']}&source_ip=192.0.2.20",headers=h).json()
    assert pivot['total']==6
    accepted=client.post(base+f"/analysis/findings/{spraying['id']}/review",headers=h,json={'status':'accepted','note':'Shared NAT remains an alternative explanation.'})
    assert accepted.status_code==200
    rejected=next(f for f in findings['items'] if f['rule_id']=='auth.activity_burst')
    client.post(base+f"/analysis/findings/{rejected['id']}/review",headers=h,json={'status':'rejected','note':'Synthetic benign service activity.'}).raise_for_status()
    client.post(base+'/analysis/notes',headers=h,json={'body':'Synthetic validation scenario; no real incident asserted.','finding_id':spraying['id']}).raise_for_status()
    report=client.post(base+f"/analysis/reports?event_set_id={selected['id']}",headers=h)
    assert report.status_code==201,report.text
    assert [f['id'] for f in report.json()['content']['accepted_findings']]==[spraying['id']]
    repeat=[]
    for item,profile in inputs: repeat.append(ingest(client,base,h,item,profile)['id'])
    repeated=selection(client,base,h,repeat)
    assert repeated['semantic_key']==selected['semantic_key']
    execute(client,base,h,repeated['id'])
    after=client.get(base+f"/authentication/findings?event_set_id={selected['id']}",headers=h).json()
    assert after['total']==5
    assert next(f for f in after['items'] if f['id']==spraying['id'])['status']=='accepted'
    assert next(f for f in after['items'] if f['id']==rejected['id'])['status']=='rejected'
