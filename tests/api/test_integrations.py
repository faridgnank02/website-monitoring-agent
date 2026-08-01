import os
os.environ.setdefault("SECRET_KEY", "test-api-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.models import User
from api.main import app
from api.deps import get_db
from api.auth.service import create_access_token


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, TestingSessionLocal


@pytest.fixture
def client(db_engine):
    engine, TestingSessionLocal = db_engine

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def authed_client(client, db_engine):
    engine, TestingSessionLocal = db_engine
    db = TestingSessionLocal()
    user = User(email="user@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return client, token, user.id, TestingSessionLocal


def test_get_integrations_returns_empty_defaults(authed_client):
    client, token, user_id, SessionLocal = authed_client
    db = SessionLocal()
    from db.models import MonitorSite
    site = MonitorSite(user_id=user_id, instruction="test")
    db.add(site)
    db.commit()
    db.refresh(site)
    db.close()

    resp = client.get(
        f"/api/integrations/sites/{site.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["actions_enabled"] == []
    assert data["integration_config"] == {}
    assert data["slack_webhook_masked"] == ""
    assert data["notion_token_masked"] == ""


def test_put_integrations_encrypts_token_and_masks_output(authed_client):
    client, token, user_id, SessionLocal = authed_client
    db = SessionLocal()
    from db.models import MonitorSite
    site = MonitorSite(user_id=user_id, instruction="test")
    db.add(site)
    db.commit()
    db.refresh(site)
    site_id = site.id
    db.close()

    resp = client.put(
        f"/api/integrations/sites/{site_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "actions_enabled": ["slack", "email"],
            "integration_config": {"notion": {"database_id": "db-123"}},
            "slack_webhook": "https://hooks.slack.com/services/T000/B000/XXX",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["actions_enabled"] == ["slack", "email"]
    assert data["integration_config"] == {"notion": {"database_id": "db-123"}}
    assert data["slack_webhook_masked"] == "****/XXX"

    db = SessionLocal()
    stored = db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
    assert stored.slack_webhook.startswith("gAAAA")
    assert "hooks.slack.com" not in stored.slack_webhook
    db.close()


def test_put_integrations_returns_404_for_other_users_site(authed_client):
    client, token, user_id, SessionLocal = authed_client
    db = SessionLocal()
    from db.models import MonitorSite
    site = MonitorSite(user_id=999, instruction="test")
    db.add(site)
    db.commit()
    db.refresh(site)
    db.close()

    resp = client.put(
        f"/api/integrations/sites/{site.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"actions_enabled": ["email"]},
    )
    assert resp.status_code == 404


def test_get_integrations_requires_auth(authed_client):
    client, token, user_id, SessionLocal = authed_client
    resp = client.get("/api/integrations/sites/1")
    assert resp.status_code == 401
