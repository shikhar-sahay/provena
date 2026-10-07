"""Reasoning tests: rules, Why data, validation RBAC, notes, reports."""

from sqlalchemy import func, select

from app.ai.rules import ArtifactFact, ExternalTransferSequenceRule, FactView
from app.modules.audit.models import AuditEvent
from app.modules.intelligence.models import Finding, InvestigationNote, Report
from tests.conftest import auth_headers, login, make_user
from tests.test_evidence import make_investigation, upload
from tests.test_intelligence import _register, _run, _verify
from app.modules.users.models import Role


def _demo_run(client, token, inv_id, storage_dir=None):
    from tests.test_intelligence import SAMPLE_DATA

    files = [
        ("authentication.log", "Auth"),
        ("usb_activity.log", "USB"),
        ("file_access.log", "Files"),
        ("network_activity.log", "Net"),
    ]
    ids = []
    for filename, title in files:
        content = (SAMPLE_DATA / filename).read_bytes()
        response = upload(client, token, inv_id, content=content, filename=filename, title=title)
        assert response.status_code == 201, response.text
        item = response.json()
        _verify(client, token, inv_id, item["id"])
        ids.append(item["id"])
    pdf = (SAMPLE_DATA / "employee-access-report.pdf").read_bytes()
    response = upload(client, token, inv_id, content=pdf, filename="report.pdf", title="PDF")
    assert response.status_code == 201, response.text
    item = response.json()
    _verify(client, token, inv_id, item["id"])
    ids.append(item["id"])
    return _run(client, token, inv_id, ids)


def _generate(client, token, inv_id, expected=200):
    response = client.post(
        f"/api/investigations/{inv_id}/analysis/findings/generate",
        headers=auth_headers(token),
    )
    assert response.status_code == expected, response.text
    return response.json()


def test_findings_generate_with_why_data(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token, title="Reasoning case")
    _demo_run(client, token, inv["id"])
    body = _generate(client, token, inv["id"])
    assert body["new_count"] >= 3
    rules = {finding["rule_id"] for finding in body["findings"]}
    assert {"identity-recurrence", "removable-media-session", "external-transfer-sequence"} <= rules

    by_rule = {finding["rule_id"]: finding for finding in body["findings"]}
    media = by_rule["removable-media-session"]
    assert media["status"] == "pending_review"
    assert 0 < media["confidence"] <= 100
    assert media["factors"]
    assert sum(f["weight"] for f in media["factors"]) >= media["confidence"]
    assert media["evidence_ids"] and media["artifact_ids"]
    assert media["recommendations"]
    assert "guilt" not in (media["title"] + media["summary"]).lower()
    assert "stole" not in (media["title"] + media["summary"]).lower()

    transfer = by_rule["external-transfer-sequence"]
    assert transfer["severity"] == "high"
    assert any("24h" in f["detail"] or "24" in f["detail"] for f in transfer["factors"])

    detail = client.get(
        f"/api/investigations/{inv['id']}/analysis/findings/{media['id']}",
        headers=auth_headers(token),
    ).json()
    assert detail["rule_version"] == "1"
    assert detail["reviewer_username"] is None


def test_regeneration_preserves_human_decisions(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token, title="Stable case")
    _demo_run(client, token, inv["id"])
    first = _generate(client, token, inv["id"])
    target = first["findings"][0]
    review = client.post(
        f"/api/investigations/{inv['id']}/analysis/findings/{target['id']}/review",
        headers=auth_headers(token),
        json={"status": "accepted", "note": "Checked against shift roster."},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "accepted"

    second = _generate(client, token, inv["id"])
    by_id = {finding["id"]: finding for finding in second["findings"]}
    assert by_id[target["id"]]["status"] == "accepted"
    assert by_id[target["id"]]["review_note"] == "Checked against shift roster."
    assert second["new_count"] == 0


def test_review_rbac(client, investigator, analyst, admin, storage_dir, db_session):
    token = login(client, "investigator")
    inv = make_investigation(client, token, title="Review case")
    _demo_run(client, token, inv["id"])
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    findings = _generate(client, token, inv["id"])["findings"]
    assert findings
    finding_id = findings[0]["id"]

    analyst_token = login(client, "analyst")
    assert (
        client.post(
            f"/api/investigations/{inv['id']}/analysis/findings/{finding_id}/review",
            headers=auth_headers(analyst_token),
            json={"status": "accepted"},
        ).status_code
        == 403
    )
    rejected = client.post(
        f"/api/investigations/{inv['id']}/analysis/findings/{finding_id}/review",
        headers=auth_headers(token),
        json={"status": "rejected", "note": "Duplicate of shift log."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["reviewer_username"] == "investigator"
    actions = db_session.execute(select(AuditEvent.action)).scalars().all()
    assert "AI_FINDING_GENERATED" in actions
    assert "AI_FINDING_REJECTED" in actions


def test_review_rejects_invalid_status(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token, title="Status case")
    _demo_run(client, token, inv["id"])
    findings = _generate(client, token, inv["id"])["findings"]
    response = client.post(
        f"/api/investigations/{inv['id']}/analysis/findings/{findings[0]['id']}/review",
        headers=auth_headers(token),
        json={"status": "pending_review"},
    )
    assert response.status_code == 422


def test_notes_lifecycle(client, investigator, analyst, admin, storage_dir, db_session):
    token = login(client, "investigator")
    inv = make_investigation(client, token, title="Notes case")
    _demo_run(client, token, inv["id"])
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    analyst_token = login(client, "analyst")

    created = client.post(
        f"/api/investigations/{inv['id']}/analysis/notes",
        headers=auth_headers(analyst_token),
        json={"body": "USB device was company-issued."},
    )
    assert created.status_code == 201, created.text
    assert created.json()["author_username"] == "analyst"

    updated = client.patch(
        f"/api/investigations/{inv['id']}/analysis/notes/{created.json()['id']}",
        headers=auth_headers(analyst_token),
        json={"body": "USB device was company-issued, per asset tag."},
    )
    assert updated.status_code == 200

    stranger = make_user(db_session, "stranger", Role.INVESTIGATOR)
    stranger_token = login(client, "stranger")
    assert (
        client.get(
            f"/api/investigations/{inv['id']}/analysis/notes",
            headers=auth_headers(stranger_token),
        ).status_code
        == 404
    )
    actions = db_session.execute(select(AuditEvent.action)).scalars().all()
    assert "INVESTIGATION_NOTE_ADDED" in actions
    assert "INVESTIGATION_NOTE_UPDATED" in actions


def test_reports_only_include_accepted(client, investigator, storage_dir, db_session):
    token = login(client, "investigator")
    inv = make_investigation(client, token, title="Report case")
    _demo_run(client, token, inv["id"])
    client.post(
        f"/api/investigations/{inv['id']}/analysis/notes",
        headers=auth_headers(token),
        json={"body": "Destination IP belongs to an approved backup provider."},
    )
    findings = _generate(client, token, inv["id"])["findings"]
    assert len(findings) >= 2
    client.post(
        f"/api/investigations/{inv['id']}/analysis/findings/{findings[0]['id']}/review",
        headers=auth_headers(token),
        json={"status": "accepted"},
    )
    client.post(
        f"/api/investigations/{inv['id']}/analysis/findings/{findings[1]['id']}/review",
        headers=auth_headers(token),
        json={"status": "rejected"},
    )

    report = client.post(
        f"/api/investigations/{inv['id']}/analysis/reports",
        headers=auth_headers(token),
    )
    assert report.status_code == 201, report.text
    body = report.json()
    assert body["report_label"] == "RPT-0001"
    assert len(body["content_sha256"]) == 64
    content = body["content"]
    assert len(content["accepted_findings"]) == 1
    assert content["accepted_findings"][0]["reviewer"] == "investigator"
    assert content["investigator_notes"][0]["body"].startswith("Destination IP")
    assert content["evidence_summary"]
    assert content["custody_summary"] or content["custody_summary"] == []
    assert content["timeline"]
    assert content["recommendations"]
    assert content["generator"] == "deterministic-report-v1"

    second = client.post(
        f"/api/investigations/{inv['id']}/analysis/reports",
        headers=auth_headers(token),
    ).json()
    assert second["report_label"] == "RPT-0002"
    actions = db_session.execute(select(AuditEvent.action)).scalars().all()
    assert "REPORT_GENERATED" in actions
    assert db_session.execute(select(func.count()).select_from(Report)).scalar_one() == 2
    assert db_session.execute(select(func.count()).select_from(Finding)).scalar_one() >= 2
    assert db_session.execute(select(func.count()).select_from(InvestigationNote)).scalar_one() == 1


def _fact(id, evidence_id, artifact_type, normalized, locator_key, context, span=None):
    return ArtifactFact(
        id=id,
        evidence_id=evidence_id,
        evidence_number=f"E-{evidence_id:03d}",
        artifact_type=artifact_type,
        normalized_value=normalized,
        locator_key=locator_key,
        context=context,
        span=span,
    )


def test_transfer_rule_ignores_source_address_before_keyword():
    facts = FactView(
        artifacts=[
            _fact(1, 10, "HOSTNAME", "ws-114", "line:1", "ws-114 (192.0.2.90) up", (0, 6)),
            _fact(2, 10, "IP_ADDRESS", "192.0.2.90", "line:1", "ws-114 (192.0.2.90) up", (8, 18)),
            _fact(
                3, 10, "IP_ADDRESS", "203.0.113.44", "line:2",
                "ws-114 upload 10 bytes to 203.0.113.44", (33, 45),
            ),
            _fact(
                4, 10, "TIMESTAMP", "2026-01-13T02:23:18+00:00", "line:2",
                "2026-01-13 02:23:18 ws-114 upload 10 bytes", None,
            ),
            _fact(5, 11, "FILE_NAME", "a.csv", "line:1", "copied a.csv", None),
            _fact(
                6, 11, "TIMESTAMP", "2026-01-13T02:20:00+00:00", "line:1",
                "2026-01-13 02:20:00 copied a.csv", None,
            ),
            _fact(7, 11, "USERNAME", "j.smith", "line:1", "user=j.smith copied a.csv", (5, 12)),
            _fact(8, 10, "USERNAME", "j.smith", "line:2", "user=j.smith upload x", (5, 12)),
        ],
        correlations={},
        all_verified=True,
    )
    findings = ExternalTransferSequenceRule().evaluate(facts)
    assert len(findings) == 1
    assert "203.0.113.44" in findings[0].title
    assert "192.0.2.90" not in findings[0].title


def test_global_findings_listing_and_bulk_review(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    _demo_run(client, token, inv["id"])
    generated = _generate(client, token, inv["id"])
    findings = generated["findings"]
    assert len(findings) >= 2

    # Test global findings endpoint returns investigation context
    res = client.get("/api/findings", headers=auth_headers(token))
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= len(findings)
    first_item = items[0]
    assert first_item["investigation_title"] == inv["title"]
    assert first_item["investigation_case_number"] == inv["case_number"]

    # Filter by status
    res_pending = client.get("/api/findings?status=pending_review", headers=auth_headers(token))
    assert res_pending.status_code == 200
    assert all(f["status"] == "pending_review" for f in res_pending.json())

    # Bulk review via global endpoint
    f_ids = [findings[0]["id"], findings[1]["id"]]
    bulk_res = client.post(
        "/api/findings/bulk-review",
        headers=auth_headers(token),
        json={"finding_ids": f_ids, "status": "accepted", "note": "Bulk validated via test"},
    )
    assert bulk_res.status_code == 200
    bulk_data = bulk_res.json()
    assert bulk_data["count"] == 2
    assert len(bulk_data["updated"]) == 2

    # Verify findings are now accepted
    res_accepted = client.get("/api/findings?status=accepted", headers=auth_headers(token))
    assert res_accepted.status_code == 200
    accepted_ids = {f["id"] for f in res_accepted.json()}
    assert set(f_ids).issubset(accepted_ids)

