"""Manual synthetic performance probe. Run from backend; no production I/O."""
import io,json,os,sys,tempfile,time,statistics
# Override local environment configuration before app/session initialization.
os.environ['APP_ENV'] = 'test'
os.environ['DATABASE_URL'] = ''
os.environ['EVIDENCE_STORAGE_BACKEND'] = 'local'
sys.path.insert(0,os.getcwd())
import app.main
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.session import Base
from app.core.config import settings
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace
from app.modules.investigations.models import Investigation
from app.modules.evidence.models import EvidenceType
from app.modules.evidence.service import register_evidence, verify_evidence
from app.modules.intelligence.service import start_run
from app.modules.intelligence.reasoning import generate_findings
samples=[]
for trial in range(3):
 engine=create_engine('sqlite://'); Base.metadata.create_all(engine)
 settings.evidence_storage_backend='local';settings.evidence_storage_root=tempfile.mkdtemp(prefix='provena-m2-bench-storage-')
 with Session(engine,autoflush=False) as db:
  actor=User(username='synthetic',email='synthetic@example.test',full_name='Synthetic',password_hash='unused',role='admin');db.add(actor);db.flush()
  ws=Workspace(name='Synthetic',slug='synthetic',created_by_id=actor.id);db.add(ws);db.flush()
  inv=Investigation(title='Synthetic benchmark',case_number='SYNTHETIC',workspace_id=ws.id,created_by_id=actor.id,lead_investigator_id=actor.id);db.add(inv);db.commit()
  ids=[]
  for file in range(3):
   data=''.join(f'2026-01-01T01:{i//60:02d}:{i%60:02d}Z user=synthetic{i%5} host=WS-17 ip=192.0.2.10\n' for i in range(80)).encode()
   ev=register_evidence(db,inv,title='Synthetic',description='',evidence_type=EvidenceType.LOG,source='Synthetic',acquired_at=None,filename=f'{file}.log',content_type='text/plain',stream=io.BytesIO(data),actor=actor)
   verify_evidence(db,inv,ev,actor);ids.append(ev.id)
  t=time.perf_counter();run=start_run(db,inv,ids,actor);analysis=time.perf_counter()-t
  assert run.status=='completed',run.error
  t=time.perf_counter();findings,_=generate_findings(db,inv,actor);reasoning=time.perf_counter()-t
  samples.append({'analysis_seconds':analysis,'reasoning_seconds':reasoning,'artifacts':run.artifact_count,'findings':len(findings)})
 engine.dispose()
print(json.dumps({'samples':samples,'median_analysis':statistics.median(x['analysis_seconds'] for x in samples),'median_reasoning':statistics.median(x['reasoning_seconds'] for x in samples)}))
