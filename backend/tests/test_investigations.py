"""Investigation tests: lifecycle, visibility, authorization, membership, state rules."""

import re

from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from tests.conftest import auth_headers, login


def create(client, token, **kwargs):
    payload = {"title": "Suspected data exfiltration", "description": "Insider threat probe."}
    payload.update(kwargs)
    response = client.post("/api/investigations", headers=auth_headers(token), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_returns_case_number(client, investigator):
    token = login(client, "investigator")
    body = create(client, token)
    assert re.fullmatch(r"PRV-\d{4}-\d{4}", body["case_number"])
    assert body["status"] == "open"
    assert body["created_by"]["username"] == "investigator"
    assert body["lead_investigator"]["username"] == "investigator"
    members = {m["user"]["username"] for m in body["members"]}
    assert "investigator" in members


def test_case_numbers_are_unique_and_sequential(client, investigator):
    token = login(client, "investigator")
    first = create(client, token, title="First")
    second = create(client, token, title="Second")
    assert first["case_number"] != second["case_number"]
    assert int(second["case_number"].rsplit("-", 1)[1]) == int(first["case_number"].rsplit("-", 1)[1]) + 1


def test_create_requires_title(client, investigator):
    token = login(client, "investigator")
    response = client.post(
        "/api/investigations", headers=auth_headers(token), json={"title": "  "}
    )
    assert response.status_code == 422


def test_analyst_cannot_create_investigation(client, analyst):
    token = login(client, "analyst")
    response = client.post(
        "/api/investigations", headers=auth_headers(token), json={"title": "Nope"}
    )
    assert response.status_code == 403


def test_custodian_cannot_create_investigation(client, custodian):
    token = login(client, "custodian")
    response = client.post(
        "/api/investigations", headers=auth_headers(token), json={"title": "Nope"}
    )
    assert response.status_code == 403


def test_list_visibility_member_vs_admin(client, investigator, analyst, admin):
    inv_token = login(client, "investigator")
    inv = create(client, inv_token)
    # Analyst is not a member: sees nothing, cannot open it.
    analyst_token = login(client, "analyst")
    assert client.get("/api/investigations", headers=auth_headers(analyst_token)).json() == []
    assert (
        client.get(f"/api/investigations/{inv['id']}", headers=auth_headers(analyst_token)).status_code
        == 404
    )
    # Admin sees everything.
    admin_token = login(client, "admin")
    listed = client.get("/api/investigations", headers=auth_headers(admin_token)).json()
    assert {i["id"] for i in listed} == {inv["id"]}


def test_update_by_lead_and_forbidden_for_member(client, investigator, analyst, db_session):
    token = login(client, "investigator")
    inv = create(client, token)
    # Add analyst as plain member.
    response = client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    assert response.status_code == 200
    analyst_token = login(client, "analyst")
    # Member can view but not edit core metadata.
    assert (
        client.get(f"/api/investigations/{inv['id']}", headers=auth_headers(analyst_token)).status_code
        == 200
    )
    response = client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(analyst_token),
        json={"title": "Hijacked"},
    )
    assert response.status_code == 403
    # Lead can edit.
    response = client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(token),
        json={"title": "Updated title", "priority": "high"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"
    assert response.json()["priority"] == "high"


def test_invalid_status_rejected(client, investigator):
    token = login(client, "investigator")
    inv = create(client, token)
    response = client.patch(
        f"/api/investigations/{inv['id']}", headers=auth_headers(token), json={"status": "bogus"}
    )
    assert response.status_code == 422


def test_close_sets_closed_at_and_reopen_clears(client, investigator):
    token = login(client, "investigator")
    inv = create(client, token)
    closed = client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(token),
        json={"status": "closed"},
    ).json()
    assert closed["closed_at"] is not None
    reopened = client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(token),
        json={"status": "in_progress"},
    ).json()
    assert reopened["closed_at"] is None


def test_archived_read_only_for_lead_but_admin_can_reopen(client, investigator, admin):
    token = login(client, "investigator")
    inv = create(client, token)
    archived = client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(token),
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    # Lead can no longer edit.
    response = client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(token),
        json={"title": "Too late"},
    )
    assert response.status_code == 403
    # Admin can reopen.
    admin_token = login(client, "admin")
    reopened = client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(admin_token),
        json={"status": "open"},
    )
    assert reopened.status_code == 200


def test_duplicate_membership_rejected(client, investigator, analyst):
    token = login(client, "investigator")
    inv = create(client, token)
    first = client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    assert second.status_code == 409


def test_member_removal_and_lead_protection(client, investigator, analyst):
    token = login(client, "investigator")
    inv = create(client, token)
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    removed = client.delete(
        f"/api/investigations/{inv['id']}/members/{analyst.id}", headers=auth_headers(token)
    )
    assert removed.status_code == 200
    assert analyst.id not in {m["user"]["id"] for m in removed.json()["members"]}
    # Lead cannot be removed while leading.
    response = client.delete(
        f"/api/investigations/{inv['id']}/members/{investigator.id}",
        headers=auth_headers(token),
    )
    assert response.status_code == 400


def test_non_manager_cannot_change_membership(client, investigator, analyst, custodian):
    token = login(client, "investigator")
    inv = create(client, token)
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    analyst_token = login(client, "analyst")
    response = client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(analyst_token),
        json={"user_id": custodian.id},
    )
    assert response.status_code == 403


def test_audit_trail_for_lifecycle(client, investigator, analyst, db_session):
    token = login(client, "investigator")
    inv = create(client, token)
    client.post(
        f"/api/investigations/{inv['id']}/members",
        headers=auth_headers(token),
        json={"user_id": analyst.id},
    )
    client.patch(
        f"/api/investigations/{inv['id']}",
        headers=auth_headers(token),
        json={"status": "in_progress"},
    )
    audit = client.get(
        f"/api/investigations/{inv['id']}/audit", headers=auth_headers(token)
    ).json()
    actions = [e["action"] for e in audit]
    assert "INVESTIGATION_CREATED" in actions
    assert "INVESTIGATION_MEMBER_ADDED" in actions
    assert "INVESTIGATION_STATUS_CHANGED" in actions
    assert all(e["actor_username"] == "investigator" for e in audit)


def test_audit_has_no_mutation_endpoints(client, investigator):
    token = login(client, "investigator")
    inv = create(client, token)
    base = f"/api/investigations/{inv['id']}/audit"
    assert client.post(base, headers=auth_headers(token)).status_code == 405
    assert client.delete(base, headers=auth_headers(token)).status_code == 405


def test_audit_not_visible_to_outsider(client, investigator, analyst):
    token = login(client, "investigator")
    inv = create(client, token)
    analyst_token = login(client, "analyst")
    response = client.get(
        f"/api/investigations/{inv['id']}/audit", headers=auth_headers(analyst_token)
    )
    assert response.status_code == 404


def test_audit_events_persisted_are_login_and_create(client, investigator, db_session):
    token = login(client, "investigator")
    create(client, token)
    events = db_session.execute(select(AuditEvent.action)).scalars().all()
    assert "USER_LOGIN" in events
    assert "INVESTIGATION_CREATED" in events
    # No secrets in audit metadata.
    for (metadata,) in db_session.execute(select(AuditEvent.event_metadata)).all():
        text = str(metadata)
        assert "password" not in text.lower()
        assert "token" not in text.lower()
