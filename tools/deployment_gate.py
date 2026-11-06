"""Offline migration planning and pinned candidate verification, never deployment approval.

No network, database connection, shell execution, extraction or source-file modification.
Candidate verification uses a bounded private temporary copy of the supplied archive.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def migration_chain(directory=ROOT / 'backend/alembic/versions'):
    revisions = {}
    for path in sorted(directory.glob('*.py')):
        values = {}
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            names = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            for name in names:
                if isinstance(name, ast.Name) and name.id in {'revision', 'down_revision'}:
                    values[name.id] = ast.literal_eval(node.value)
        if set(values) != {'revision', 'down_revision'}:
            raise ValueError('Migration revision metadata is incomplete.')
        revision, previous = values.get('revision'), values.get('down_revision')
        if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{12}', revision) or revision in revisions:
            raise ValueError('Invalid or duplicate migration revision.')
        if previous is not None and (not isinstance(previous, str) or not re.fullmatch('[0-9a-f]{12}', previous)):
            raise ValueError('Nonlinear or invalid migration dependency.')
        revisions[revision] = previous
    heads = set(revisions) - set(revisions.values())
    if len(heads) != 1:
        raise ValueError('Expected a single migration head.')
    chain, current = [], heads.pop()
    while current is not None:
        if current in chain or current not in revisions:
            raise ValueError('Migration chain is cyclic or incomplete.')
        chain.append(current)
        current = revisions[current]
    if len(chain) != len(revisions):
        raise ValueError('Disconnected migration history.')
    return list(reversed(chain))


def migration_plan(source):
    chain = migration_chain()
    if source == 'unknown':
        return {'status': 'blocked_source_unknown', 'source': None, 'target': chain[-1],
                'required_migrations': None, 'recognized_revisions': chain,
                'backup_strategy': 'undetermined_until_source_revision_verified'}
    if source not in chain:
        raise ValueError('Source revision is not in the migration chain; do not stamp a revision.')
    pending = chain[chain.index(source) + 1:]
    return {'status': 'offline_path_known', 'source': source, 'target': chain[-1],
            'required_migrations': pending, 'workspace_backfill_approval_required': '9b6e5c4d3a21' in pending,
            'backup_strategy': 'matching_head_snapshot_tool' if not pending else 'reviewed_native_legacy_backup',
            'source_provenance': 'Operator supplied; this tool has not inspected a database.',
            'production_compatibility_verified': False}


def verify_candidate(package, expected_commit, expected_sha256):
    if not re.fullmatch('[0-9a-f]{40}', expected_commit or '') or not re.fullmatch('[0-9a-f]{64}', expected_sha256 or ''):
        raise ValueError('Supply an independently trusted full commit and package SHA-256.')
    spec = importlib.util.spec_from_file_location('provena_release', ROOT / 'tools/build_release.py')
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    with tempfile.TemporaryFile(mode='w+b') as snapshot:
        digest, size = hashlib.sha256(), 0
        with Path(package).open('rb') as source:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > release.LIMIT:
                    raise ValueError('Candidate archive exceeds the verification budget.')
                digest.update(chunk)
                snapshot.write(chunk)
        if digest.hexdigest() != expected_sha256:
            raise ValueError('Candidate differs from the independently supplied digest.')
        snapshot.seek(0)
        manifest = release.archive_tools.inspect_package(snapshot, expected_schema=release.SCHEMA, max_bytes=release.LIMIT)
        if manifest.get('commit') != expected_commit or manifest.get('publishable') is not False or manifest.get('publication') != 'validation-artifact-only':
            raise ValueError('Candidate commit or validation-only status does not match.')
        required = {'source/backend/app/main.py', 'source/backend/requirements.txt',
                    'source/backend/alembic/env.py', 'source/frontend/package-lock.json', 'web/index.html'}
        if not required.issubset({item['path'] for item in manifest['files']}):
            raise ValueError('Candidate lacks required source or frontend entry points.')
        snapshot.seek(0)
        with ZipFile(snapshot) as archive:
            for item in manifest['files']:
                if not item['path'].startswith(('source/', 'web/')):
                    raise ValueError('Unexpected candidate content root.')
                release.release_path(item['path'])
                tail = b''
                with archive.open(item['path']) as source:
                    while chunk := source.read(1024 * 1024):
                        tail = release.secret_fragment(chunk, tail)
        return {'status': 'verified_consistency', 'commit': expected_commit, 'sha256': digest.hexdigest(),
                'size': size, 'files': len(manifest['files']), 'publishable': False,
                'meaning': 'Unsigned integrity consistency against supplied pins, not authenticity or deployment approval.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', default='unknown')
    parser.add_argument('--candidate')
    parser.add_argument('--expect-commit')
    parser.add_argument('--expect-sha256')
    args = parser.parse_args()
    try:
        plan = migration_plan(args.source_revision)
        candidate = None
        if args.candidate:
            candidate = verify_candidate(args.candidate, args.expect_commit, args.expect_sha256)
        elif args.expect_commit or args.expect_sha256:
            raise ValueError('Candidate pins require a candidate archive.')
        print(json.dumps({'deployment_authorized': False, 'migration_plan': plan, 'candidate': candidate,
                          'gates_A_to_G': 'Require independently verified inventory, compatibility, backup, rehearsal, capacity, configuration and owner authorization.'}, indent=2))
        return 2 if plan['source'] is None else 0
    except (ValueError, OSError, SyntaxError, TypeError):
        print(json.dumps({'deployment_authorized': False, 'error': 'Offline validation failed. Check recognized revision, trusted archive pins, integrity, private-file exclusions and validation-only status.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
