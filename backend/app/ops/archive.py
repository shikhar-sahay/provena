"""Offline archive integrity checks. Never extract or execute archive contents."""
import hashlib
import json
import re
import stat
from pathlib import PurePosixPath
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
                if not isinstance(manifest.get('actor'),dict) or not isinstance(manifest.get('investigation'),dict) or not isinstance(manifest.get('created_at'),str):
                    raise ValueError('Missing export provenance metadata.')
                if not isinstance(manifest.get('reports'),list) or not isinstance(manifest.get('evidence'),list):
                    raise ValueError('Invalid provenance inventory.')
                if manifest.get('mode') not in ('metadata','originals'):
                    raise ValueError('Invalid export mode.')
                for report in manifest.get('reports',[]):
                    if report.get('path') not in inventory or inventory[report['path']]['sha256']!=report.get('content_sha256'):
                        raise ValueError('Embedded immutable report hash mismatch.')
                for evidence in manifest.get('evidence',[]):
                    if not isinstance(evidence,dict) or not isinstance(evidence.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',evidence['sha256']):
                        raise ValueError('Invalid evidence baseline reference.')
                    name=evidence.get('included_path')
                    if name is not None and (manifest['mode']!='originals' or name not in inventory or inventory[name]['sha256']!=evidence.get('sha256') or inventory[name]['size']!=evidence.get('size')):
                        raise ValueError('Original evidence baseline mismatch.')
            elif expected_schema==BACKUP_SCHEMA:
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
