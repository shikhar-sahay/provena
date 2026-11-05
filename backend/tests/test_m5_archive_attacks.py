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
        'created_at':'2026-11-06T00:00:00Z','application_version':'0.1.0-beta.0','consistency':'Synthetic offline fixture',
        'warnings':['Offline manifest validation does not execute or validate native SQL.'],
        'database_revision':'synthetic','table_fingerprints':{'alembic_version':{'count':1,'sha256':'a'*64}},'evidence':[],'export_cache':[],
        'files':[{'path':'database.dump','sha256':hashlib.sha256(payload).hexdigest(),'size':len(payload)}]}
    package=tmp_path/'synthetic.zip'
    with ZipFile(package,'w') as archive:
        archive.writestr('database.dump',payload);archive.writestr('manifest.json',verifier.canonical(manifest))
    monkeypatch.setattr('sys.argv',['archive',str(package),'--kind','backup'])
    assert verifier.main()==0
    assert '"valid": true' in capsys.readouterr().out
    monkeypatch.setattr('sys.argv',['archive',str(package)])
    assert verifier.main()==1


def export_manifest_package(change=None):
    import hashlib
    from app.ops.archive import canonical,EXPORT_SCHEMA
    data=b'{}\n'
    manifest={'schema':EXPORT_SCHEMA,'hash_algorithm':'sha256','authenticity':'unsigned-integrity-only',
        'created_at':'2026-11-06T00:00:00Z','actor':{'id':1,'username':'synthetic'},
        'investigation':{'id':1,'case_number':'SYNTHETIC-1','title':'Invented case'},'export_id':1,'mode':'metadata',
        'selection':{'mode':'metadata','event_set_ids':[],'report_ids':[],'evidence_ids':[]},
        'event_set_keys':[],'coverage':[],'processing_versions':[],'warnings':['Unsigned consistency only.'],
        'reports':[],'evidence':[],
        'files':[{'path':'metadata/investigation.jsonl','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
    if change: change(manifest)
    result=io.BytesIO()
    with ZipFile(result,'w') as archive:
        archive.writestr('metadata/investigation.jsonl',data);archive.writestr('manifest.json',canonical(manifest))
    result.seek(0)
    return result


@pytest.mark.parametrize('mutation',[
    lambda m:m.update(actor={}), lambda m:m.update(export_id=True),
    lambda m:m.update(created_at='not-a-time'), lambda m:m.update(created_at='2026-11-06T00:00:00'),
    lambda m:m['selection'].update(report_ids=[2]), lambda m:m['selection'].update(event_set_ids=[1,1]),
    lambda m:m.update(coverage=[{}]), lambda m:m.update(event_set_keys=['a'*64]),
    lambda m:m.pop('processing_versions'), lambda m:m.update(warnings='missing list'),
    lambda m:m['selection'].update(mode='originals'),
    lambda m:m.update(evidence=[{'id':True,'sha256':'a'*64,'size':3}]),
])
def test_manifest_provenance_and_selection_are_required(mutation):
    with pytest.raises(ValueError): inspect_package(export_manifest_package(mutation))


def test_metadata_inventory_can_reference_large_original_without_including_it():
    def metadata(manifest):
        manifest['evidence']=[{'id':1,'sha256':'a'*64,'size':2*1024**3,'included_path':None}]
    assert inspect_package(export_manifest_package(metadata))['evidence'][0]['size']==2*1024**3
