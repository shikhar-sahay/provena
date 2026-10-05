"""Auth tests: login, failures, inactive users, protected routes, RBAC basics."""

from tests.conftest import auth_headers, login


def test_login_success_by_username(client, investigator):
    body = client.post(
        "/api/auth/login",
        json={"username_or_email": "investigator", "password": "password-123"},
    ).json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "investigator"
    assert "password_hash" not in body["user"]


def test_login_success_by_email(client, investigator):
    response = client.post(
        "/api/auth/login",
        json={"username_or_email": "investigator@provena.local", "password": "password-123"},
    )
    assert response.status_code == 200


def test_login_wrong_password(client, investigator):
    response = client.post(
        "/api/auth/login",
        json={"username_or_email": "investigator", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post(
        "/api/auth/login", json={"username_or_email": "ghost", "password": "password-123"}
    )
    assert response.status_code == 401


def test_login_inactive_user(client, db_session, investigator):
    investigator.is_active = False
    db_session.commit()
    response = client.post(
        "/api/auth/login",
        json={"username_or_email": "investigator", "password": "password-123"},
    )
    assert response.status_code == 401


def test_me_returns_current_user(client, investigator):
    token = login(client, "investigator")
    body = client.get("/api/auth/me", headers=auth_headers(token)).json()
    assert body["username"] == "investigator"
    assert body["role"] == "investigator"


def test_protected_endpoint_without_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/investigations").status_code == 401


def test_invalid_token_rejected(client):
    assert client.get("/api/auth/me", headers=auth_headers("bogus")).status_code == 401


def test_logout_records_event_and_me_still_requires_token(client, investigator, db_session):
    token = login(client, "investigator")
    response = client.post("/api/auth/logout", headers=auth_headers(token))
    assert response.status_code == 200
    # Logout does not invalidate the stateless token server-side, but the
    # client discards it. Audit trail must contain the logout.
    from sqlalchemy import select

    from app.modules.audit.models import AuditEvent

    events = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "USER_LOGOUT")
    ).scalars().all()
    assert len(events) == 1


def test_admin_can_create_user(client, admin):
    token = login(client, "admin")
    response = client.post(
        "/api/users",
        headers=auth_headers(token),
        json={
            "username": "newbie",
            "email": "newbie@provena.local",
            "full_name": "New Hire",
            "password": "password-123",
            "role": "forensic_analyst",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "forensic_analyst"
    assert "password_hash" not in body


def test_non_admin_cannot_create_user(client, investigator):
    token = login(client, "investigator")
    response = client.post(
        "/api/users",
        headers=auth_headers(token),
        json={
            "username": "newbie",
            "email": "newbie@provena.local",
            "password": "password-123",
            "role": "investigator",
        },
    )
    assert response.status_code == 403


def test_duplicate_user_rejected(client, admin, investigator):
    token = login(client, "admin")
    response = client.post(
        "/api/users",
        headers=auth_headers(token),
        json={
            "username": "investigator",
            "email": "other@provena.local",
            "password": "password-123",
            "role": "investigator",
        },
    )
    assert response.status_code == 409
