"""Backend smoke tests: the app must import, start, and answer /api/health."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_app_imports():
    assert app.title == "Provena API"


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "Provena API"
    assert body["db"] in {"ok", "not_configured", "unreachable"}


def test_health_without_database_configured():
    # Default dev settings ship with no DATABASE_URL, and the endpoint
    # must still answer instead of failing.
    response = client.get("/api/health")
    assert response.status_code == 200
