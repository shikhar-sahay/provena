"""M1 failure injection uses temporary local storage and an in-memory S3 fake."""
import hashlib
import io
from contextlib import contextmanager

import pytest
from sqlalchemy import select

from app.ai import parsers
from app.modules.evidence import service, storage
from app.modules.evidence.models import CustodyEvent, Evidence, EvidenceVerification
from app.modules.intelligence.models import Artifact, AnalysisRunEvidence
from tests.conftest import auth_headers, login
from tests.test_evidence import make_investigation, upload
from tests.test_storage import make_s3

DATA = b"user=original host=WS-17 from 192.0.2.10\n"


@pytest.fixture(params=["local", "s3"])
def backend(request, storage_dir, monkeypatch):
    if request.param == "local":
        store, fake = storage.LocalEvidenceStorage(storage_dir), None
    else:
        store, fake = make_s3()
    monkeypatch.setattr(storage, "get_storage", lambda: store)
    def replace(key, data):
        if fake is None:
            store.resolve(key).write_bytes(data)
        elif data is None:
            fake.objects.pop(key, None)
        else:
            fake.objects[key] = data
    def remove(key):
        if fake is None:
            store.resolve(key).unlink()
        else:
            fake.objects.pop(key, None)
    return store, replace, remove


def setup_item(client, investigator, db_session):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = upload(client, token, inv["id"], content=DATA).json()
    base = f"/api/investigations/{inv['id']}"
    headers = auth_headers(token)
    assert client.post(f"{base}/evidence/{item['id']}/verify", headers=headers).json()["result"] == "verified"
    return token, inv, item, base, headers, db_session.get(Evidence, item["id"])


@pytest.mark.parametrize("change", ["changed", "missing", "growing"])
def test_analysis_rechecks_exact_bytes_and_isolates_failed_item(backend, client, investigator, db_session, change):
    store, replace, remove = backend
    token, inv, item, base, headers, row = setup_item(client, investigator, db_session)
    other = upload(client, token, inv["id"], content=DATA, filename="other.log").json()
    client.post(f"{base}/evidence/{other['id']}/verify", headers=headers)
    if change == "missing":
        remove(row.storage_key)
    else:
        replace(row.storage_key, DATA.replace(b"original", b"attacker") if change == "changed" else DATA + b"extra")
    run = client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": [item["id"], other["id"]]})
    assert run.status_code == 201, run.text
    outcomes = {o["evidence_id"]: o for o in run.json()["evidence_outcomes"]}
    assert outcomes[item["id"]]["status"] == ("blocked_unavailable" if change == "missing" else "blocked_mismatch")
    assert outcomes[other["id"]]["status"] == "processed"
    assert outcomes[other["id"]]["input_sha256"] == hashlib.sha256(DATA).hexdigest()
    assert outcomes[other["id"]]["verification_id"]
    assert not db_session.execute(select(Artifact).where(Artifact.evidence_id == item["id"])).scalars().all()
    check = db_session.get(EvidenceVerification, outcomes[item["id"]]["verification_id"])
    assert check.purpose == "analysis" and check.performed_by_id == investigator.id


def test_source_changes_during_copy_fail_closed(backend, client, investigator, db_session, monkeypatch):
    store, _, _ = backend
    _, _, item, base, headers, row = setup_item(client, investigator, db_session)
    original_open = store.open
    @contextmanager
    def changing(key):
        if key == row.storage_key:
            yield io.BytesIO(DATA[:8] + b"changed during read")
        else:
            with original_open(key) as handle:
                yield handle
    monkeypatch.setattr(store, "open", changing)
    result = client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": [item["id"]]}).json()
    assert result["evidence_outcomes"][0]["status"] == "blocked_mismatch"


def test_parser_uses_private_copy_not_reopened_source(backend, client, investigator, db_session, monkeypatch):
    _, replace, _ = backend
    _, _, item, base, headers, row = setup_item(client, investigator, db_session)
    original = parsers.PARSERS["log"]
    def parse(copied):
        replace(row.storage_key, b"user=attacker host=WS-99\n")
        assert copied == DATA
        return original(copied)
    monkeypatch.setitem(parsers.PARSERS, "log", parse)
    response = client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": [item["id"]]})
    assert response.json()["evidence_outcomes"][0]["status"] == "processed"
    artifacts = db_session.execute(select(Artifact)).scalars().all()
    assert any(a.normalized_value == "original" for a in artifacts)
    assert all(a.input_sha256 == hashlib.sha256(DATA).hexdigest() for a in artifacts)


def test_failed_promotion_is_visible_blocked_and_recoverable(backend, client, investigator, db_session, monkeypatch):
    store, _, _ = backend
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    promote = store.finalize
    monkeypatch.setattr(store, "finalize", lambda _: (_ for _ in ()).throw(OSError("private/storage/internal")))
    failed = upload(client, token, inv["id"], content=DATA)
    assert failed.status_code == 503 and "private/storage" not in failed.text
    row = db_session.execute(select(Evidence)).scalar_one()
    assert row.registration_status == "failed"
    base = f"/api/investigations/{inv['id']}"
    headers = auth_headers(token)
    assert client.post(f"{base}/evidence/{row.id}/verify", headers=headers).status_code == 409
    assert client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": [row.id]}).json()["artifact_count"] == 0
    monkeypatch.setattr(store, "finalize", promote)
    recovered = client.post(f"{base}/evidence/{row.id}/recover", headers=headers)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["registration_status"] == "ready"
    assert recovered.json()["integrity_status"] == "not_verified"
    retry = upload(client, token, inv["id"], content=DATA)
    assert retry.json()["id"] == row.id
    actions = db_session.execute(select(CustodyEvent.action)).scalars().all()
    assert actions.count("registered") == 1 and "recovered" in actions


def test_retry_can_supply_original_bytes_after_failed_storage(backend, client, investigator, db_session, monkeypatch):
    store, _, _ = backend
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    promote = store.finalize
    monkeypatch.setattr(store, "finalize", lambda _: (_ for _ in ()).throw(OSError()))
    assert upload(client, token, inv["id"], content=DATA).status_code == 503
    row = db_session.execute(select(Evidence)).scalar_one()
    monkeypatch.setattr(store, "finalize", promote)
    retry = upload(client, token, inv["id"], content=DATA)
    assert retry.status_code == 201 and retry.json()["id"] == row.id
    assert row.registration_status == "ready"


def test_lost_commit_acknowledgement_retains_recoverable_input(backend, client, investigator, db_session, monkeypatch):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    commit = db_session.commit
    calls = 0
    def lost_ack():
        nonlocal calls
        calls += 1
        commit()
        if calls == 1:
            raise OSError("lost commit acknowledgement")
    monkeypatch.setattr(db_session, "commit", lost_ack)
    assert upload(client, token, inv["id"], content=DATA).status_code == 503
    row = db_session.execute(select(Evidence)).scalar_one()
    assert row.registration_status == "pending"
    response = client.post(f"/api/investigations/{inv['id']}/evidence/{row.id}/recover", headers=auth_headers(token))
    assert response.status_code == 200 and response.json()["registration_status"] == "ready"


def test_verification_does_not_transfer_custody(backend, client, investigator, analyst, db_session):
    _, _, item, base, headers, row = setup_item(client, investigator, db_session)
    assert service.current_holder(db_session, row).id == investigator.id
    assert client.post(f"{base}/evidence/{item['id']}/custody", headers=headers,
                       json={"action": "verified"}).status_code == 422
    assert client.patch(f"{base}/evidence/{item['id']}/custody", headers=headers, json={"notes": "edit"}).status_code == 405


def test_degraded_support_is_excluded_without_rewriting_old_report(backend, client, investigator, db_session):
    _, replace, _ = backend
    token, inv, item, base, headers, row = setup_item(client, investigator, db_session)
    ids = [item["id"]]
    for filename in ["b.log", "c.log"]:
        other = upload(client, token, inv["id"], content=DATA, filename=filename).json()
        client.post(f"{base}/evidence/{other['id']}/verify", headers=headers)
        ids.append(other["id"])
    client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": ids})
    finding = client.post(f"{base}/analysis/findings/generate", headers=headers).json()["findings"][0]
    client.post(f"{base}/analysis/findings/{finding['id']}/review", headers=headers, json={"status": "accepted"})
    before = client.post(f"{base}/analysis/reports", headers=headers).json()
    assert before["content"]["accepted_findings"][0]["source_artifacts"]
    replace(row.storage_key, DATA.replace(b"original", b"attacker"))
    after = client.post(f"{base}/analysis/reports", headers=headers).json()
    assert after["content"]["accepted_findings"] == []
    assert finding["id"] in after["content"]["excluded_stale_finding_ids"]
    assert client.get(f"{base}/analysis/reports/{before['id']}", headers=headers).json()["content_sha256"] == before["content_sha256"]


def test_database_failure_before_commit_leaves_no_completed_item(backend, client, investigator, db_session, monkeypatch):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    commit = db_session.commit
    def fail():
        raise OSError("internal database address")
    monkeypatch.setattr(db_session, "commit", fail)
    failed = upload(client, token, inv["id"], content=DATA)
    assert failed.status_code == 503 and "internal database" not in failed.text
    assert db_session.execute(select(Evidence)).scalars().all() == []
    monkeypatch.setattr(db_session, "commit", commit)
    assert upload(client, token, inv["id"], content=DATA).status_code == 201


def test_interrupted_upload_cleans_partial_staging(backend):
    store, _, _ = backend
    class Interrupted:
        def read(self, _):
            raise OSError("synthetic interruption")
    with pytest.raises(OSError):
        store.stage(Interrupted(), 1, 100)
    if isinstance(store, storage.LocalEvidenceStorage):
        assert not list(store.root.rglob("*.part"))
    else:
        assert not store.client.uploads


def test_explicit_retry_key_rejects_different_bytes(backend, client, investigator, db_session):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    headers = {**auth_headers(token), "Idempotency-Key": "synthetic-request-1"}
    def send(data):
        return client.post(f"/api/investigations/{inv['id']}/evidence", headers=headers,
                           data={"title": "Retry"}, files={"file": ("a.log", data, "text/plain")})
    first = send(DATA)
    assert first.status_code == 201
    assert send(DATA).json()["id"] == first.json()["id"]
    assert send(b"different bytes").status_code == 409
    assert len(db_session.execute(select(Evidence)).scalars().all()) == 1


def test_run_failure_keeps_observed_integrity_failures(backend, client, investigator, db_session, monkeypatch):
    _, replace, _ = backend
    token, inv, item, base, headers, row = setup_item(client, investigator, db_session)
    other = upload(client, token, inv["id"], content=DATA, filename="second.log").json()
    client.post(f"{base}/evidence/{other['id']}/verify", headers=headers)
    replace(row.storage_key, DATA.replace(b"original", b"attacker"))
    monkeypatch.setitem(parsers.PARSERS, "log", lambda _: (_ for _ in ()).throw(RuntimeError("private/parser/internal")))
    response = client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": [row.id, other["id"]]})
    assert response.status_code == 201 and response.json()["status"] == "failed"
    assert "private/parser" not in response.text
    db_session.refresh(row)
    assert row.integrity_status == "mismatch"
    assert db_session.execute(select(EvidenceVerification).where(
        EvidenceVerification.evidence_id == row.id, EvidenceVerification.purpose == "analysis_failure",
        EvidenceVerification.result == "mismatch")).scalars().all()


def test_identical_rerun_preserves_finding_and_correlation_references(backend, client, investigator, db_session):
    token, inv, item, base, headers, _ = setup_item(client, investigator, db_session)
    ids = [item["id"]]
    for filename in ["b.log", "c.log"]:
        other = upload(client, token, inv["id"], content=DATA, filename=filename).json()
        client.post(f"{base}/evidence/{other['id']}/verify", headers=headers)
        ids.append(other["id"])
    def analyse():
        assert client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": ids}).status_code == 201
        return client.post(f"{base}/analysis/findings/generate", headers=headers).json()
    first = analyse()
    correlations = client.get(f"{base}/analysis/correlations", headers=headers).json()
    second = analyse()
    assert second["new_count"] == 0
    assert [f["id"] for f in first["findings"]] == [f["id"] for f in second["findings"]]
    assert [c["id"] for c in correlations] == [c["id"] for c in client.get(f"{base}/analysis/correlations", headers=headers).json()]
    # Legacy provenance is not fabricated by verification or finding generation.
    for artifact in db_session.execute(select(Artifact)).scalars():
        artifact.input_sha256 = None
    db_session.commit()
    historical = client.get(f"{base}/analysis/findings", headers=headers).json()
    assert historical and all(not f["support_current"] for f in historical)
    from app.modules.intelligence.reasoning import build_facts
    from app.modules.investigations.service import get_investigation
    assert build_facts(db_session, get_investigation(db_session, inv["id"])).artifacts == []
    # Reanalysis of the original baseline restores the existing stable references.
    restored = analyse()
    assert restored["new_count"] == 0
    assert all(f["support_current"] for f in restored["findings"])



def test_known_flush_failure_cleans_staging(backend, client, investigator, db_session, monkeypatch):
    store, _, _ = backend
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    flush = db_session.flush
    def fail(objects=None):
        if any(isinstance(obj, Evidence) for obj in db_session.new):
            raise OSError("synthetic flush failure")
        return flush(objects)
    monkeypatch.setattr(db_session, "flush", fail)
    assert upload(client, token, inv["id"], content=DATA).status_code == 503
    assert db_session.execute(select(Evidence)).scalars().all() == []
    if isinstance(store, storage.LocalEvidenceStorage):
        assert not [p for p in store.root.rglob("*") if p.is_file()]
    else:
        assert not store.client.objects
