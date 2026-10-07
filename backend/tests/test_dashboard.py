"""Dashboard summary tests: scoped counts derived from real records."""

from tests.conftest import auth_headers, login


def make_investigation(client, token, title="Dashboard case"):
    response = client.post(
        "/api/investigations", headers=auth_headers(token), json={"title": title}
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, token, inv_id, title="Evidence item"):
    response = client.post(
        f"/api/investigations/{inv_id}/evidence",
        headers=auth_headers(token),
        data={"title": title},
        files={"file": ("item.log", b"log line\n", "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_empty_dashboard(client, investigator):
    token = login(client, "investigator")
    body = client.get("/api/dashboard/summary", headers=auth_headers(token)).json()
    assert body["investigations_total"] == 0
    assert body["by_status"] == {}
    assert body["evidence_total"] == 0
    assert body["integrity_issues"] == 0
    assert body["recent_activity"] == []
    assert body["pending_analysis"] == 0
    assert body["findings_pending_review"] == 0
    assert body["last_analysis"] is None


def test_dashboard_counts_and_scoping(client, investigator, analyst, admin, storage_dir):
    inv_token = login(client, "investigator")
    inv = make_investigation(client, inv_token)
    upload(client, inv_token, inv["id"])
    client.patch(
        f"/api/investigations/{inv['id']}", headers=auth_headers(inv_token),
        json={"status": "in_progress"},
    )

    member = client.get("/api/dashboard/summary", headers=auth_headers(inv_token)).json()
    assert member["investigations_total"] == 1
    assert member["by_status"] == {"in_progress": 1}
    assert member["evidence_total"] == 1
    assert member["integrity_issues"] == 0
    assert any(e["action"] == "EVIDENCE_REGISTERED" for e in member["recent_activity"])
    assert all(e["investigation_id"] == inv["id"] for e in member["recent_activity"])

    outsider_token = login(client, "analyst")
    outsider = client.get("/api/dashboard/summary", headers=auth_headers(outsider_token)).json()
    assert outsider["investigations_total"] == 0
    assert outsider["evidence_total"] == 0
    assert outsider["recent_activity"] == []

    admin_token = login(client, "admin")
    full = client.get("/api/dashboard/summary", headers=auth_headers(admin_token)).json()
    assert full["investigations_total"] == 1
    assert full["evidence_total"] == 1


def test_dashboard_counts_integrity_issues(client, investigator, db_session, storage_dir):
    from app.modules.evidence import storage as storage_module
    from app.modules.evidence.models import Evidence

    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = upload(client, token, inv["id"])
    row = db_session.get(Evidence, item["id"])
    assert row is not None
    with open(storage_module.resolve(row.storage_key), "ab") as handle:
        handle.write(b"tampered")
    client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    body = client.get("/api/dashboard/summary", headers=auth_headers(token)).json()
    assert body["integrity_issues"] == 1


def test_dashboard_requires_auth(client):
    assert client.get("/api/dashboard/summary").status_code == 401


def test_dashboard_attention_fields(client, investigator, storage_dir):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    item = upload(client, token, inv["id"])
    client.post(
        f"/api/investigations/{inv['id']}/evidence/{item['id']}/verify",
        headers=auth_headers(token),
    )
    before = client.get("/api/dashboard/summary", headers=auth_headers(token)).json()
    assert before["pending_analysis"] == 1
    assert before["findings_pending_review"] == 0
    assert before["last_analysis"] is None

    run = client.post(
        f"/api/investigations/{inv['id']}/analysis/runs",
        headers=auth_headers(token),
        json={"evidence_ids": [item["id"]]},
    )
    assert run.status_code == 201, run.text
    client.post(
        f"/api/investigations/{inv['id']}/analysis/findings/generate",
        headers=auth_headers(token),
    )
    after = client.get("/api/dashboard/summary", headers=auth_headers(token)).json()
    assert after["pending_analysis"] == 0
    assert after["findings_pending_review"] >= 0
    assert after["last_analysis"]["run_label"] == "RUN-0001"
    assert after["last_analysis"]["investigation_id"] == inv["id"]
