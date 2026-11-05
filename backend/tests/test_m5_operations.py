import logging
import pytest
from pydantic import ValidationError
from app.core.config import Settings
from app.api.endpoints import health
from app.ops.preflight import diagnostics, local_directory


def test_liveness_has_no_dependency_requirement(client,monkeypatch):
    def forbidden(): raise AssertionError('Liveness must not touch dependencies')
    monkeypatch.setattr(health,'check_database',forbidden)
    response=client.get('/api/live')
    assert response.status_code==200 and response.json()['status']=='alive'
    assert 'db' not in response.json()


def test_request_ids_and_logs_do_not_expose_sensitive_inputs(client,caplog):
    with caplog.at_level(logging.INFO,logger='provena.operations'):
        response=client.get('/api/live?secret=private-evidence-text',headers={'Authorization':'Bearer secret-token','X-Request-ID':'synthetic_request'})
    assert response.headers['X-Request-ID']=='synthetic_request'
    assert 'private-evidence-text' not in caplog.text and 'secret-token' not in caplog.text
    assert 'duration_ms' in caplog.text
    invalid=client.get('/api/live',headers={'X-Request-ID':'unsafe id'})
    assert invalid.headers['X-Request-ID']!='unsafe id'


def test_readiness_is_safe_and_optional_llm_is_not_required(client,monkeypatch):
    monkeypatch.setattr(health,'readiness_checks',lambda:{'ready':False,'checks':{'database':'sensitive path must not escape'}})
    response=client.get('/api/ready')
    assert response.status_code==503 and 'sensitive' not in response.text
    monkeypatch.setattr(health,'readiness_checks',lambda:{'ready':True})
    assert client.get('/api/ready').status_code==200


@pytest.mark.parametrize('values',[
    {'secret_key':'x'*64},{'cors_origins':'http://external.example'},
    {'cors_origins':'https://example.test/path'},{'trusted_proxy_ips':'0.0.0.0/0'},
    {'database_url':'sqlite:///unsafe.db'},{'access_token_expire_minutes':0},
    {'export_storage_root':' '},{'export_storage_root':'./evidence-storage'},
])
def test_unsafe_production_configuration_is_rejected_without_secret_values(values):
    config={'app_env':'production','database_url':'postgresql://db/provena','secret_key':'Synthetic-production-signing-key-1234567890',
        'cors_origins':'https://example.test',**values}
    with pytest.raises(ValidationError) as exc: Settings(_env_file=None,**config)
    assert 'Synthetic-production-signing-key-1234567890' not in str(exc.value)


def test_offline_preflight_is_read_only(tmp_path):
    target=tmp_path/'not-created'
    config=Settings(_env_file=None,evidence_storage_root=str(target),export_storage_root=str(tmp_path/'exports'))
    result=diagnostics(config,storage=True)
    assert result['ready'] and not target.exists()
    assert local_directory(str(target))=='ok'
