"""Manual, synthetic CPU and isolated API throughput probes. No production access."""
import json
import time
from app.events.detections import evaluate
from app.modules.detections.schemas import DetectionConfig
from tests.test_m4_engine import event
from tests.test_m4_workbench import scenario, selection, execute


def test_authentication_cpu_benchmark():
    config=DetectionConfig(window_seconds=86400,min_failures=1000,min_occurrences=1000).model_dump()
    for size in (1000,5000,10000):
        data=[event(i,user=f'account{i%50}',outcome='success' if i%3==0 else 'failure') for i in range(size)]
        start=time.perf_counter()
        result,coverage=evaluate(data,config)
        print(json.dumps({'workload':'mixed authentication','events':size,'seconds':round(time.perf_counter()-start,4),'results':len(result),'evaluated':coverage['evaluated']}))
    data=[event(i,outcome='failure' if i<999 else 'success',source_port=i+1,
        original_timestamp='2026-11-05T00:00:00Z',timestamp_utc='2026-11-05T00:00:00Z') for i in range(10000)]
    start=time.perf_counter()
    result,coverage=evaluate(data,config)
    assert not result
    print(json.dumps({'workload':'equal-time temporal exclusion','events':10000,'seconds':round(time.perf_counter()-start,4)}))


def test_authentication_api_benchmark(client,investigator,db_session,storage_dir):
    from tests.test_evidence import upload
    from tests.test_m3_events import ingest
    base,h,_,profile,_,token,_=scenario(client,investigator)
    data=''.join(f'2026-11-05T12:{i//60:02d}:{i%60:02d}Z benchmark sshd[123]: Failed password for account{i%20} from 192.0.2.1 port {2000+i} ssh2\n' for i in range(2000)).encode()
    item=upload(client,token,int(base.rsplit('/',1)[1]),content=data,filename='synthetic-benchmark.log').json()
    client.post(base+f"/evidence/{item['id']}/verify",headers=h).raise_for_status()
    run=ingest(client,base,h,item,profile)
    start=time.perf_counter();selected=selection(client,base,h,[run['id']]);selection_seconds=time.perf_counter()-start
    start=time.perf_counter();result=execute(client,base,h,selected['id']);first=time.perf_counter()-start
    start=time.perf_counter();repeat=execute(client,base,h,selected['id']);retry=time.perf_counter()-start
    assert result['status']==repeat['status']=='completed'
    assert result['coverage']['result_count']==repeat['coverage']['result_count']
    print(json.dumps({'workload':'SQLite synthetic API, not PostgreSQL capacity','events':2000,
        'selection_seconds':round(selection_seconds,4),'first_detection_seconds':round(first,4),'repeat_seconds':round(retry,4),
        'results':result['coverage']['result_count']}))


def test_authentication_postgres_benchmark(tmp_path,monkeypatch):
    import io
    import os
    import uuid
    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    from app.core.config import settings
    from app.modules.users.models import User
    from app.modules.workspaces.models import Workspace
    from app.modules.investigations.models import Investigation
    from app.modules.evidence.models import EvidenceType
    from app.modules.evidence.service import register_evidence, verify_evidence
    from app.modules.events.schemas import ProfileCreate
    from app.modules.events.service import create_profile, ingest
    from app.modules.detections.schemas import EventSetCreate, DetectionCreate
    from app.modules.detections.service import create_set, execute as detect
    url=os.getenv('M1_POSTGRES_TEST_URL')
    if not url: pytest.skip('Disposable PostgreSQL CI database not configured.')
    parsed=make_url(url)
    assert parsed.database=='provena_ci' and parsed.host in {'127.0.0.1','localhost'}
    monkeypatch.setattr(settings,'evidence_storage_backend','local')
    monkeypatch.setattr(settings,'evidence_storage_root',str(tmp_path))
    engine=create_engine(url)
    suffix=uuid.uuid4().hex[:12]
    try:
        with Session(engine) as db:
            actor=User(username=f'bench_{suffix}',email=f'{suffix}@example.test',role='admin',password_hash='unused')
            db.add(actor);db.flush()
            workspace=Workspace(name='Synthetic benchmark',slug=f'bench-{suffix}',created_by_id=actor.id)
            db.add(workspace);db.flush()
            inv=Investigation(title='Synthetic benchmark',case_number=f'BENCH-{suffix}',workspace_id=workspace.id,created_by_id=actor.id,lead_investigator_id=actor.id)
            db.add(inv);db.commit()
            data=''.join(f'2026-11-05T12:{i//60:02d}:{i%60:02d}Z benchmark sshd[123]: Failed password for account{i%20} from 192.0.2.1 port {2000+i} ssh2\n' for i in range(2000)).encode()
            evidence=register_evidence(db,inv,title='Synthetic benchmark',description='',evidence_type=EvidenceType.LOG,source='Synthetic',acquired_at=None,filename='benchmark.log',content_type='text/plain',stream=io.BytesIO(data),actor=actor)
            verify_evidence(db,inv,evidence,actor)
            profile=create_profile(db,inv,ProfileCreate(name='Synthetic UTC',configuration={'adapter':'linux_auth','format':'syslog'}),actor)
            ingestion=ingest(db,inv,evidence.id,profile.id,actor)
            start=time.perf_counter();selected=create_set(db,inv,EventSetCreate(name='Benchmark',run_ids=[ingestion.id]),actor);selection_seconds=time.perf_counter()-start
            start=time.perf_counter();first=detect(db,inv,DetectionCreate(event_set_id=selected.id),actor);first_seconds=time.perf_counter()-start
            start=time.perf_counter();retry=detect(db,inv,DetectionCreate(event_set_id=selected.id),actor);retry_seconds=time.perf_counter()-start
            assert first.status==retry.status=='completed'
            assert first.coverage['result_count']==retry.coverage['result_count']
            print(json.dumps({'workload':'local PostgreSQL 16.15 service probe, not EC2 capacity','events':2000,
                'selection_seconds':round(selection_seconds,4),'first_detection_seconds':round(first_seconds,4),
                'repeat_seconds':round(retry_seconds,4),'results':first.coverage['result_count']}))
    finally:
        engine.dispose()
