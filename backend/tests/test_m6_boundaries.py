"""Authorized-in-both-cases identifiers still cannot cross case boundaries."""
from sqlalchemy import event
from tests.test_m5_exports import package
from tests.test_evidence import make_investigation
from tests.conftest import login


def test_cross_case_export_and_event_references_fail_closed(client,investigator,db_session,storage_dir,tmp_path,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'export_storage_root',str(tmp_path/'exports'))
    base,h,item,selected,report=package(client,investigator,db_session)
    other=make_investigation(client,login(client,investigator.username))
    foreign=f"/api/investigations/{other['id']}"
    failed=client.post(foreign+'/exports',headers=h,json={'mode':'metadata','report_ids':[report['id']],'event_set_ids':[selected['id']]}).json()
    assert failed['status']=='failed'
    exported=client.post(base+'/exports',headers=h,json={'mode':'metadata'}).json()
    assert exported['status']=='completed'
    assert client.get(foreign+f"/exports/{exported['id']}/download",headers=h).status_code==404
    events=client.get(base+'/events?limit=200',headers=h).json()
    key=events['items'][0]['semantic_key']
    assert client.get(foreign+'/events/'+key,headers=h).status_code==404
    assert client.get(foreign+f"/authentication/findings/{report['content']['accepted_findings'][0]['id']}/history",headers=h).status_code==404


def test_event_pagination_query_count_is_bounded(client,investigator,db_session,storage_dir,tmp_path,monkeypatch):
    from app.core.config import settings
    from tests.test_m3_events import ingest
    from tests.test_evidence import upload
    from tests.conftest import auth_headers
    monkeypatch.setattr(settings,'export_storage_root',str(tmp_path/'exports'))
    token=login(client,investigator.username);h=auth_headers(token)
    inv=make_investigation(client,token);base=f"/api/investigations/{inv['id']}"
    content=b'2026-11-06T12:00:00Z lab sshd[1]: Failed password for synthetic from 192.0.2.1 port 2200 ssh2\n'*300
    item=upload(client,token,inv['id'],content=content).json()
    client.post(base+f"/evidence/{item['id']}/verify",headers=h)
    profile=client.post(base+'/events/profiles',headers=h,json={'name':'Capacity','configuration':{'adapter':'linux_auth','format':'syslog'}}).json()
    assert ingest(client,base,h,item,profile)['status']=='completed'
    queries=[]
    def count(*args):queries.append(True)
    engine=db_session.get_bind();event.listen(engine,'before_cursor_execute',count)
    try:
        small=client.get(base+'/events?limit=50',headers=h);baseline=len(queries);queries.clear()
        large=client.get(base+'/events?limit=200',headers=h)
        assert small.status_code==large.status_code==200
        assert len(large.json()['items'])==200 and large.json()['total']==300
        assert len(queries)<=baseline+3 and len(queries)<20
        print(f'M6_EVENT_QUERIES page50={baseline} page200={len(queries)} database=SQLite')
    finally:event.remove(engine,'before_cursor_execute',count)
