"""Build and verify a non-published release candidate from committed allowlisted source."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
from zipfile import ZipFile, ZIP_STORED

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('provena_archive',ROOT/'backend/app/ops/archive.py')
archive_tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(archive_tools)
SCHEMA='provena-release-candidate/1'
LIMIT=100*1024*1024
import re
SECRET_PATTERNS=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'AKIA[A-Z0-9]{16}'),re.compile(rb'gh[pousr]_[A-Za-z0-9]{36,}')]


def secret_fragment(chunk,tail=b''):
    data=tail+chunk
    if any(pattern.search(data) for pattern in SECRET_PATTERNS):raise ValueError('High-confidence secret pattern detected in release content.')
    return data[-256:]


def release_path(name):
    archive_tools.safe_path(name)
    private={'evidence-storage','export-storage','migration-backup','node_modules','backups','.venv','venv','__pycache__','test-results','playwright-report','models'}
    if any(part.startswith('.env') or part in private for part in Path(name).parts) or Path(name).suffix.lower() in {'.dump','.db','.sqlite','.sqlite3','.pem','.key','.zip'}:
        raise ValueError('Private operational material cannot enter release content.')


SOURCE=['backend/app','backend/alembic','backend/tests','backend/requirements.txt','backend/alembic.ini','backend/Dockerfile',
    'frontend/src','frontend/public','frontend/package.json','frontend/package-lock.json','frontend/index.html','frontend/vite.config.ts',
    'frontend/tsconfig.json','frontend/tsconfig.e2e.json','frontend/playwright.config.ts','frontend/e2e','frontend/eslint.config.js','frontend/vitest.config.ts','README.md','AGENTS.md','tools','docker-compose.yml','backend/.dockerignore',
    'sample-data/m3-authentication','sample-data/m4-authentication','sample-data/m5-operations',
    '.github/workflows/ci.yml','.github/workflows/release-validation.yml']
DOCS=['docs/architecture.md','docs/ai-architecture.md','docs/evidence-integrity.md','docs/development.md',
    'docs/security.md','docs/m2-implementation.md','docs/m3-implementation.md',
    'docs/m4-implementation.md','docs/m5-implementation.md','docs/m6-implementation.md','docs/README.md','docs/investigator-guide.md','docs/operations.md','docs/releases.md',
    'CONTRIBUTING.md','SECURITY.md','CODE_OF_CONDUCT.md','CHANGELOG.md','LICENSE']


def build(frontend,output):
    tracked=set(subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'],cwd=ROOT,text=True).splitlines())
    paths=[path for path in SOURCE if any(name==path or name.startswith(path+'/') for name in tracked)]
    paths += [path for path in DOCS if path in tracked]
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    version_source=subprocess.check_output(['git','show','HEAD:backend/app/version.py'],cwd=ROOT,text=True)
    version=next(ast.literal_eval(node.value) for node in ast.parse(version_source).body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in node.targets))
    frontend_version=json.loads(subprocess.check_output(['git','show','HEAD:frontend/package.json'],cwd=ROOT,text=True))['version']
    if frontend_version!=version: raise ValueError('Committed backend and frontend release versions differ.')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise ValueError('Release output already exists; use a new candidate path.')
    files=[];size=0
    def write(target,name,stream):
        nonlocal size
        release_path(name)
        digest=hashlib.sha256();count=0;tail=b''
        with target.open(name,'w') as destination:
            while chunk:=stream.read(1024*1024):
                size+=len(chunk);count+=len(chunk)
                if size>LIMIT or len(files)>=9998: raise ValueError('Release candidate budget exceeded.')
                tail=secret_fragment(chunk,tail)
                digest.update(chunk);destination.write(chunk)
        files.append({'path':name,'sha256':digest.hexdigest(),'size':count})
    try:
        with ZipFile(output,'x',compression=ZIP_STORED) as package:
            process=subprocess.Popen(['git','archive','--format=tar','HEAD',*paths],cwd=ROOT,stdout=subprocess.PIPE)
            try:
                with tarfile.open(fileobj=process.stdout,mode='r|') as source:
                    for member in source:
                        if member.isdir(): continue
                        if not member.isfile(): raise ValueError('Source release contains a link or special file.')
                        path=archive_tools.safe_path(member.name)
                        if any(part.startswith('.env') or part in ('evidence-storage','export-storage','migration-backup','node_modules','backups','.venv','venv','__pycache__','test-results','playwright-report','models') for part in Path(path).parts):
                            raise ValueError('Private operational material cannot enter a release candidate.')
                        with source.extractfile(member) as handle: write(package,'source/'+path,handle)
                if process.wait(timeout=60)!=0: raise ValueError('Committed source packaging failed.')
            finally:
                if process.poll() is None: process.terminate();process.wait(timeout=10)
                process.stdout.close()
            frontend=Path(frontend).resolve()
            if not (frontend/'index.html').is_file(): raise ValueError('A completed frontend production build is required.')
            for path in sorted(frontend.rglob('*')):
                if path.is_symlink(): raise ValueError('Frontend build contains a symlink.')
                if path.is_file():
                    with path.open('rb') as handle: write(package,'web/'+path.relative_to(frontend).as_posix(),handle)
            manifest={'schema':SCHEMA,'hash_algorithm':'sha256','authenticity':'unsigned-integrity-only',
                'version':version,'commit':commit,'publication':'validation-artifact-only','publishable':False,
                'release_blockers':['Maintainer approval is required before creating a release or tag.'] +
                    ([] if 'LICENSE' in tracked else ['A project license grant has not been approved.']), 'files':files}
            package.writestr('manifest.json',archive_tools.canonical(manifest))
        archive_tools.inspect_package(output,expected_schema=SCHEMA,max_bytes=LIMIT)
        with output.open('rb') as handle: digest,byte_size=archive_tools.file_digest(handle,LIMIT)
        return {'version':version,'commit':commit,'sha256':digest,'size':byte_size,'files':len(files),'publishable':False,'release_blockers':manifest['release_blockers']}
    except Exception:
        output.unlink(missing_ok=True)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=build(args.frontend,args.output)
    Path(str(args.output)+'.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result))
