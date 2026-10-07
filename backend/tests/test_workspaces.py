"""Registration, workspace invite, role, and isolation coverage."""

from tests.conftest import auth_headers, login


def register(client, username: str):
    response = client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.test",
        "full_name": username.title(),
        "password": "strong-pass-123",
    })
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_registration_workspace_invite_and_join(client):
    owner_token = register(client, "workspace_owner")
    owner_headers = auth_headers(owner_token)
    created = client.post("/api/workspaces", headers=owner_headers, json={"name": "Digital Lab"})
    assert created.status_code == 201
    assert created.json()["role"] == "admin"

    invite = client.post(
        "/api/workspaces/current/invites",
        headers=owner_headers,
        json={"role": "forensic_analyst", "expires_in_days": 7, "max_uses": 2},
    )
    assert invite.status_code == 201
    code = invite.json()["code"]
    assert code.startswith("PRV-")

    analyst_token = register(client, "new_analyst")
    joined = client.post(
        "/api/workspaces/join", headers=auth_headers(analyst_token), json={"code": code}
    )
    assert joined.status_code == 200
    assert joined.json()["role"] == "forensic_analyst"
    assert client.post(
        "/api/workspaces/join", headers=auth_headers(analyst_token), json={"code": code}
    ).status_code == 409

    members = client.get("/api/workspaces/current/members", headers=owner_headers)
    assert {item["username"] for item in members.json()} == {"workspace_owner", "new_analyst"}


def test_invalid_invite_and_duplicate_registration(client):
    token = register(client, "duplicate_name")
    assert token
    duplicate = client.post("/api/auth/register", json={
        "username": "duplicate_name", "email": "other@example.test",
        "full_name": "Other", "password": "strong-pass-123",
    })
    assert duplicate.status_code == 409
    invalid = client.post(
        "/api/workspaces/join", headers=auth_headers(token), json={"code": "PRV-not-a-real-code"}
    )
    assert invalid.status_code == 400


def test_cross_workspace_investigation_is_hidden(client):
    first = register(client, "first_owner")
    second = register(client, "second_owner")
    client.post("/api/workspaces", headers=auth_headers(first), json={"name": "First Lab"})
    client.post("/api/workspaces", headers=auth_headers(second), json={"name": "Second Lab"})
    inv = client.post(
        "/api/investigations",
        headers=auth_headers(first),
        json={"title": "Private first workspace case"},
    )
    assert inv.status_code == 201
    inv_id = inv.json()["id"]
    assert client.get(f"/api/investigations/{inv_id}", headers=auth_headers(second)).status_code == 404
    assert client.get("/api/investigations", headers=auth_headers(second)).json() == []
    assert client.get("/api/search?q=Private", headers=auth_headers(second)).json()["total"] == 0


def test_user_without_workspace_cannot_create_investigation(client):
    token = register(client, "not_onboarded")
    response = client.post(
        "/api/investigations", headers=auth_headers(token), json={"title": "No workspace"}
    )
    assert response.status_code == 403
