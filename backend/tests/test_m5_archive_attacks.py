"""Bounded offline checks for hostile archives; no extraction occurs."""
import io
import stat
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import pytest
from app.ops.archive import inspect_package, safe_path


@pytest.mark.parametrize('path',['../outside','/absolute','C:/outside','a\\b','a//b','./a','a/../b','a/./b','a\x00b','a/','a\nb'])
def test_reject_unsafe_paths(path):
    with pytest.raises(ValueError): safe_path(path)


@pytest.mark.parametrize('kind',['symlink','duplicate','bomb','missing_manifest','duplicate_manifest_keys'])
def test_hostile_archives_are_rejected(kind):
    output=io.BytesIO()
    with ZipFile(output,'w',compression=ZIP_DEFLATED) as archive:
        archive.writestr('payload.txt',b'x'*100000 if kind=='bomb' else b'x')
        if kind=='duplicate': archive.writestr('payload.txt',b'y')
        if kind=='symlink':
            info=ZipInfo('link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
            archive.writestr(info,'/etc/passwd')
        if kind!='missing_manifest':
            archive.writestr('manifest.json',b'{"schema":"one","schema":"two"}' if kind=='duplicate_manifest_keys' else b'{}')
    with pytest.raises(ValueError): inspect_package(io.BytesIO(output.getvalue()))


def test_backup_offline_cli_never_executes_dump(tmp_path,monkeypatch,capsys):
    import hashlib
    from app.ops import archive as verifier
    payload=b'not executable SQL; offline verification only'
    manifest={'schema':verifier.BACKUP_SCHEMA,'hash_algorithm':'sha256','authenticity':'unsigned-integrity-only',
        'database_revision':'synthetic','table_fingerprints':{},'evidence':[],'export_cache':[],
        'files':[{'path':'database.dump','sha256':hashlib.sha256(payload).hexdigest(),'size':len(payload)}]}
    package=tmp_path/'synthetic.zip'
    with ZipFile(package,'w') as archive:
        archive.writestr('database.dump',payload);archive.writestr('manifest.json',verifier.canonical(manifest))
    monkeypatch.setattr('sys.argv',['archive',str(package),'--kind','backup'])
    assert verifier.main()==0
    assert '"valid": true' in capsys.readouterr().out
    monkeypatch.setattr('sys.argv',['archive',str(package)])
    assert verifier.main()==1
