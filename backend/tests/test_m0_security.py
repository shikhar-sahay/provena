"""Synthetic multipart and workspace isolation regression coverage."""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.audit.models import AuditEvent
from app.modules.evidence.models import Evidence
from app.modules.investigations.service import can_access, can_manage, get_investigation
from app.modules.users.models import Role
from app.modules.workspaces.models import Workspace, WorkspaceMembership
from tests.conftest import auth_headers, login, make_user
from tests.test_evidence import make_investigation, upload


def membership(db, user, workspace_id=None):
    return db.execute(select(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user.id,
        WorkspaceMembership.workspace_id == (workspace_id or user.active_workspace_id),
    )).scalar_one()


def second_workspace(db, owner, shared=None):
    workspace = Workspace(name="Other lab", slug="other-lab", created_by_id=owner.id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=owner.id, role="admin"))
    if shared is not None:
        db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=shared.id, role="investigator"))
    db.commit()
    return workspace


def test_suspension_is_workspace_scoped_and_audited(client, db_session, admin, investigator):
    owner = make_user(db_session, "other_owner", Role.ADMIN)
    other = second_workspace(db_session, owner, investigator)
    a = investigator.active_workspace_id
    headers = auth_headers(login(client, "admin"))
    user_headers = auth_headers(login(client, "investigator"))
    response = client.patch(f"/api/admin/users/{investigator.id}", headers=headers, json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert investigator.is_active
    assert not membership(db_session, investigator, a).is_active
    assert membership(db_session, investigator, other.id).is_active
    assert client.get("/api/auth/me", headers=user_headers).json()["active_workspace_id"] is None
    assert client.get("/api/investigations", headers=user_headers).status_code == 403
    assert client.post(f"/api/workspaces/{other.id}/select", headers=user_headers).status_code == 200
    assert client.post("/api/investigations", headers=user_headers, json={"title": "Other workspace case"}).status_code == 201
    assert client.post(f"/api/workspaces/{a}/select", headers=user_headers).status_code == 403
    assert client.get("/api/workspaces", headers=user_headers).json()[0]["id"] == other.id
    roster = client.get("/api/admin/users", headers=headers).json()
    assert next(row for row in roster if row["id"] == investigator.id)["is_active"] is False
    assert investigator.id not in [row["id"] for row in client.get("/api/users", headers=headers).json()]
    events = db_session.execute(select(AuditEvent).where(AuditEvent.action == "WORKSPACE_MEMBERSHIP_SUSPENDED")).scalars().all()
    assert len(events) == 1 and events[0].event_metadata["user_id"] == investigator.id
    restored = client.patch(f"/api/admin/users/{investigator.id}", headers=headers, json={"is_active": True})
    assert restored.status_code == 200 and restored.json()["is_active"] is True
    assert client.post(f"/api/workspaces/{a}/select", headers=user_headers).status_code == 200


def test_admin_cannot_administer_unrelated_workspace(client, db_session, admin):
    outsider = make_user(db_session, "outsider")
    db_session.delete(membership(db_session, outsider))
    other = second_workspace(db_session, outsider)
    outsider.active_workspace_id = other.id
    db_session.commit()
    headers = auth_headers(login(client, "admin"))
    assert client.patch(f"/api/admin/users/{outsider.id}", headers=headers, json={"is_active": False}).status_code == 404
    assert client.patch(f"/api/workspaces/current/members/{outsider.id}", headers=headers, json={"role": "investigator"}).status_code == 404
    assert outsider.is_active and membership(db_session, outsider).is_active


def test_workspace_roles_not_global_cached_roles(client, db_session, admin, investigator):
    investigator.role = "admin"  # Cached role from a different selected workspace.
    db_session.commit()
    headers = auth_headers(login(client, "admin"))
    roster = client.get("/api/admin/users", headers=headers).json()
    assert next(row for row in roster if row["id"] == investigator.id)["role"] == "investigator"
    assert client.patch(f"/api/admin/users/{investigator.id}", headers=headers, json={"is_active": False}).status_code == 200


def test_last_active_admin_is_workspace_scoped(client, db_session, admin):
    # A global/cached admin elsewhere must not satisfy this workspace's guard.
    other_admin = make_user(db_session, "elsewhere_admin", Role.ADMIN)
    membership(db_session, other_admin).is_active = False
    second_workspace(db_session, other_admin)
    db_session.commit()
    headers = auth_headers(login(client, "admin"))
    role = client.patch(f"/api/workspaces/current/members/{admin.id}", headers=headers, json={"role": "investigator"})
    assert role.status_code == 400
    assert "At least one active workspace administrator" in role.text
    suspended = client.patch(f"/api/admin/users/{admin.id}", headers=headers, json={"is_active": False})
    assert suspended.status_code == 400
    assert "At least one active workspace administrator" in suspended.text


def test_two_admins_allow_demotion_and_suspend_restore(client, db_session, admin):
    peer = make_user(db_session, "peer_admin", Role.ADMIN)
    headers = auth_headers(login(client, "admin"))
    assert client.patch(f"/api/admin/users/{peer.id}", headers=headers, json={"is_active": False}).status_code == 200
    assert peer.is_active
    assert client.patch(f"/api/admin/users/{peer.id}", headers=headers, json={"is_active": True}).status_code == 200
    assert client.patch(f"/api/workspaces/current/members/{admin.id}", headers=headers, json={"role": "investigator"}).status_code == 200
    assert client.get("/api/admin/users", headers=headers).status_code == 403


def test_invite_does_not_restore_suspended_membership(client, db_session, admin, investigator):
    headers = auth_headers(login(client, "admin"))
    user_headers = auth_headers(login(client, "investigator"))
    invite = client.post("/api/workspaces/current/invites", headers=headers, json={"role": "investigator"}).json()
    assert client.patch(f"/api/admin/users/{investigator.id}", headers=headers, json={"is_active": False}).status_code == 200
    assert client.post("/api/workspaces/join", headers=user_headers, json={"code": invite["code"]}).status_code == 403
    assert not membership(db_session, investigator).is_active


@pytest.mark.parametrize("state", ["suspended", "missing", "inactive_workspace"])
def test_direct_case_routes_require_active_workspace(client, db_session, investigator, storage_dir, state):
    headers = auth_headers(login(client, "investigator"))
    token = headers["Authorization"].split()[1]
    inv = make_investigation(client, token)
    base = f"/api/investigations/{inv['id']}"
    item = upload(client, token, inv["id"]).json()
    assert client.post(f"{base}/evidence/{item['id']}/verify", headers=headers).status_code == 200
    run = client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": [item["id"]]}).json()
    report = client.post(f"{base}/analysis/reports", headers=headers).json()
    member = membership(db_session, investigator)
    if state == "missing":
        db_session.delete(member)
    elif state == "suspended":
        member.is_active = False
    else:
        db_session.get(Workspace, member.workspace_id).is_active = False
    db_session.commit()
    case = get_investigation(db_session, inv["id"])
    assert not can_access(db_session, case, investigator)
    assert not can_manage(db_session, case, investigator)
    for suffix in ["", "/evidence", f"/evidence/{item['id']}", f"/evidence/{item['id']}/download",
                   "/analysis/eligibility", "/analysis/runs", f"/analysis/runs/{run['id']}",
                   "/analysis/artifacts", "/analysis/correlations", "/analysis/findings", "/analysis/notes",
                   "/analysis/reports", f"/analysis/reports/{report['id']}", "/timeline", "/custody", "/audit"]:
        assert client.get(base + suffix, headers=headers).status_code == 404, suffix
    assert client.patch(base, headers=headers, json={"title": "Denied"}).status_code == 404
    assert client.post(f"{base}/evidence/{item['id']}/verify", headers=headers).status_code == 404
    assert client.post(f"{base}/analysis/runs", headers=headers, json={"evidence_ids": [item["id"]]}).status_code == 404
    assert client.post(f"{base}/analysis/reports", headers=headers).status_code == 404
    assert client.get("/api/search?q=Firewall", headers=headers).status_code == 403


@pytest.mark.parametrize("content_type,body,expected", [
    ("multipart/form-data", b"missing-boundary", 400),
    ("multipart/form-data; boundary=test", b"--test\r\nBad header\r\n\r\nx\r\n--test--\r\n", 400),
    ("multipart/form-data; boundary=test", b"--test\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.log\"\r\n", 422),
    ("multipart/form-data; boundary=test", b"--test\r\nX-Large: " + b"x" * 20000 + b"\r\n\r\nx\r\n--test--\r\n", 400),
])
def test_malformed_multipart_has_no_registration(client, investigator, storage_dir, db_session, content_type, body, expected):
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    response = client.post(f"/api/investigations/{inv['id']}/evidence", content=body,
                           headers={**auth_headers(token), "Content-Type": content_type})
    assert response.status_code == expected, response.text
    assert db_session.execute(select(Evidence)).scalars().all() == []
    assert not [p for p in storage_dir.rglob("*") if p.is_file()]


def test_upload_limit_boundary_and_no_failed_registration(client, investigator, storage_dir, db_session, monkeypatch):
    monkeypatch.setattr(settings, "evidence_max_upload_bytes", 10)
    token = login(client, "investigator")
    inv = make_investigation(client, token)
    assert upload(client, token, inv["id"], content=b"x" * 10).status_code == 201
    assert upload(client, token, inv["id"], content=b"x" * 11).status_code == 413
    assert len(db_session.execute(select(Evidence)).scalars().all()) == 1
    assert len([p for p in storage_dir.rglob("*") if p.is_file()]) == 1
