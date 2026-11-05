"""Offline archive integrity checks. Never extract or execute archive contents."""
import hashlib
import json
import re
import stat
from pathlib import PurePosixPath
from datetime import datetime,timedelta
from zipfile import ZipFile, BadZipFile, ZIP_STORED, ZIP_DEFLATED

EXPORT_SCHEMA = 'provena-investigation-export/1'
BACKUP_SCHEMA = 'provena-system-backup/1'
MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 10000
MANIFEST_LIMIT = 2 * 1024 * 1024
CHUNK = 1024 * 1024


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False,default=str).encode('utf-8')


def safe_path(value):
    if not isinstance(value,str) or not value or len(value)>240 or '\\' in value:
        raise ValueError('Unsafe archive path.')
    path=PurePosixPath(value)
    if path.is_absolute() or str(path)!=value or any(p in ('.','..') or not re.fullmatch(r'[A-Za-z0-9_.-]+',p) for p in path.parts):
        raise ValueError('Unsafe archive path.')
    return value


def file_digest(handle,limit=MAX_BYTES):
    digest=hashlib.sha256();size=0
    while chunk:=handle.read(CHUNK):
        size+=len(chunk)
        if size>limit: raise ValueError('File exceeds verification budget.')
        digest.update(chunk)
    return digest.hexdigest(),size


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate JSON manifest key.')
        result[key]=value
    return result


def positive_id(value):
    return isinstance(value,int) and not isinstance(value,bool) and value>0


def digest_reference(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def string_list(value,limit=100,max_length=2000):
    return isinstance(value,list) and len(value)<=limit and all(isinstance(item,str) and len(item)<=max_length for item in value)


def creation_time(value):
    try:
        if not isinstance(value,str) or len(value)>64: raise ValueError()
        parsed=datetime.fromisoformat(value)
        if parsed.utcoffset()!=timedelta(0): raise ValueError()
    except (ValueError,TypeError): raise ValueError('Manifest creation time must be a valid UTC timestamp.') from None


def export_provenance(manifest):
    creation_time(manifest.get('created_at'))
    actor,case,selection=manifest.get('actor'),manifest.get('investigation'),manifest.get('selection')
    if not isinstance(actor,dict) or not positive_id(actor.get('id')) or not isinstance(actor.get('username'),str) or not 1<=len(actor['username'])<=128:
        raise ValueError('Invalid export actor reference.')
    if not isinstance(case,dict) or not positive_id(case.get('id')) or not positive_id(manifest.get('export_id')):
        raise ValueError('Invalid export investigation reference.')
    if any(not isinstance(case.get(key),str) or not 1<=len(case[key])<=512 for key in ('case_number','title')):
        raise ValueError('Missing export investigation metadata.')
    if not isinstance(selection,dict) or set(selection)!= {'mode','event_set_ids','report_ids','evidence_ids'} or selection['mode']!=manifest.get('mode'):
        raise ValueError('Invalid explicit export selection.')
    for key,limit in (('event_set_ids',20),('report_ids',100),('evidence_ids',100)):
        values=selection[key]
        if not isinstance(values,list) or len(values)>limit or not all(positive_id(v) for v in values) or values!=sorted(set(values)):
            raise ValueError('Invalid export selection identifiers.')
    if manifest.get('mode') not in ('metadata','originals') or (manifest['mode']=='originals')!=bool(selection['evidence_ids']):
        raise ValueError('Export mode and original evidence selection differ.')
    keys,coverage=manifest.get('event_set_keys'),manifest.get('coverage')
    if not isinstance(keys,list) or len(keys)!=len(selection['event_set_ids']) or not all(digest_reference(v) for v in keys) or len(set(keys))!=len(keys):
        raise ValueError('Invalid event-set provenance inventory.')
    if not isinstance(coverage,list) or len(coverage)!=len(keys) or not all(isinstance(v,dict) for v in coverage):
        raise ValueError('Missing event-set coverage metadata.')
    if not string_list(manifest.get('warnings')) or not string_list(manifest.get('processing_versions'),20000,128):
        raise ValueError('Invalid processing versions or limitations.')


def backup_provenance(manifest):
    creation_time(manifest.get('created_at'))
    for key in ('database_revision','application_version','consistency'):
        if not isinstance(manifest.get(key),str) or not 1<=len(manifest[key])<=512:
            raise ValueError('Missing backup version or consistency metadata.')
    if not string_list(manifest.get('warnings')): raise ValueError('Missing backup limitations.')
    fingerprints=manifest.get('table_fingerprints')
    if not isinstance(fingerprints,dict) or not fingerprints or len(fingerprints)>1000 or 'alembic_version' not in fingerprints:
        raise ValueError('Missing database schema fingerprint.')
    total=0
    for table,item in fingerprints.items():
        if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,62}',table) or not isinstance(item,dict): raise ValueError('Invalid table fingerprint.')
        count=item.get('count')
        if not isinstance(count,int) or isinstance(count,bool) or count<0 or not digest_reference(item.get('sha256')): raise ValueError('Invalid table fingerprint.')
        total+=count
    if total>2_000_000 or fingerprints['alembic_version']['count']!=1: raise ValueError('Invalid database fingerprint coverage.')


def inspect_package(path,expected_schema=EXPORT_SCHEMA,max_bytes=MAX_BYTES):
    """Return a validated manifest or fail closed with a safe diagnostic."""
    try:
        with ZipFile(path) as archive:
            entries=archive.infolist()
            if not 1<len(entries)<=MAX_FILES: raise ValueError('Invalid archive file count.')
            names=set();total=0
            for entry in entries:
                name=safe_path(entry.filename)
                if entry.orig_filename!=entry.filename: raise ValueError('Ambiguous archive filename.')
                if name in names: raise ValueError('Duplicate archive entry.')
                names.add(name);total+=entry.file_size
                mode=entry.external_attr>>16
                if entry.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not stat.S_ISREG(mode)):
                    raise ValueError('Archive contains a non-regular file.')
                if entry.flag_bits&1 or entry.compress_type not in (ZIP_STORED,ZIP_DEFLATED):
                    raise ValueError('Encrypted or unsupported compression.')
                if entry.file_size<0 or total>max_bytes or entry.file_size>max(1,entry.compress_size)*100:
                    raise ValueError('Archive exceeds decompression budget.')
            if 'manifest.json' not in names or archive.getinfo('manifest.json').file_size>MANIFEST_LIMIT:
                raise ValueError('Manifest is missing or oversized.')
            with archive.open('manifest.json') as handle:
                manifest=json.loads(handle.read(MANIFEST_LIMIT+1).decode('utf-8'),object_pairs_hook=unique_object)
            if not isinstance(manifest,dict) or manifest.get('schema')!=expected_schema:
                raise ValueError('Unsupported package schema/version.')
            if manifest.get('hash_algorithm')!='sha256' or manifest.get('authenticity')!='unsigned-integrity-only':
                raise ValueError('Unsupported manifest validation metadata.')
            files=manifest.get('files')
            if not isinstance(files,list) or len(files)>MAX_FILES-1:
                raise ValueError('Invalid manifest file inventory.')
            inventory={}
            for item in files:
                if not isinstance(item,dict) or set(item)!= {'path','sha256','size'}:
                    raise ValueError('Invalid manifest file entry.')
                name=safe_path(item['path'])
                if name=='manifest.json' or name in inventory or not isinstance(item['size'],int) or isinstance(item['size'],bool) or not 0<=item['size']<=max_bytes:
                    raise ValueError('Invalid manifest file entry.')
                if not isinstance(item['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',item['sha256']):
                    raise ValueError('Invalid SHA-256 reference.')
                inventory[name]=item
            if names!={'manifest.json',*inventory}:
                raise ValueError('Missing or unexpected package files.')
            for name,item in inventory.items():
                if archive.getinfo(name).file_size!=item['size']:
                    raise ValueError('File size mismatch.')
                with archive.open(name) as handle:
                    observed,size=file_digest(handle,min(max_bytes,item['size']))
                if observed!=item['sha256'] or size!=item['size']:
                    raise ValueError('File digest mismatch.')
            if expected_schema==EXPORT_SCHEMA:
                export_provenance(manifest)
                if not isinstance(manifest.get('reports'),list) or not isinstance(manifest.get('evidence'),list):
                    raise ValueError('Invalid provenance inventory.')
                if manifest.get('mode') not in ('metadata','originals'):
                    raise ValueError('Invalid export mode.')
                report_ids=[];original_ids=[];evidence_ids=[]
                for report in manifest.get('reports',[]):
                    if not positive_id(report.get('id')) or report.get('path')!=f"reports/{report['id']}.json" or report.get('path') not in inventory or inventory[report['path']]['sha256']!=report.get('content_sha256'):
                        raise ValueError('Embedded immutable report hash mismatch.')
                    report_ids.append(report['id'])
                if sorted(report_ids)!=manifest['selection']['report_ids']: raise ValueError('Embedded reports differ from the explicit selection.')
                for evidence in manifest.get('evidence',[]):
                    if not isinstance(evidence,dict) or not positive_id(evidence.get('id')) or not digest_reference(evidence.get('sha256')) or not isinstance(evidence.get('size'),int) or isinstance(evidence['size'],bool) or evidence['size']<0:
                        raise ValueError('Invalid evidence baseline reference.')
                    evidence_ids.append(evidence['id'])
                    name=evidence.get('included_path')
                    if name is not None and (name!=f"evidence/{evidence['id']}.bin" or manifest['mode']!='originals' or name not in inventory or inventory[name]['sha256']!=evidence.get('sha256') or inventory[name]['size']!=evidence.get('size')):
                        raise ValueError('Original evidence baseline mismatch.')
                    if name is not None: original_ids.append(evidence['id'])
                if len(evidence_ids)>1000 or len(set(evidence_ids))!=len(evidence_ids) or sorted(original_ids)!=manifest['selection']['evidence_ids']:
                    raise ValueError('Original evidence inventory differs from the explicit selection.')
            elif expected_schema==BACKUP_SCHEMA:
                backup_provenance(manifest)
                if 'database.dump' not in inventory or not isinstance(manifest.get('table_fingerprints'),dict) or not isinstance(manifest.get('database_revision'),str):
                    raise ValueError('Missing backup database validation metadata.')
                if not isinstance(manifest.get('evidence'),list) or not isinstance(manifest.get('export_cache'),list):
                    raise ValueError('Invalid backup content inventory.')
                referenced={'database.dump'};keys=set()
                for evidence in manifest['evidence']:
                    key=evidence.get('storage_key')
                    if not isinstance(key,str) or not re.fullmatch('[1-9][0-9]*/[0-9a-f]{32}',key) or key in keys:
                        raise ValueError('Invalid or repeated backup storage identifier.')
                    keys.add(key);name=evidence.get('path')
                    if name not in inventory or inventory[name]['sha256']!=evidence.get('sha256') or inventory[name]['size']!=evidence.get('size'):
                        raise ValueError('Backup evidence reference mismatch.')
                    referenced.add(name)
                for item in manifest['export_cache']:
                    key=item.get('artifact_key');name=item.get('path')
                    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{32}\\.zip',key) or name!='exports/'+key or name not in inventory:
                        raise ValueError('Invalid backup cache reference.')
                    if inventory[name]['sha256']!=item.get('sha256') or inventory[name]['size']!=item.get('size'):
                        raise ValueError('Backup cache digest mismatch.')
                    referenced.add(name)
                if set(inventory)!=referenced: raise ValueError('Unreferenced backup content.')
            return manifest
    except (BadZipFile,RuntimeError,OSError,UnicodeError,json.JSONDecodeError,KeyError,TypeError,AttributeError,RecursionError) as exc:
        raise ValueError('Package is malformed, inaccessible or inconsistent.') from exc


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Verify unsigned Provena packages offline; never execute or extract content.')
    parser.add_argument('package')
    parser.add_argument('--kind',choices=('export','backup'),default='export')
    args=parser.parse_args()
    try:
        manifest=inspect_package(args.package,expected_schema=BACKUP_SCHEMA if args.kind=='backup' else EXPORT_SCHEMA,
            max_bytes=4*1024**3 if args.kind=='backup' else MAX_BYTES)
        print(json.dumps({'valid':True,'schema':manifest['schema'],'files':len(manifest['files']),
            'meaning':'Integrity consistency only; not authenticity, certification or independent proof of provenance.'}))
        return 0
    except ValueError as exc:
        print(json.dumps({'valid':False,'error':str(exc)}))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
