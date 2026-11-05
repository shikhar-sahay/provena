"""Manual M3 throughput probe with synthetic, isolated test fixtures."""
import time
from tests.test_m3_events import setup,ingest,DATA
from tests.test_evidence import upload


def test_m3_throughput(client,investigator,db_session,storage_dir):
    base,headers,_,profile,token,inv=setup(client,investigator,db_session)
    item=upload(client,token,inv['id'],content=DATA*2000,filename='throughput.log').json()
    client.post(f"{base}/evidence/{item['id']}/verify",headers=headers)
    started=time.perf_counter()
    result=ingest(client,base,headers,item,profile)
    first=time.perf_counter()-started
    started=time.perf_counter()
    retry=ingest(client,base,headers,item,profile)
    repeat=time.perf_counter()-started
    assert result['coverage']['recognized']==2000 and retry['coverage']['events_created']==0
    print(f'M3 synthetic 2000 events: first ingestion {first:.3f}s; identical retry {repeat:.3f}s; zero duplicates.')
