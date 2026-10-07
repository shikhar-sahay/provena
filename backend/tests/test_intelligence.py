"""Intelligence tests: integrity gate, extraction, correlation, RBAC, audit."""

import importlib.util
import io
from pathlib import Path

from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.evidence import storage
from app.modules.evidence.models import Evidence
from app.modules.intelligence.models import Artifact, Correlation
from tests.conftest import auth_headers, login, make_user
from tests.test_evidence import make_investigation, upload

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "sample-data"


def _pdf_builder():
    spec = importlib.util.spec_from_file_location(
        "make_access_report", SAMPLE_DATA / "make_access_report.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_text_pdf


def _register(client, token, inv_id, content, filename, title="Item"):
    response = upload(client, token, inv_id, content=content, filename=filename, title=title)
    assert response.status_code == 201, response.text
    return response.json()


def _verify(client, token, inv_id, evidence_id):
    response = client.post(
        f"/api/investigations/{inv_id}/evidence/{evidence_id}/verify",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _run(client, token, inv_id, evidence_ids, expected=201):
    response = client.post(
        f"/api/investigations/{inv_id}/analysis/runs",
        headers=auth_headers(token),
        json={"evidence_ids": evidence_ids},
    )
    assert response.status_code == expected, response.text
    return response.json()


def test_verified_evidence_processes_with_provenance(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = _register(
        client, token, inv["id"],
        b"2026-01-13 02:15:01 login user=j.smith host=WS-17 from 192.0.2.90\n",
        "auth.log",
    )
    _verify(client, token, inv["id"], item["id"])
    run = _run(client, token, inv["id"], [item["id"]])
    assert run["status"] == "completed"
    assert run["run_label"] == "RUN-0001"
    assert run["artifact_count"] > 0
    assert run["evidence_outcomes"][0]["status"] == "processed"

    artifacts = client.get(
        f"/api/investigations/{inv['id']}/analysis/artifacts",
        headers=auth_headers(token),
    ).json()
    by_type = {(a["artifact_type"], a["normalized_value"]) for a in artifacts["items"]}
    assert ("USERNAME", "j.smith") in by_type
    assert ("HOSTNAME", "ws-17") in by_type
    assert ("IP_ADDRESS", "192.0.2.90") in by_type
    detail = client.get(
        f"/api/investigations/{inv['id']}/analysis/artifacts/{artifacts['items'][0]['id']}",
        headers=auth_headers(token),
    ).json()
    assert detail["locator"] == {"kind": "line", "line": 1}
    assert "storage_key" not in str(detail)
    assert len(detail["context"]) <= 280


def test_integrity_gate_blocks_unverified_mismatch_unavailable(
    client, investigator, storage_dir, db_session
):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    fresh = _register(client, token, inv["id"], b"user=j.smith\n", "a.log", title="Fresh")
    tampered = _register(client, token, inv["id"], b"user=j.smith\n", "b.log", title="Tampered")
    gone = _register(client, token, inv["id"], b"user=j.smith\n", "c.log", title="Gone")
    _verify(client, token, inv["id"], tampered["id"])
    _verify(client, token, inv["id"], gone["id"])

    row = db_session.get(Evidence, tampered["id"])
    with open(storage.resolve(row.storage_key), "ab") as handle:
        handle.write(b"tamper")
    row = db_session.get(Evidence, gone["id"])
    storage.resolve(row.storage_key).unlink()
    _verify(client, token, inv["id"], tampered["id"])
    _verify(client, token, inv["id"], gone["id"])

    run = _run(client, token, inv["id"], [fresh["id"], tampered["id"], gone["id"]])
    assert run["status"] == "completed"
    assert run["artifact_count"] == 0
    outcomes = {o["evidence_id"]: o["status"] for o in run["evidence_outcomes"]}
    assert outcomes[fresh["id"]] == "blocked_not_verified"
    assert outcomes[tampered["id"]] == "blocked_mismatch"
    assert outcomes[gone["id"]] == "blocked_unavailable"


def test_unsupported_format_and_malformed_json(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    binary = _register(client, token, inv["id"], b"\x00\x01\x02", "tool.exe", title="Binary")
    broken = _register(client, token, inv["id"], b"{not json", "broken.json", title="Broken")
    for item in (binary, broken):
        _verify(client, token, inv["id"], item["id"])
    run = _run(client, token, inv["id"], [binary["id"], broken["id"]])
    outcomes = {o["evidence_id"]: o for o in run["evidence_outcomes"]}
    assert outcomes[binary["id"]]["status"] == "unsupported"
    assert "not supported" in outcomes[binary["id"]]["error"]
    assert outcomes[broken["id"]]["status"] == "failed"
    assert "parsed" in outcomes[broken["id"]]["error"]


def test_csv_json_txt_pdf_extraction(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    csv_item = _register(
        client, token, inv["id"], b"username,host\nj.smith,WS-17\n", "users.csv", title="CSV"
    )
    json_item = _register(
        client, token, inv["id"], b'{"events": [{"username": "j.smith"}]}', "e.json", title="JSON"
    )
    txt_item = _register(
        client, token, inv["id"], b"Contact a.lindqvist@example.com re WS-17\n", "n.txt", title="TXT"
    )
    pdf_bytes = (SAMPLE_DATA / "employee-access-report.pdf").read_bytes()
    pdf_item = _register(client, token, inv["id"], pdf_bytes, "report.pdf", title="PDF")
    for item in (csv_item, json_item, txt_item, pdf_item):
        _verify(client, token, inv["id"], item["id"])
    run = _run(
        client, token, inv["id"],
        [csv_item["id"], json_item["id"], txt_item["id"], pdf_item["id"]],
    )
    assert run["status"] == "completed"
    assert run["artifact_count"] > 0

    artifacts = client.get(
        f"/api/investigations/{inv['id']}/analysis/artifacts",
        headers=auth_headers(token),
        params={"limit": 500},
    ).json()["items"]
    by_evidence: dict[int, set] = {}
    for artifact in artifacts:
        by_evidence.setdefault(artifact["evidence_id"], set()).add(
            (artifact["artifact_type"], artifact["locator"].get("kind"))
        )
    assert ("USERNAME", "csv") in by_evidence[csv_item["id"]]
    assert ("USERNAME", "json") in by_evidence[json_item["id"]]
    assert ("EMAIL_ADDRESS", "line") in by_evidence[txt_item["id"]]
    pdf_kinds = {kind for _, kind in by_evidence[pdf_item["id"]]}
    assert "pdf" in pdf_kinds
    pdf_users = [
        a for a in artifacts
        if a["evidence_id"] == pdf_item["id"] and a["artifact_type"] == "USERNAME"
    ]
    assert pdf_users and all(a["locator"].get("page") in (1, 2) for a in pdf_users)


def test_scanned_pdf_reports_no_text(client, investigator, storage_dir):
    build = _pdf_builder()
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = _register(client, token, inv["id"], build([["   "]]), "scan.pdf", title="Scan")
    _verify(client, token, inv["id"], item["id"])
    run = _run(client, token, inv["id"], [item["id"]])
    outcome = run["evidence_outcomes"][0]
    assert outcome["status"] == "failed"
    assert "OCR" in (outcome["error"] or "")


def test_rerun_does_not_duplicate_artifacts(client, investigator, storage_dir, db_session):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = _register(client, token, inv["id"], b"user=j.smith host=WS-17\n", "a.log")
    _verify(client, token, inv["id"], item["id"])
    first = _run(client, token, inv["id"], [item["id"]])
    before = db_session.execute(select(func.count()).select_from(Artifact)).scalar_one()
    second = _run(client, token, inv["id"], [item["id"]])
    after = db_session.execute(select(func.count()).select_from(Artifact)).scalar_one()
    assert before == after > 0
    assert second["run_label"] == "RUN-0002"
    assert second["artifact_count"] == first["artifact_count"]


def test_shared_value_correlation_and_isolation(
    client, investigator, analyst, admin, storage_dir, db_session
):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    first = _register(client, token, inv["id"], b"user=j.smith host=WS-17\n", "a.log", title="A")
    second = _register(client, token, inv["id"], b"user=J.SMITH\n", "b.log", title="B")
    other = make_investigation(client, token, title="Other case")
    third = _register(client, token, other["id"], b"user=j.smith\n", "c.log", title="C")
    for item in (first, second, third):
        _verify(client, token, item["investigation_id"], item["id"])
    _run(client, token, inv["id"], [first["id"], second["id"]])
    _run(client, token, other["id"], [third["id"]])

    correlations = client.get(
        f"/api/investigations/{inv['id']}/analysis/correlations",
        headers=auth_headers(token),
    ).json()
    users = [c for c in correlations if c["normalized_value"] == "j.smith"]
    assert len(users) == 1
    assert users[0]["artifact_type"] == "USERNAME"
    assert users[0]["evidence_count"] == 2
    detail = client.get(
        f"/api/investigations/{inv['id']}/analysis/correlations/{users[0]['id']}",
        headers=auth_headers(token),
    ).json()
    assert {a["evidence_number"] for a in detail["artifacts"]} == {"E-001", "E-002"}
    assert all("locator" in a and "context" in a for a in detail["artifacts"])

    other_correlations = client.get(
        f"/api/investigations/{other['id']}/analysis/correlations",
        headers=auth_headers(token),
    ).json()
    assert other_correlations == []
    count = db_session.execute(select(func.count()).select_from(Correlation)).scalar_one()
    assert count == len(correlations)


def test_analysis_rbac(client, investigator, analyst, custodian, admin, storage_dir, db_session):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = _register(client, token, inv["id"], b"user=j.smith\n", "a.log")
    _verify(client, token, inv["id"], item["id"])
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": custodian.id},
    )

    analyst_token = login(client, "analyst")
    run = _run(client, analyst_token, inv["id"], [item["id"]])
    assert run["status"] == "completed"

    custodian_token = login(client, "custodian")
    response = client.post(
        f"/api/investigations/{inv['id']}/analysis/runs",
        headers=auth_headers(custodian_token),
        json={"evidence_ids": [item["id"]]},
    )
    assert response.status_code == 403
    assert (
        client.get(
            f"/api/investigations/{inv['id']}/analysis/artifacts",
            headers=auth_headers(custodian_token),
        ).status_code
        == 200
    )

    from app.modules.users.models import Role

    make_user(db_session, "stranger", Role.INVESTIGATOR)
    stranger_token = login(client, "stranger")
    assert (
        client.post(
            f"/api/investigations/{inv['id']}/analysis/runs",
            headers=auth_headers(stranger_token),
            json={"evidence_ids": [item["id"]]},
        ).status_code
        == 404
    )

    admin_token = login(client, "admin")
    admin_run = _run(client, admin_token, inv["id"], [item["id"]])
    assert admin_run["status"] == "completed"


def test_analysis_audit_events(client, investigator, storage_dir, db_session):
    from app.modules.audit.models import AuditEvent

    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = _register(client, token, inv["id"], b"user=j.smith\n", "a.log")
    _verify(client, token, inv["id"], item["id"])
    _run(client, token, inv["id"], [item["id"]])
    actions = db_session.execute(select(AuditEvent.action)).scalars().all()
    assert "AI_ANALYSIS_STARTED" in actions
    assert "AI_ANALYSIS_COMPLETED" in actions
    for (metadata,) in db_session.execute(select(AuditEvent.event_metadata)).all():
        text = str(metadata)
        assert "j.smith" not in text
