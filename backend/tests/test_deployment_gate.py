"""No production access: offline candidate and migration decision boundaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile
import pytest

ROOT = Path(__file__).resolve().parents[2]


def gate():
    spec = importlib.util.spec_from_file_location('deployment_gate', ROOT / 'tools/deployment_gate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate(tmp_path, *, extra=None, altered=False, publication='validation-artifact-only'):
    files = {'source/backend/app/main.py': b'# synthetic', 'source/backend/requirements.txt': b'',
             'source/backend/alembic/env.py': b'# synthetic', 'source/frontend/package-lock.json': b'{}',
             'web/index.html': b'<html></html>'}
    files.update(extra or {})
    manifest = {'schema': 'provena-release-candidate/1', 'hash_algorithm': 'sha256',
                'authenticity': 'unsigned-integrity-only', 'commit': 'a' * 40, 'publishable': False,
                'publication': publication, 'files': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
                'size': len(data)} for name, data in files.items()]}
    path = tmp_path / 'synthetic-candidate.zip'
    with ZipFile(path, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, b'altered' if altered and name == 'web/index.html' else data)
        archive.writestr('manifest.json', json.dumps(manifest))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_unknown_source_never_invents_a_migration_suffix():
    plan = gate().migration_plan('unknown')
    assert plan['source'] is None and plan['required_migrations'] is None
    assert plan['status'] == 'blocked_source_unknown'


@pytest.mark.parametrize('source,count,backfill', [('000a8976b7f1', 7, True), ('9b6e5c4d3a21', 6, False), ('ee5b99eb5ce4', 0, False)])
def test_recognized_paths_are_explicitly_not_live_verification(source, count, backfill):
    plan = gate().migration_plan(source)
    assert len(plan['required_migrations']) == count
    assert plan['workspace_backfill_approval_required'] is backfill
    assert plan['production_compatibility_verified'] is False


def test_unknown_revision_refused():
    with pytest.raises(ValueError):
        gate().migration_plan('not-a-known-revision')


@pytest.mark.parametrize('previous', ['"bbbbbbbbbbbb"', '"aaaaaaaaaaaa"'])
def test_missing_dependency_or_cycle_refused(tmp_path, previous):
    (tmp_path / 'one.py').write_text('revision="aaaaaaaaaaaa"\ndown_revision=' + previous)
    with pytest.raises(ValueError):
        gate().migration_chain(tmp_path)


def test_candidate_snapshot_checks_pins_without_modifying_source(tmp_path):
    path, digest = candidate(tmp_path)
    result = gate().verify_candidate(path, 'a' * 40, digest)
    assert result['status'] == 'verified_consistency' and result['publishable'] is False
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('mode', ['wrong_digest', 'wrong_commit', 'altered', 'private_path', 'secret', 'publication', 'unexpected_root'])
def test_unsafe_or_unpinned_candidates_fail_closed(tmp_path, mode):
    extras = {'web/.env': b'not-a-secret'} if mode == 'private_path' else {'web/key.txt': b'AKIA' + b'A' * 16} if mode == 'secret' else {'other/file.txt': b'not allowed'} if mode == 'unexpected_root' else None
    path, digest = candidate(tmp_path, extra=extras, altered=mode == 'altered',
                             publication='public' if mode == 'publication' else 'validation-artifact-only')
    with pytest.raises(ValueError):
        gate().verify_candidate(path, 'b' * 40 if mode == 'wrong_commit' else 'a' * 40,
                                '0' * 64 if mode == 'wrong_digest' else digest)
