"""Private legacy-row comparison helpers; no connection creation or command interface.

The caller supplies an authorized, consistent connection and keeps returned inventories
private. No row values are returned. Added columns are excluded after migration;
the Alembic revision is the only permitted change in the original field projection.
"""
import hashlib
import json
from sqlalchemy import MetaData, select

SCHEMA = 'provena-legacy-projection/1'


def _metadata(connection):
    metadata = MetaData()
    metadata.reflect(bind=connection)
    if not metadata.tables or len(metadata.tables) > 1000:
        raise ValueError('Legacy table inventory is empty or exceeds its budget.')
    return metadata


def _fingerprint(connection, table, columns, primary, remaining):
    if not columns or not primary or len(set(columns)) != len(columns):
        raise ValueError('Invalid legacy column inventory.')
    if any(name not in table.c for name in columns + primary):
        raise ValueError('A required legacy column is missing.')
    if primary != [column.name for column in table.primary_key.columns]:
        raise ValueError('Legacy primary key changed.')
    query = select(*(table.c[name] for name in columns)).order_by(*(table.c[name] for name in primary))
    query = query.execution_options(stream_results=True, yield_per=200)
    digest, count = hashlib.sha256(), 0
    for row in connection.execute(query).mappings():
        count += 1
        if count > remaining:
            raise ValueError('Legacy row validation budget exceeded.')
        digest.update(json.dumps(dict(row), sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False, default=str).encode('utf-8'))
        digest.update(b'\n')
    return {'count': count, 'sha256': digest.hexdigest()}


def capture(connection, max_rows=2_000_000):
    metadata, tables, remaining = _metadata(connection), {}, max_rows
    revision_table = metadata.tables['alembic_version']
    revisions = list(connection.scalars(select(revision_table.c.version_num)))
    if revisions != ['9b6e5c4d3a21']:
        raise ValueError('Expected the explicitly approved legacy source revision.')
    for name, table in sorted(metadata.tables.items()):
        columns = [column.name for column in table.columns]
        primary = [column.name for column in table.primary_key.columns]
        result = _fingerprint(connection, table, columns, primary, remaining)
        remaining -= result['count']
        tables[name] = {'columns': columns, 'primary_key': primary, **result}
    return {'schema': SCHEMA, 'source_revision': revisions[0], 'tables': tables}


def verify(connection, baseline, expected_revision, max_rows=2_000_000):
    if baseline.get('schema') != SCHEMA or baseline.get('source_revision') != '9b6e5c4d3a21':
        raise ValueError('Unsupported private legacy baseline.')
    if expected_revision not in {'9b6e5c4d3a21', 'ee5b99eb5ce4'}:
        raise ValueError('Unexpected verification revision.')
    tables = baseline.get('tables')
    if not isinstance(tables, dict) or not 1 < len(tables) <= 1000 or 'alembic_version' not in tables:
        raise ValueError('Private legacy inventory is incomplete.')
    metadata, remaining = _metadata(connection), max_rows
    revisions = list(connection.scalars(select(metadata.tables['alembic_version'].c.version_num)))
    if revisions != [expected_revision]:
        raise ValueError('Restored migration revision differs.')
    for name, original in tables.items():
        if name not in metadata.tables:
            raise ValueError('A legacy table is missing.')
        if name == 'alembic_version':
            continue
        result = _fingerprint(connection, metadata.tables[name], original['columns'], original['primary_key'], remaining)
        remaining -= result['count']
        if result != {key: original[key] for key in ('count', 'sha256')}:
            raise ValueError('Legacy data projection differs. Keep the restore target offline.')
    return {'legacy_projection_preserved': True, 'revision': expected_revision}
