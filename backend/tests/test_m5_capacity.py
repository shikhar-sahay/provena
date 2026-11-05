"""Bounded synthetic operational benchmark, not a production capacity guarantee."""
import json
import time
import tracemalloc
from datetime import datetime,timedelta,timezone
from app.core.config import settings
from tests.conftest import login,auth_headers
from tests.test_evidence import make_investigation,upload
from tests.test_m3_events import ingest
from tests.test_m4_workbench import selection,execute


def test_representative_operational_workload(client,investigator,storage_dir,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'export_storage_root',str(tmp_path/'exports'))
    token=login(client,investigator.username);h=auth_headers(token)
    inv=make_investigation(client,token);base=f"/api/investigations/{inv['id']}"
    start=datetime(2026,11,5,12,tzinfo=timezone.utc)
    records=''.join(f"{(start+timedelta(seconds=i)).isoformat()} lab sshd[{100+i}]: Failed password for user{i%20} from 192.0.2.1 port {2200+i} ssh2\n" for i in range(2000)).encode()
    item=upload(client,token,inv['id'],content=records,filename='capacity.log').json()
    client.post(base+f"/evidence/{item['id']}/verify",headers=h).raise_for_status()
    profile=client.post(base+'/events/profiles',headers=h,json={'name':'Synthetic capacity','configuration':{'adapter':'linux_auth','format':'syslog'}}).json()
    timings={}
    before=time.perf_counter();run=ingest(client,base,h,item,profile);timings['ingest_seconds']=time.perf_counter()-before
    assert run['status']=='completed'
    selected=selection(client,base,h,[run['id']])
    before=time.perf_counter();detected=execute(client,base,h,selected['id']);timings['detect_seconds']=time.perf_counter()-before
    assert detected['status']=='completed'
    before=time.perf_counter()
    timeline=client.get(base+f"/authentication/timeline?event_set_id={selected['id']}&limit=100",headers=h).json()
    timings['timeline_seconds']=time.perf_counter()-before
    assert timeline['total']==2000 and len(timeline['items'])==100
    before=time.perf_counter();report=client.post(base+f"/analysis/reports?event_set_id={selected['id']}",headers=h)
    timings['report_seconds']=time.perf_counter()-before
    assert report.status_code==201,report.text
    # A separate opaque 16 MiB original exercises disk-backed package generation.
    large=upload(client,token,inv['id'],content=b'x'*(16*1024*1024),filename='capacity.bin').json()
    assert 'id' in large,large
    client.post(base+f"/evidence/{large['id']}/verify",headers=h).raise_for_status()
    tracemalloc.start();before=time.perf_counter()
    result=client.post(base+'/exports',headers=h,json={'mode':'originals','event_set_ids':[selected['id']],
        'report_ids':[report.json()['id']],'evidence_ids':[item['id'],large['id']]}).json()
    timings['export_seconds']=time.perf_counter()-before
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    assert result['status']=='completed',result
    assert result['byte_size']>16*1024*1024
    print('M5_SYNTHETIC_CAPACITY '+json.dumps({'database':'isolated SQLite','events':2000,'original_bytes':len(records)+16*1024*1024,
        'archive_bytes':result['byte_size'],'export_python_peak_bytes':peak,**timings},sort_keys=True))
