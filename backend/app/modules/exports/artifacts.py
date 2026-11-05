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
    with tempfile.TemporaryDirectory(prefix='building-',dir=base) as directory:
        temporary=Path(directory)/'package.zip'
        yield temporary
        if temporary.stat().st_size>settings.export_max_bytes:
            raise ValueError('Generated package exceeds its size budget.')
        os.chmod(temporary,0o600)
        with temporary.open('r+b') as handle: os.fsync(handle.fileno())
        os.replace(temporary,path(key))
