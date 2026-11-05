"""The committed M3 synthetic demonstration, entirely isolated from live data."""
from pathlib import Path
from tests.conftest import login, auth_headers
from tests.test_evidence import make_investigation, upload

DATA=Path(__file__).resolve().parents[2]/'sample-data'/'m3-authentication'


def test_m3_synthetic_investigation_demo(client,investigator,storage_dir):
    token=login(client,investigator.username)
    inv=make_investigation(client,token,title='Synthetic M3 authentication investigation')
    base=f"/api/investigations/{inv['id']}"
    headers=auth_headers(token)
    results=[]
    for filename,adapter,fmt,expected in [('linux-auth.log','linux_auth','syslog',11),
        ('windows-security.jsonl','windows_security','jsonl',5),('sysmon.csv','sysmon','csv',2)]:
        item=upload(client,token,inv['id'],content=(DATA/filename).read_bytes(),filename=filename,title=filename).json()
        assert client.post(f"{base}/evidence/{item['id']}/verify",headers=headers).json()['result']=='verified'
        profile=client.post(base+'/events/profiles',headers=headers,json={'name':filename+' source','configuration':{
            'adapter':adapter,'format':fmt}}).json()
        request={'evidence_id':item['id'],'profile_id':profile['id']}
        first=client.post(base+'/events/runs',headers=headers,json=request).json()
        assert first['status']=='partial' and first['coverage']['recognized']==expected,first
        coverage=first['coverage']
        assert sum(coverage[x] for x in ['recognized','unrecognized','rejected','omitted'])==coverage['records_total']
        before=client.get(base+f"/events?profile_id={profile['id']}",headers=headers).json()
        second=client.post(base+'/events/runs',headers=headers,json=request).json()
        assert second['coverage']['events_created']==0
        after=client.get(base+f"/events?profile_id={profile['id']}",headers=headers).json()
        assert [e['semantic_key'] for e in before['items']]==[e['semantic_key'] for e in after['items']]
        event=after['items'][0]
        detail=client.get(base+'/events/'+event['semantic_key'],headers=headers).json()
        assert detail['input_sha256']==item['sha256'] and detail['locator']
        assert 'storage_key' not in detail
        results.append((filename,coverage['recognized'],coverage['unrecognized'],coverage['rejected']))
    all_events=client.get(base+'/events',headers=headers).json()
    failures=client.get(base+'/events?category=authentication&outcome=failure',headers=headers).json()
    assert all_events['total']==18
    assert failures['total']==8
    assert any(e['timestamp_utc'] is None for e in all_events['items'])
    assert all(e['category'] not in ('authentication','session') for e in all_events['items'] if e['provider']=='Microsoft-Windows-Sysmon')
    print(f'Synthetic demo: {results}; total=18; authentication failures=8; identical reingestion creates zero events.')
