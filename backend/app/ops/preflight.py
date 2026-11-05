"""Read-only deployment diagnostics. Connectivity is explicitly opt-in on the CLI."""
import argparse
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, text


def expected_revision():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    base=Path(__file__).resolve().parents[2]
    config=Config(str(base/'alembic.ini'));config.set_main_option('script_location',str(base/'alembic'))
    return ScriptDirectory.from_config(config).get_current_head()


def database_diagnostics(connection,revision=None):
    connection.execute(text('SELECT 1'))
    actual=connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    return {'connectivity':'ok','migrations':'ok' if actual==[revision or expected_revision()] else 'mismatch'}


def local_directory(path):
    """No probe files or mkdir: examine nearest existing ancestor read-only."""
    target=Path(path).resolve()
    while not target.exists(): target=target.parent
    return 'ok' if target.is_dir() and os.access(target,os.R_OK|os.W_OK|os.X_OK) else 'unavailable'


def diagnostics(config,database=False,storage=False):
    checks={'configuration':'ok','build_id':config.build_id,'migration_target':expected_revision()}
    if database:
        if not config.database_url: checks['database']='not_configured'
        else:
            engine=None
            try:
                options={'connect_timeout':3} if config.database_url.startswith('postgresql') else {}
                engine=create_engine(config.database_url,connect_args=options)
                with engine.connect() as connection: checks['database']=database_diagnostics(connection)
            except Exception: checks['database']='unavailable_or_unmigrated'
            finally:
                if engine is not None: engine.dispose()
    if storage:
        checks['exports']=local_directory(config.export_storage_root)
        if config.evidence_storage_backend=='local':
            from app.modules.evidence.storage import LocalEvidenceStorage
            checks['evidence']='restore_incomplete' if LocalEvidenceStorage(config.evidence_storage_root).restoration_incomplete() else local_directory(config.evidence_storage_root)
        else:
            # A read-only bucket probe is opt-in, never part of offline preflight.
            try:
                from app.modules.evidence.storage import get_storage
                get_storage().client.head_bucket(Bucket=config.s3_evidence_bucket)
                checks['evidence']='ok'
            except Exception: checks['evidence']='unavailable'
    def healthy(value):
        if isinstance(value,dict): return all(healthy(v) for v in value.values())
        return value=='ok'
    required={k:v for k,v in checks.items() if k not in ('build_id','migration_target')}
    return {'ready':all(healthy(v) for v in required.values()),'checks':checks,
            'limitations':['Filesystem permission inspection is read-only; it does not prove disk space, actual writes or external TLS/proxy configuration.']}


def main():
    parser=argparse.ArgumentParser(description='Read-only deployment preflight. No database or storage network calls without explicit flags.')
    parser.add_argument('--database',action='store_true');parser.add_argument('--storage',action='store_true')
    args=parser.parse_args()
    try:
        from app.core.config import settings
        result=diagnostics(settings,args.database,args.storage)
    except Exception:
        result={'ready':False,'checks':{'configuration':'invalid'},'error':'Configuration is invalid. Check environment mode, PostgreSQL URL, signing secret, HTTPS origins, proxy addresses and storage settings. Values are never printed.'}
    print(json.dumps(result));return 0 if result['ready'] else 1


if __name__=='__main__': raise SystemExit(main())
