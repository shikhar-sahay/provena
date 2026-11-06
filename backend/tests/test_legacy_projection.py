"""Synthetic private-field preservation, including added columns after migration."""
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text


def module():
    path = Path(__file__).resolve().parents[2] / 'tools/legacy_projection.py'
    spec = importlib.util.spec_from_file_location('legacy_projection', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture()
def fixture():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)'))
        connection.execute(text("INSERT INTO alembic_version VALUES ('9b6e5c4d3a21')"))
        connection.execute(text('CREATE TABLE history (id INTEGER PRIMARY KEY, value TEXT NOT NULL)'))
        connection.execute(text("INSERT INTO history VALUES (1, 'synthetic historical value')"))
        yield connection
    engine.dispose()


def test_added_fields_and_expected_revision_do_not_hide_legacy_data(fixture):
    helper = module()
    baseline = helper.capture(fixture)
    fixture.execute(text('ALTER TABLE history ADD COLUMN new_support TEXT'))
    fixture.execute(text("UPDATE alembic_version SET version_num='ee5b99eb5ce4'"))
    assert helper.verify(fixture, baseline, 'ee5b99eb5ce4')['legacy_projection_preserved']


@pytest.mark.parametrize('statement', ["UPDATE history SET value='changed'", 'DELETE FROM history', 'DROP TABLE history'])
def test_changed_or_missing_history_is_rejected(fixture, statement):
    helper = module()
    baseline = helper.capture(fixture)
    fixture.execute(text(statement))
    with pytest.raises(ValueError):
        helper.verify(fixture, baseline, '9b6e5c4d3a21')


def test_row_budget_and_wrong_revision_fail_closed(fixture):
    helper = module()
    with pytest.raises(ValueError, match='budget'):
        helper.capture(fixture, max_rows=1)
    baseline = helper.capture(fixture)
    with pytest.raises(ValueError, match='revision'):
        helper.verify(fixture, baseline, 'ee5b99eb5ce4')


def test_incomplete_baseline_cannot_claim_preservation(fixture):
    helper = module()
    baseline = helper.capture(fixture)
    baseline['tables'] = {}
    with pytest.raises(ValueError, match='incomplete'):
        helper.verify(fixture, baseline, '9b6e5c4d3a21')
