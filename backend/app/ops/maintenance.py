"""Explicit bounded cleanup of generated artifacts, never original evidence."""
import argparse
import json
import os
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
from sqlalchemy import create_engine, select, and_, or_
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def prune(url,recover_interrupted=False):
    from app.api.router import router  # Register the complete schema without invoking endpoints.
    from app.modules.exports.models import InvestigationExport
    from app.modules.exports.service import recover, expired
    from app.modules.investigations.models import Investigation
    from app.core.config import settings
    engine=create_engine(url)
    closed=0
    try:
        with Session(engine) as db:
            cutoff=datetime.now(timezone.utc)-timedelta(hours=settings.export_retention_hours)
            eligible=[and_(InvestigationExport.status=='completed',InvestigationExport.created_at<cutoff),
                and_(InvestigationExport.status=='failed',InvestigationExport.manifest_summary['cleanup_pending'].as_boolean().is_(True))]
            if recover_interrupted: eligible.append(InvestigationExport.status=='running')
            ids=list(db.scalars(select(InvestigationExport.id).where(or_(*eligible)).order_by(InvestigationExport.id).limit(5000)))
            for ident in ids:
                item=db.get(InvestigationExport,ident)
                if ((item.status=='completed' and expired(item)) or item.manifest_summary.get('cleanup_pending') or
                    (recover_interrupted and item.status=='running')):
                    recover(db,db.get(Investigation,item.investigation_id),item,SimpleNamespace(id=None),prune=True)
                    closed+=1
        return {'closed_operations':closed,'scan_limit':5000,'source_evidence_modified':False}
    finally: engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url-env',required=True);parser.add_argument('--confirm-database',required=True)
    parser.add_argument('--recover-interrupted',action='store_true')
    args=parser.parse_args()
    try:
        url=os.environ.get(args.database_url_env,'')
        if make_url(url).database!=args.confirm_database: raise ValueError('Confirmation mismatch.')
        print(json.dumps(prune(url,args.recover_interrupted)));return 0
    except Exception:
        print(json.dumps({'success':False,'error':'Cleanup failed safely. Check the explicit target and generated storage permissions.'}));return 1


if __name__=='__main__': raise SystemExit(main())
