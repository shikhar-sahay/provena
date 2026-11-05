"""Run real Chromium against an owned disposable localhost PostgreSQL application."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]


def control_url(value):
    url=make_url(value)
    if url.drivername!='postgresql+psycopg2' or url.host not in ('127.0.0.1','localhost') or url.database!='provena_ci' or url.query:
        raise ValueError('E2E requires a dedicated localhost provena_ci control database without connection options.')
    return url


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def wait_ready(url,process):
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        if process.poll() is not None: raise RuntimeError('Disposable server exited before readiness. Inspect synthetic logs.')
        try:
            with urllib.request.urlopen(url,timeout=2) as response:
                if response.status==200:return
        except OSError:pass
        time.sleep(.15)
    raise RuntimeError('Disposable server readiness timed out.')


def run(value,artifacts,extra):
    parsed=control_url(value);name='provena_e2e_'+uuid.uuid4().hex
    controller=create_engine(value,connect_args={'connect_timeout':5})
    processes=[];logs=[];created=False
    workspace=tempfile.TemporaryDirectory(prefix='provena-m6-e2e-')
    work=workspace.name
    artifacts=Path(artifacts).resolve()/name;artifacts.mkdir(parents=True,exist_ok=False,mode=0o700)
    try:
        with controller.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"');created=True
        api,web=port(),port()
        while api==web:web=port()
        environment={**os.environ,'APP_ENV':'test','DATABASE_URL':parsed.set(database=name).render_as_string(hide_password=False),
            'SECRET_KEY':secrets.token_urlsafe(48),'EVIDENCE_STORAGE_BACKEND':'local',
            'EVIDENCE_STORAGE_ROOT':str(Path(work)/'evidence'),'EXPORT_STORAGE_ROOT':str(Path(work)/'exports'),
            'CORS_ORIGINS':f'http://127.0.0.1:{web}','TRUSTED_PROXY_IPS':'','LLM_ENABLED':'false',
            'VITE_API_URL':f'http://127.0.0.1:{api}','M6_E2E':'1','M6_API_URL':f'http://127.0.0.1:{api}',
            'M6_WEB_URL':f'http://127.0.0.1:{web}','M6_PYTHON':sys.executable,'M6_ARTIFACTS':str(artifacts)}
        with (artifacts/'setup.log').open('w',encoding='utf-8') as setup:
            for command,cwd in [([sys.executable,'-m','alembic','upgrade','head'],ROOT/'backend'),
                (['node','node_modules/typescript/bin/tsc'],ROOT/'frontend'),
                (['node','node_modules/vite/bin/vite.js','build'],ROOT/'frontend')]:
                subprocess.run(command,cwd=cwd,env=environment,stdout=setup,stderr=setup,check=True,timeout=180)
        for command,cwd,label in [([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(api)],ROOT/'backend','api'),
            (['node','node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port',str(web),'--strictPort'],ROOT/'frontend','web')]:
            log=(artifacts/(label+'.log')).open('w',encoding='utf-8');logs.append(log)
            processes.append(subprocess.Popen(command,cwd=cwd,env=environment,stdout=log,stderr=log))
        wait_ready(environment['M6_API_URL']+'/api/ready',processes[0]);wait_ready(environment['M6_WEB_URL'],processes[1])
        result=subprocess.run(['node','node_modules/@playwright/test/cli.js','test',*extra],cwd=ROOT/'frontend',env=environment,timeout=900)
        return result.returncode
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        for log in logs:log.close()
        workspace.cleanup()
        if created:
            # Only the randomly named database created by this invocation is eligible.
            assert name.startswith('provena_e2e_') and len(name)==44
            with controller.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
                connection.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()'),{'name':name})
                connection.exec_driver_sql(f'DROP DATABASE "{name}"')
        controller.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url-env',default='M6_POSTGRES_TEST_URL')
    parser.add_argument('--artifacts',default=str(ROOT/'frontend/test-results'))
    args,extra=parser.parse_known_args()
    try:raise SystemExit(run(os.environ.get(args.database_url_env,''),args.artifacts,extra))
    except Exception:
        print(json.dumps({'success':False,'error':'E2E failed safely. Use only the dedicated local control database and inspect synthetic test artifacts.'}));raise SystemExit(1)
