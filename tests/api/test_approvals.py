import os
os.environ.setdefault("SECRET_KEY", "test-api-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.base import Base
from db.models import User, MonitorSite, ApprovalRequest
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
def seeded(db_engine):
    engine, TestingSessionLocal = db_engine
    db = TestingSessionLocal()
    owner = User(email="owner@example.com", hashed_password="x", role="user")
    admin = User(email="admin@example.com", hashed_password="x", role="admin")
    db.add_all([owner, admin])
    db.commit()
    db.refresh(owner)
    db.refresh(admin)
    site = MonitorSite(user_id=owner.id, instruction="test", approval_policy="always")
    db.add(site)
    db.commit()
    db.refresh(site)
    ar = ApprovalRequest(
        run_id="r1", site_id=site.id, action_type="slack", risk_score=0.9,
        payload={"webhook": "https://hooks.slack.com/services/T/B/X", "text": "hi"},
        status="pending", user_id=owner.id,
    )
    db.add(ar)
    db.commit()
    db.refresh(ar)
    owner_token = create_access_token({"sub": str(owner.id), "email": owner.email})
    admin_token = create_access_token({"sub": str(admin.id), "email": admin.email})
    db.close()
    return {
        "owner": owner, "admin": admin, "site": site, "request": ar,
        "owner_token": owner_token, "admin_token": admin_token,
        "SessionLocal": TestingSessionLocal,
    }


def test_get_approvals_requires_auth(client):
    resp = client.get("/api/approvals")
    assert resp.status_code == 401


def test_get_approvals_lists_owner_pending(client, seeded):
    resp = client.get(
        "/api/approvals",
        headers={"Authorization": f"Bearer {seeded['owner_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["action_type"] == "slack"
    assert data[0]["status"] == "pending"
    assert "payload" not in data[0]
    assert "webhook" not in data[0]


def test_owner_cannot_see_other_users_requests(client, db_engine, seeded):
    engine, SessionLocal = db_engine
    db = SessionLocal()
    other = User(email="other@example.com", hashed_password="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    other_site = MonitorSite(user_id=other.id, instruction="test")
    db.add(other_site)
    db.commit()
    db.refresh(other_site)
    db.add(ApprovalRequest(
        run_id="r2", site_id=other_site.id, action_type="stub", risk_score=0.9,
        payload={}, status="pending", user_id=other.id,
    ))
    db.commit()
    db.close()

    resp = client.get(
        "/api/approvals",
        headers={"Authorization": f"Bearer {seeded['owner_token']}"},
    )
    data = resp.json()
    assert all(r["id"] == seeded["request"].id for r in data)


def test_admin_sees_all(client, seeded, db_engine):
    engine, SessionLocal = db_engine
    db = SessionLocal()
    other = User(email="other2@example.com", hashed_password="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    other_site = MonitorSite(user_id=other.id, instruction="test")
    db.add(other_site)
    db.commit()
    db.refresh(other_site)
    db.add(ApprovalRequest(
        run_id="r3", site_id=other_site.id, action_type="stub", risk_score=0.9,
        payload={}, status="pending", user_id=other.id,
    ))
    db.commit()
    db.close()

    resp = client.get(
        "/api/approvals",
        headers={"Authorization": f"Bearer {seeded['admin_token']}"},
    )
    data = resp.json()
    assert len(data) == 2


def test_approve_executes_slack_and_returns_result(client, seeded):
    from unittest.mock import patch
    with patch("core.actions.handlers.slack.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        resp = client.post(
            f"/api/approvals/{seeded['request'].id}/approve",
            headers={"Authorization": f"Bearer {seeded['owner_token']}"},
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_approve_unknown_id_404(client, seeded):
    resp = client.post(
        "/api/approvals/9999/approve",
        headers={"Authorization": f"Bearer {seeded['owner_token']}"},
    )
    assert resp.status_code == 404


def test_approve_non_owner_403(client, seeded, db_engine):
    engine, SessionLocal = db_engine
    db = SessionLocal()
    other = User(email="other3@example.com", hashed_password="x")
    db.add(other)
    db.commit()
    db.refresh(other)
    other_token = create_access_token({"sub": str(other.id), "email": other.email})
    db.close()
    resp = client.post(
        f"/api/approvals/{seeded['request'].id}/approve",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_approve_twice_409(client, seeded):
    from unittest.mock import patch
    with patch("core.actions.handlers.slack.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        client.post(
            f"/api/approvals/{seeded['request'].id}/approve",
            headers={"Authorization": f"Bearer {seeded['owner_token']}"},
        )
        resp2 = client.post(
            f"/api/approvals/{seeded['request'].id}/approve",
            headers={"Authorization": f"Bearer {seeded['owner_token']}"},
        )
    assert resp2.status_code == 409


def test_reject_records_rejected(client, seeded):
    resp = client.post(
        f"/api/approvals/{seeded['request'].id}/reject",
        headers={"Authorization": f"Bearer {seeded['owner_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_admin_can_approve_other_users(client, seeded):
    from unittest.mock import patch
    with patch("core.actions.handlers.slack.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        resp = client.post(
            f"/api/approvals/{seeded['request'].id}/approve",
            headers={"Authorization": f"Bearer {seeded['admin_token']}"},
        )
    assert resp.status_code == 200


def test_failed_approval_surfaces_error_message(client, db_engine, seeded):
    engine, SessionLocal = db_engine
    db = SessionLocal()
    owner = db.query(User).filter(User.email == "owner@example.com").one()
    site = db.query(MonitorSite).filter(MonitorSite.user_id == owner.id).one()
    ghost = ApprovalRequest(
        run_id="r-ghost", site_id=site.id, action_type="ghost",
        risk_score=0.9, payload={"secret": "yes"}, status="pending",
        user_id=owner.id,
    )
    db.add(ghost)
    db.commit()
    db.refresh(ghost)
    db.close()

    resp = client.post(
        f"/api/approvals/{ghost.id}/approve",
        headers={"Authorization": f"Bearer {seeded['owner_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False

    listing = client.get(
        "/api/approvals",
        headers={"Authorization": f"Bearer {seeded['owner_token']}"},
    )
    data = listing.json()
    failed = next(r for r in data if r["id"] == ghost.id)
    assert failed["status"] == "failed"
    assert failed["error_message"] == "handler not registered"
    assert "payload" not in failed
    assert "secret" not in failed


def test_stale_pending_request_auto_expires(client, db_engine, seeded):
    from datetime import datetime, timedelta
    engine, SessionLocal = db_engine
    db = SessionLocal()
    ar = db.query(ApprovalRequest).filter(ApprovalRequest.id == seeded["request"].id).first()
    ar.created_at = datetime.utcnow() - timedelta(hours=48)
    db.commit()
    db.close()

    resp = client.get(
        "/api/approvals",
        headers={"Authorization": f"Bearer {seeded['owner_token']}"},
    )
    data = resp.json()
    assert data[0]["status"] == "expired"

    resp2 = client.post(
        f"/api/approvals/{seeded['request'].id}/approve",
        headers={"Authorization": f"Bearer {seeded['owner_token']}"},
    )
    assert resp2.status_code == 409
