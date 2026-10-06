"""Shared test fixtures: SQLite-backed app with dependency-overridden sessions.

Tests run against in-memory SQLite (fast, no Postgres needed). Models use
plain String columns for roles/statuses, so they work on both databases.
Schema management in production remains Alembic; create_all is test-only.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.modules.users.models import Role, User
from app.core.config import settings


@pytest.fixture()
def storage_dir(tmp_path, monkeypatch):
    """Isolated evidence storage root so uploads never touch real storage."""
    target = tmp_path / "evidence-storage"
    monkeypatch.setattr(settings, "evidence_storage_root", str(target))
    return target


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    def override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def make_user(db_session, username="tester", role=Role.INVESTIGATOR, active=True):
    user = User(
        username=username,
        email=f"{username}@provena.local",
        full_name=f"{username.title()} User",
        password_hash=hash_password("password-123"),
        role=role.value,
        is_active=active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin(db_session):
    return make_user(db_session, "admin", Role.ADMIN)


@pytest.fixture()
def investigator(db_session):
    return make_user(db_session, "investigator", Role.INVESTIGATOR)


@pytest.fixture()
def analyst(db_session):
    return make_user(db_session, "analyst", Role.FORENSIC_ANALYST)


@pytest.fixture()
def custodian(db_session):
    return make_user(db_session, "custodian", Role.EVIDENCE_CUSTODIAN)


def login(client, username, password="password-123"):
    response = client.post(
        "/api/auth/login", json={"username_or_email": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
