"""Compare production assets against an independent second Vite build, no deployment."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def inventory(root):
    result={};total=0
    for path in sorted(Path(root).rglob('*')):
        if path.is_symlink():raise ValueError('Build contains a symlink.')
        if path.is_file():
            if len(result)>=10000:raise ValueError('Build file limit exceeded.')
            digest=hashlib.sha256()
            with path.open('rb') as source:
                while chunk:=source.read(1024*1024):
                    total+=len(chunk)
                    if total>100*1024*1024:raise ValueError('Build byte limit exceeded.')
                    digest.update(chunk)
            result[path.relative_to(root).as_posix()]=digest.hexdigest()
    if 'index.html' not in result:raise ValueError('Build index is missing.')
    return result


if __name__=='__main__':
    frontend=ROOT/'frontend'
    first=inventory(frontend/'dist')
    with tempfile.TemporaryDirectory(prefix='provena-repro-build-') as work:
        target=Path(work)/'web'
        subprocess.run(['node','node_modules/vite/bin/vite.js','build','--outDir',str(target)],cwd=frontend,check=True,timeout=180)
        if inventory(target)!=first:raise SystemExit('Production frontend builds differ.')
    print(json.dumps({'reproducible':True,'files':len(first),'scope':'Same source, runtime and environment; not a cross-platform reproducibility guarantee.'}))
