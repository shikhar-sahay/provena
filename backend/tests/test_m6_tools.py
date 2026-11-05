"""Offline release checks and refusal of unsafe browser test targets."""
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('url',[
    'postgresql+psycopg2://user@production.example/provena_ci',
    'postgresql+psycopg2://user@127.0.0.1/provena',
    'postgresql+psycopg2://user@127.0.0.1/provena_ci?options=unsafe',
    'sqlite:///provena_ci',
])
def test_browser_runner_refuses_non_disposable_targets(url):
    with pytest.raises(ValueError):module('run_e2e').control_url(url)


@pytest.mark.parametrize('value',[
    b'AKIA'+b'A'*16,b'ghp_'+b'A'*36,b'-----BEGIN '+b'PRIVATE KEY-----',
])
def test_release_secret_detection_including_chunk_boundaries(value):
    checker=module('build_release')
    tail=checker.secret_fragment(value[:8])
    with pytest.raises(ValueError):checker.secret_fragment(value[8:],tail)


@pytest.mark.parametrize('path',['web/.env','web/private.dump','web/test-results/trace.zip','source/backend/.venv/code.py','source/migration-backup/dump.sql','web/signing.key'])
def test_release_private_path_guard_applies_to_web_and_source(path):
    with pytest.raises(ValueError):module('build_release').release_path(path)


def test_documentation_checker_detects_missing_links_without_network():
    checker=module('check_docs')
    assert checker.inspect('[Missing](missing.md)','docs/example.md',{'README.md'})
    assert checker.inspect('```mermaid\nunknownGraph\n```','docs/example.md',set())
    assert checker.inspect('```sh\nnever closed','docs/example.md',set())
    assert not checker.inspect('[Root](../README.md)\n[External](https://invalid.example)','docs/example.md',{'README.md'})
