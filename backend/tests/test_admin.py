"""Admin user management tests: listing, activation guards, RBAC."""

from tests.conftest import auth_headers, login


def test_admin_lists_users_with_memberships(client, admin, investigator, db_session):
    admin_token = login(client, "admin")
    inv_token = login(client, "investigator")
    response = client.post(
        "/api/investigations", headers=auth_headers(inv_token), json={"title": "Admin view case"}
    )
    assert response.status_code == 201
    body = client.get("/api/admin/users", headers=auth_headers(admin_token)).json()
    usernames = {u["username"] for u in body}
    assert {"admin", "investigator"} <= usernames
    investigator_entry = next(u for u in body if u["username"] == "investigator")
    assert len(investigator_entry["investigations"]) == 1
    assert investigator_entry["investigations"][0]["case_number"].startswith("PRV-")


def test_non_admin_cannot_use_admin_endpoints(client, investigator):
    token = login(client, "investigator")
    assert client.get("/api/admin/users", headers=auth_headers(token)).status_code == 403
    assert (
        client.patch(
            "/api/admin/users/1", headers=auth_headers(token), json={"is_active": False}
        ).status_code
        == 403
    )


def test_admin_can_deactivate_and_reactivate(client, admin, investigator, db_session):
    admin_token = login(client, "admin")
    response = client.patch(
        f"/api/admin/users/{investigator.id}",
        headers=auth_headers(admin_token),
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert (
        client.post(
            "/api/auth/login",
            json={"username_or_email": "investigator", "password": "password-123"},
        ).status_code
        == 401
    )
    reactivated = client.patch(
        f"/api/admin/users/{investigator.id}",
        headers=auth_headers(admin_token),
        json={"is_active": True},
    )
    assert reactivated.json()["is_active"] is True


def test_admin_cannot_deactivate_self_or_last_admin(client, admin, db_session):
    admin_token = login(client, "admin")
    response = client.patch(
        f"/api/admin/users/{admin.id}",
        headers=auth_headers(admin_token),
        json={"is_active": False},
    )
    assert response.status_code == 400
