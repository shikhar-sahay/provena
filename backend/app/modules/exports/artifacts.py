"""Private generated archives, separate from original evidence storage."""
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
import hashlib
from app.core.config import settings


def root():
    return Path(settings.export_storage_root).resolve()


def path(key):
    if not re.fullmatch('[0-9a-f]{32}\\.zip',key): raise ValueError('Invalid generated artifact identifier.')
    base=root()
    candidate=(base/key).resolve()
    if candidate.parent!=base: raise ValueError('Generated artifact escapes its private root.')
    return candidate


def remove(key):
    path(key).unlink(missing_ok=True)
    # An interrupted process can leave its private builder directory behind.
    # Remove only this operation's known generated file, never recurse or follow links.
    base=root()
    if not base.exists(): return
    for directory in base.glob('building-'+key+'-*'):
        if directory.is_symlink() or directory.resolve().parent!=base or not directory.is_dir():
            raise OSError('Generated temporary directory is unsafe.')
        children=list(directory.iterdir())
        if any(child.name!='package.zip' or child.is_symlink() or not child.is_file() for child in children):
            raise OSError('Generated temporary directory contains unexpected content.')
        for child in children: child.unlink()
        directory.rmdir()


def restore_cache(directory,key,archive,item):
    if not re.fullmatch('[0-9a-f]{32}\\.zip',key): raise ValueError('Invalid restored cache identifier.')
    target=Path(directory)/key
    digest=hashlib.sha256();size=0
    with archive.open(item['path']) as source,target.open('xb') as output:
        while chunk:=source.read(1024*1024):
            size+=len(chunk)
            if size>item['size']: raise ValueError('Restored cache exceeds its recorded size.')
            digest.update(chunk);output.write(chunk)
    if digest.hexdigest()!=item['sha256'] or size!=item['size']: raise ValueError('Restored cache digest mismatch.')


@contextmanager
def building(key):
    base=root();base.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix='building-'+key+'-',dir=base) as directory:
        temporary=Path(directory)/'package.zip'
        yield temporary
        if temporary.stat().st_size>settings.export_max_bytes:
            raise ValueError('Generated package exceeds its size budget.')
        os.chmod(temporary,0o600)
        with temporary.open('r+b') as handle: os.fsync(handle.fileno())
        os.replace(temporary,path(key))
