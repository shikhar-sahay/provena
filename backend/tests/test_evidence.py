"""Evidence tests: registration, hashing, verification, custody, audit, security."""

import hashlib
import io
import os

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.audit.models import AuditEvent
from app.modules.evidence import storage
from app.modules.evidence.models import Evidence
from tests.conftest import auth_headers, login

CONTENT = b"2026-01-14 03:12:44 auth: failed login for jdoe from 10.0.0.8\n"
DIGEST = hashlib.sha256(CONTENT).hexdigest()


def make_investigation(client, token, title="Exfiltration probe"):
    response = client.post(
        "/api/investigations", headers=auth_headers(token), json={"title": title}
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, token, inv_id, content=CONTENT, filename="auth.log", **fields):
    payload = {"title": "Firewall log", "description": "Perimeter export."}
    payload.update(fields)
    return client.post(
        f"/api/investigations/{inv_id}/evidence",
        headers=auth_headers(token),
        data=payload,
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )


@pytest.fixture()
def evidence(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    response = upload(client, token, inv["id"])
    assert response.status_code == 201, response.text
    return inv, response.json(), token


def test_upload_succeeds_with_baseline_digest(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    body = upload(client, token, inv["id"]).json()
    assert body["evidence_number"] == "E-001"
    assert body["sha256"] == DIGEST
    assert body["integrity_status"] == "not_verified"
    assert body["file_size"] == len(CONTENT)
    assert body["original_filename"] == "auth.log"
    assert "storage_key" not in body
    assert "storage_path" not in str(body).lower()
    # File actually stored under the storage root, not the original name.
    stored = list(storage_dir.rglob("*"))
    files = [p for p in stored if p.is_file() and not p.suffix == ".part"]
    assert len(files) == 1
    assert files[0].name != "auth.log"
    assert files[0].read_bytes() == CONTENT


def test_evidence_numbers_sequence_per_investigation(evidence, client):
    inv, first, token = evidence
    second = upload(client, token, inv["id"], filename="other.log").json()
    assert first["evidence_number"] == "E-001"
    assert second["evidence_number"] == "E-002"


def test_member_analyst_can_view_and_verify(evidence, client, analyst, db_session):
    inv, item, token = evidence
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    analyst_token = login(client, "analyst")
    # Analysts cannot register evidence (manage permission required).
    assert upload(client, analyst_token, inv["id"]).status_code == 403
    # But members can view evidence and run verification.
    detail = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}",
        headers=auth_headers(analyst_token),
    )
    assert detail.status_code == 200
    assert detail.json()["sha256"] == DIGEST
    verify = client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(analyst_token),
    )
    assert verify.status_code == 200
    assert verify.json()["result"] == "verified"


def test_custodian_cannot_register(evidence, client, custodian):
    inv, _, token = evidence
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": custodian.id},
    )
    custodian_token = login(client, "custodian")
    assert upload(client, custodian_token, inv["id"]).status_code == 403


def test_outsider_cannot_access_evidence(evidence, client, analyst):
    inv, item, _ = evidence
    token = login(client, "analyst")
    base = f"/api/investigations/{inv['id']}/evidence/{item['id']}"
    assert client.get(base, headers=auth_headers(token)).status_code == 404
    assert client.get(f"{base}/custody", headers=auth_headers(token)).status_code == 404
    assert client.get(f"{base}/timeline", headers=auth_headers(token)).status_code == 404


def test_empty_upload_rejected(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    response = upload(client, token, inv["id"], content=b"")
    assert response.status_code == 422
    # No orphan files left behind.
    assert [p for p in storage_dir.rglob("*") if p.is_file()] == []


def test_oversized_upload_rejected(client, investigator, storage_dir, monkeypatch):
    monkeypatch.setattr(settings, "evidence_max_upload_bytes", 10)
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    response = upload(client, token, inv["id"])
    assert response.status_code == 413
    assert [p for p in storage_dir.rglob("*") if p.is_file()] == []


def test_verify_unchanged_evidence(evidence, client):
    inv, item, token = evidence
    response = client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "verified"
    assert body["expected_sha256"] == DIGEST
    assert body["observed_sha256"] == DIGEST
    detail = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}",
        headers=auth_headers(token),
    ).json()
    assert detail["integrity_status"] == "verified"
    assert detail["last_verified_at"] is not None
    history = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verifications",
        headers=auth_headers(token),
    ).json()
    assert len(history) == 1


def test_tampered_file_produces_mismatch(evidence, client, db_session, storage_dir):
    inv, item, token = evidence
    row = db_session.get(Evidence, item["id"])
    with open(storage.resolve(row.storage_key), "ab") as handle:
        handle.write(b"attacker was here")
    baseline = row.sha256
    response = client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "mismatch"
    assert body["expected_sha256"] == baseline == DIGEST
    assert body["observed_sha256"] != DIGEST
    # Baseline digest never changes.
    db_session.refresh(row)
    assert row.sha256 == DIGEST
    assert row.integrity_status == "mismatch"


def test_missing_file_produces_unavailable(evidence, client, db_session):
    inv, item, token = evidence
    row = db_session.get(Evidence, item["id"])
    os.remove(storage.resolve(row.storage_key))
    response = client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["result"] == "unavailable"
    detail = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}",
        headers=auth_headers(token),
    ).json()
    assert detail["integrity_status"] == "unavailable"


def test_initial_custody_event_automatic(evidence, client):
    inv, item, token = evidence
    history = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/custody",
        headers=auth_headers(token),
    ).json()
    assert len(history) == 1
    assert history[0]["action"] == "registered"
    assert history[0]["to_user"]["username"] == "investigator"
    detail = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}",
        headers=auth_headers(token),
    ).json()
    assert detail["current_holder"]["username"] == "investigator"


def test_custody_transfer_flow(client, investigator, custodian, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    # Custodian must be an investigation member to receive custody.
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": custodian.id},
    )
    item = upload(client, token, inv["id"]).json()
    custodian_token = login(client, "custodian")
    # Member custodians can record transfers.
    response = client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/custody",
        headers=auth_headers(custodian_token),
        json={"action": "transferred", "to_user_id": investigator.id, "notes": "Handed back."},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["action"] == "transferred"
    assert body["to_user"]["username"] == "investigator"
    history = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/custody",
        headers=auth_headers(token),
    ).json()
    assert [e["action"] for e in history] == ["registered", "transferred"]


def test_transfer_to_non_member_rejected(client, investigator, custodian, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = upload(client, token, inv["id"]).json()
    response = client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/custody",
        headers=auth_headers(token),
        json={"action": "transferred", "to_user_id": custodian.id},
    )
    assert response.status_code == 400


def test_analyst_cannot_record_custody(client, investigator, analyst, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    item = upload(client, token, inv["id"]).json()
    analyst_token = login(client, "analyst")
    response = client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/custody",
        headers=auth_headers(analyst_token),
        json={"action": "transferred", "to_user_id": investigator.id},
    )
    assert response.status_code == 403


def test_custody_has_no_mutation_endpoints(evidence, client):
    inv, item, token = evidence
    base = f"/api/investigations/{inv['id']}/evidence/{item['id']}/custody"
    assert client.put(base, headers=auth_headers(token)).status_code == 405
    assert client.delete(base, headers=auth_headers(token)).status_code == 405


def test_evidence_audit_events(evidence, client, db_session):
    inv, item, token = evidence
    client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    actions = db_session.execute(select(AuditEvent.action)).scalars().all()
    assert "EVIDENCE_REGISTERED" in actions
    assert "EVIDENCE_VERIFIED" in actions
    for (metadata,) in db_session.execute(select(AuditEvent.event_metadata)).all():
        text = str(metadata)
        assert "password" not in text.lower()
        assert CONTENT.decode() not in text


def test_mismatch_audit_event(client, investigator, db_session, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = upload(client, token, inv["id"]).json()
    row = db_session.get(Evidence, item["id"])
    with open(storage.resolve(row.storage_key), "ab") as handle:
        handle.write(b"x")
    client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    actions = db_session.execute(select(AuditEvent.action)).scalars().all()
    assert "EVIDENCE_INTEGRITY_MISMATCH" in actions


def test_metadata_update_and_immutables(evidence, client, db_session):
    inv, item, token = evidence
    before = db_session.get(Evidence, item["id"])
    baseline_key = before.storage_key
    baseline_uploader = before.registered_by_id
    response = client.patch(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}",
        headers=auth_headers(token),
        json={"title": "Renamed log", "evidence_type": "log"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed log"
    row = db_session.get(Evidence, item["id"])
    assert row.sha256 == DIGEST
    assert row.storage_key == baseline_key
    assert row.registered_by_id == baseline_uploader


def test_path_traversal_filename_contained(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    body = upload(client, token, inv["id"], filename="../../evil.sh").json()
    assert body["original_filename"] == "evil.sh"
    stored = [p for p in storage_dir.rglob("*") if p.is_file()]
    assert len(stored) == 1
    assert storage_dir.resolve() in stored[0].resolve().parents


def test_archived_investigation_blocks_upload(client, investigator, admin, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(token),
        json={"status": "archived"},
    )
    assert upload(client, token, inv["id"]).status_code == 403


def test_evidence_timeline_assembles(evidence, client):
    inv, item, token = evidence
    client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    timeline = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/timeline",
        headers=auth_headers(token),
    ).json()
    kinds = [e["kind"] for e in timeline]
    assert kinds[0] == "evidence"
    assert "custody" in kinds
    assert "integrity" in kinds
    assert all(e["evidence_number"] == "E-001" for e in timeline if e["kind"] != "investigation")


def test_investigation_timeline_and_custody_views(client, investigator, custodian, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = upload(client, token, inv["id"]).json()
    client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    timeline = client.get(
        f"/api/investigations/{inv['id']}/timeline", headers=auth_headers(token)
    ).json()
    titles = [e["title"] for e in timeline]
    assert "Investigation created" in titles
    assert any("registered" in t for t in titles)
    assert any("integrity" in t for t in titles)
    custody = client.get(
        f"/api/investigations/{inv['id']}/custody", headers=auth_headers(token)
    ).json()
    assert len(custody) == 1
    assert custody[0]["evidence_number"] == "E-001"


def test_download_returns_bytes(evidence, client):
    inv, item, token = evidence
    response = client.get(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/download",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.content == CONTENT
    assert "auth.log" in response.headers.get("content-disposition", "")


def test_chunked_hash_matches_known_digest(tmp_path):
    target = tmp_path / "big.bin"
    target.write_bytes(b"a" * 200000 + b"b" * 200000)
    expected = hashlib.sha256(b"a" * 200000 + b"b" * 200000).hexdigest()
    assert storage.sha256_file(target) == expected
