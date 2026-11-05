"""Snapshot-bound PostgreSQL backups and guarded trusted-backup restoration.

No default database operation. CLI requires a named connection environment variable,
database-name confirmation and sensitive-backup acknowledgement. Restore accepts only
an empty database, fresh evidence/cache roots and an independently supplied package hash.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_STORED
from sqlalchemy import create_engine, MetaData, select, text
from sqlalchemy.engine import make_url
from app.ops.archive import canonical, file_digest, inspect_package, BACKUP_SCHEMA, CHUNK, MAX_FILES

MAX_BACKUP_BYTES=4*1024*1024*1024


def pg_environment(url):
    parsed=make_url(url)
    if not parsed.drivername.startswith('postgresql') or not parsed.database or parsed.database in ('postgres','template0','template1'):
        raise ValueError('An explicit non-system PostgreSQL database is required.')
    environment={k:v for k,v in os.environ.items() if not k.startswith('PG')}
    environment.update(PGHOST=parsed.host or 'localhost',PGPORT=str(parsed.port or 5432),PGDATABASE=parsed.database,
        PGUSER=parsed.username or '',PGPASSWORD=parsed.password or '',PGCONNECT_TIMEOUT='5')
    allowed={'sslmode':'PGSSLMODE','sslrootcert':'PGSSLROOTCERT','sslcert':'PGSSLCERT','sslkey':'PGSSLKEY','options':'PGOPTIONS'}
    for key,value in parsed.query.items():
        if key not in allowed or not isinstance(value,str): raise ValueError('Unsupported PostgreSQL connection option.')
        environment[allowed[key]]=value
    return environment


def native(name,pg_bin=None):
    target=str(Path(pg_bin)/(name+('.exe' if os.name=='nt' else ''))) if pg_bin else shutil.which(name)
    if not target or not Path(target).is_file(): raise ValueError('Required PostgreSQL native utility is unavailable.')
    return target


def fingerprints(connection):
    """Stream every table, hash canonical rows, expose no individual credential fields."""
    metadata=MetaData();metadata.reflect(bind=connection)
    result={};total=0
    for table in sorted(metadata.tables.values(),key=lambda t:t.name):
        if not table.primary_key.columns: raise ValueError('Backup validation requires stable primary keys.')
        digest=hashlib.sha256();count=0
        query=select(table).order_by(*table.primary_key.columns).execution_options(stream_results=True,yield_per=200)
        for row in connection.execute(query).mappings():
            count+=1;total+=1
            if total>2_000_000: raise ValueError('Backup validation row budget exceeded.')
            digest.update(canonical(dict(row)));digest.update(b'\n')
        result[table.name]={'count':count,'sha256':digest.hexdigest()}
    return result


def validate_reports(connection):
    query=text('SELECT content, content_sha256 FROM reports').execution_options(stream_results=True,yield_per=20)
    for row in connection.execute(query).mappings():
        digest=hashlib.sha256(json.dumps(row['content'],sort_keys=True,default=str).encode()).hexdigest()
        if digest!=row['content_sha256']: raise ValueError('Immutable report content hash mismatch.')


class BackupWriter:
    def __init__(self,archive): self.archive=archive;self.files=[];self.size=0
    def write(self,name,chunks):
        if len(self.files)>=MAX_FILES-1: raise ValueError('Backup file budget exceeded.')
        digest=hashlib.sha256();size=0
        with self.archive.open(name,'w',force_zip64=True) as target:
            for chunk in chunks:
                size+=len(chunk);self.size+=len(chunk)
                if self.size>MAX_BACKUP_BYTES-2*1024*1024: raise ValueError('Backup byte budget exceeded.')
                digest.update(chunk);target.write(chunk)
        item={'path':name,'sha256':digest.hexdigest(),'size':size};self.files.append(item)
        return item


def backup(url,output,pg_bin=None):
    """A PostgreSQL exported snapshot binds dump, row fingerprints and evidence inventory."""
    from app.ops.preflight import expected_revision
    from app.modules.evidence import storage
    from app.modules.exports import artifacts
    from app.version import VERSION
    output=Path(output).resolve()
    if output.exists() or not output.parent.is_dir(): raise ValueError('Backup requires a new file in an existing private output directory.')
    repository=Path(__file__).resolve().parents[3]
    if (repository/'.git').exists() and repository in output.parents:
        raise ValueError('Private backups must be written outside the repository.')
    environment=pg_environment(url)
    engine=create_engine(url,connect_args={'connect_timeout':5})
    try:
        with tempfile.TemporaryDirectory(prefix='provena-backup-',dir=output.parent) as directory:
            temporary=Path(directory)/'backup.zip'
            with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
                with connection.begin():
                    connection.execute(text('SET TRANSACTION READ ONLY'))
                    connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
                    revision=connection.scalar(text('SELECT version_num FROM alembic_version'))
                    if revision!=expected_revision(): raise ValueError('Backup schema must match the running application revision.')
                    snapshot=connection.scalar(text('SELECT pg_export_snapshot()'))
                    evidence=list(connection.execute(text('SELECT id,storage_key,sha256,file_size,registration_status,integrity_status FROM evidence ORDER BY id LIMIT 10001')).mappings())
                    if len(evidence)>10000 or any(e['registration_status']!='ready' or e['integrity_status'] in ('mismatch','unavailable') for e in evidence):
                        raise ValueError('Recover incomplete registrations or evidence integrity failures before creating a complete backup.')
                    validate_reports(connection)
                    state=fingerprints(connection)
                    cache=list(connection.execute(text("SELECT artifact_key,package_sha256,byte_size FROM investigation_exports WHERE status='completed' ORDER BY id LIMIT 10001")).mappings())
                    manifest={'schema':BACKUP_SCHEMA,'hash_algorithm':'sha256','authenticity':'unsigned-integrity-only',
                        'created_at':datetime.now(timezone.utc).isoformat(),'application_version':VERSION,'database_revision':revision,
                        'consistency':'PostgreSQL exported REPEATABLE READ snapshot plus exact immutable baseline-verified evidence copies.',
                        'table_fingerprints':state,'evidence':[],'export_cache':[],
                        'warnings':['Private backup includes confidential evidence and database account hashes. Encrypt and restrict access outside this tool.',
                            'Running operations remain running in the database snapshot and require explicit recovery after restoration.',
                            'Configuration secrets, database roles, TLS keys and external infrastructure are not included.'], 'files':[]}
                    with ZipFile(temporary,'w',compression=ZIP_STORED,allowZip64=True) as archive:
                        writer=BackupWriter(archive)
                        with tempfile.TemporaryFile() as errors:
                            process=subprocess.Popen([native('pg_dump',pg_bin),'--format=custom','--no-owner','--no-acl',f'--snapshot={snapshot}'],env=environment,stdout=subprocess.PIPE,stderr=errors)
                            try:
                                writer.write('database.dump',iter(lambda:process.stdout.read(CHUNK),b''))
                                if process.wait(timeout=600)!=0: raise ValueError('Native PostgreSQL backup failed. Check protected operator diagnostics.')
                            finally:
                                if process.poll() is None: process.terminate();process.wait(timeout=10)
                                process.stdout.close()
                        for row in evidence:
                            storage.validate_storage_key(row['storage_key'])
                            with storage.snapshot(row['storage_key'],row['file_size']) as copied:
                                if copied.sha256!=row['sha256'] or copied.size!=row['file_size']: raise ValueError('Evidence backup baseline mismatch.')
                                item=writer.write(f"evidence/{row['id']}.bin",iter(lambda:copied.handle.read(CHUNK),b''))
                            manifest['evidence'].append({'id':row['id'],'storage_key':row['storage_key'],'sha256':row['sha256'],'size':row['file_size'],'path':item['path']})
                        for row in cache:
                            with artifacts.path(row['artifact_key']).open('rb') as handle:
                                item=writer.write('exports/'+row['artifact_key'],iter(lambda:handle.read(CHUNK),b''))
                            if item['sha256']!=row['package_sha256'] or item['size']!=row['byte_size']: raise ValueError('Export cache backup mismatch.')
                            manifest['export_cache'].append({'artifact_key':row['artifact_key'],**item})
                        manifest['files']=writer.files
                        encoded=canonical(manifest)
                        if len(encoded)>2*1024*1024: raise ValueError('Backup manifest budget exceeded.')
                        archive.writestr('manifest.json',encoded)
            inspect_package(temporary,expected_schema=BACKUP_SCHEMA,max_bytes=MAX_BACKUP_BYTES)
            with temporary.open('rb') as handle: digest,size=file_digest(handle,MAX_BACKUP_BYTES)
            os.chmod(temporary,0o600)
            with temporary.open('r+b') as handle: os.fsync(handle.fileno())
            os.link(temporary,output)  # Never overwrite another backup, including a concurrent creator.
            return {'sha256':digest,'size':size,'evidence_count':len(evidence),'schema':BACKUP_SCHEMA}
    finally:
        engine.dispose()


def restore(url,package,evidence_root,exports_root,expected_sha256,pg_bin=None):
    """Trusted private backups only. Empty database and brand-new roots are mandatory."""
    from app.ops.preflight import expected_revision
    from app.modules.evidence.storage import LocalEvidenceStorage
    from app.modules.exports import artifacts
    environment=pg_environment(url)
    engine=create_engine(url,connect_args={'connect_timeout':5})
    try:
        with tempfile.TemporaryFile(mode='w+b') as snapshot:
            digest=hashlib.sha256();size=0
            with Path(package).open('rb') as source:
                while chunk:=source.read(CHUNK):
                    size+=len(chunk)
                    if size>MAX_BACKUP_BYTES: raise ValueError('Backup archive exceeds restore budget.')
                    digest.update(chunk);snapshot.write(chunk)
            if digest.hexdigest()!=expected_sha256: raise ValueError('Trusted backup SHA-256 does not match.')
            snapshot.seek(0)
            manifest=inspect_package(snapshot,expected_schema=BACKUP_SCHEMA,max_bytes=MAX_BACKUP_BYTES)
            if manifest.get('database_revision')!=expected_revision(): raise ValueError('Use the application release matching this backup schema revision.')
            with engine.connect() as connection:
                # Empty means no user objects, not merely no ordinary tables.
                occupied=connection.scalar(text("""SELECT EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                      WHERE left(n.nspname,3)<>'pg_' AND n.nspname<>'information_schema'
                    UNION ALL SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                      WHERE left(n.nspname,3)<>'pg_' AND n.nspname<>'information_schema'
                    UNION ALL SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
                      WHERE left(n.nspname,3)<>'pg_' AND n.nspname<>'information_schema'
                    UNION ALL SELECT 1 FROM pg_namespace n
                      WHERE left(n.nspname,3)<>'pg_' AND n.nspname NOT IN ('public','information_schema')
                    UNION ALL SELECT 1 FROM pg_largeobject_metadata
                )"""))
                if occupied: raise ValueError('Restore target database is not empty. Existing objects will never be overwritten.')
            target=LocalEvidenceStorage(evidence_root)
            evidence_path,cache_path=Path(evidence_root).resolve(),Path(exports_root).resolve()
            if evidence_path==cache_path or evidence_path in cache_path.parents or cache_path in evidence_path.parents:
                raise ValueError('Restore evidence and cache roots must be separate and non-nested.')
            if Path(exports_root).exists(): raise ValueError('Restore cache directory already exists.')
            target.prepare_restore()
            Path(exports_root).mkdir(parents=True,exist_ok=False,mode=0o700)
            with ZipFile(snapshot) as archive:
                with tempfile.TemporaryFile() as errors:
                    process=subprocess.Popen([native('pg_restore',pg_bin),'--single-transaction','--no-owner','--no-acl','--exit-on-error',f"--dbname={environment['PGDATABASE']}"],env=environment,stdin=subprocess.PIPE,stderr=errors,stdout=errors)
                    try:
                        with archive.open('database.dump') as dump:
                            while chunk:=dump.read(CHUNK): process.stdin.write(chunk)
                        process.stdin.close()
                        if process.wait(timeout=600)!=0: raise ValueError('Native restore failed. Target remains offline; inspect protected operator diagnostics.')
                    finally:
                        if process.poll() is None: process.terminate();process.wait(timeout=10)
                for item in manifest['evidence']:
                    with archive.open(item['path']) as source:
                        target.restore_verified(item['storage_key'],source,item['sha256'],item['size'])
                for item in manifest['export_cache']:
                    artifacts.restore_cache(exports_root,item['artifact_key'],archive,item)
            with engine.connect() as connection:
                connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
                validate_reports(connection)
                if fingerprints(connection)!=manifest['table_fingerprints']:
                    raise ValueError('Restored database fingerprints differ. Keep the target offline.')
            target.complete_restore()
            return {'restored':True,'evidence_count':len(manifest['evidence']),'database_revision':manifest['database_revision'],
                'warnings':manifest['warnings']}
    finally:
        engine.dispose()


def main():
    parser=argparse.ArgumentParser(description='Private snapshot backup and trusted empty-target restoration. Never overwrites existing state.')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('backup','restore'):
        command=sub.add_parser(name)
        command.add_argument('--database-url-env',required=True);command.add_argument('--confirm-database',required=True)
        command.add_argument('--pg-bin');command.add_argument('--acknowledge-sensitive-backup',action='store_true',required=True)
        if name=='backup': command.add_argument('--output',required=True)
        else:
            command.add_argument('--package',required=True);command.add_argument('--evidence-root',required=True)
            command.add_argument('--exports-root',required=True);command.add_argument('--expect-sha256',required=True)
            command.add_argument('--trust-backup',action='store_true',required=True)
    args=parser.parse_args()
    try:
        url=os.environ.get(args.database_url_env,'')
        if make_url(url).database!=args.confirm_database: raise ValueError('Database confirmation does not match the target.')
        result=backup(url,args.output,args.pg_bin) if args.command=='backup' else restore(url,args.package,args.evidence_root,args.exports_root,args.expect_sha256,args.pg_bin)
        print(json.dumps(result));return 0
    except Exception:
        print(json.dumps({'success':False,'error':'Operation failed or safety validation rejected the target. Existing state is never overwritten. Check schema, trusted package hash, evidence integrity, free space and native-tool compatibility; incomplete restore targets must stay offline.'}));return 1


if __name__=='__main__': raise SystemExit(main())
