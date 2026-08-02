import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import ApprovalRequest, AuditLog, MonitorChange, MonitorSite, User


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_audit_log_creation(db):
    user = User(email=f"audit-{uuid.uuid4()}@example.com", hashed_password="x")
    db.add(user)
    db.commit()

    site = MonitorSite(user_id=user.id, instruction="test")
    db.add(site)
    db.commit()
    db.refresh(site)

    change = MonitorChange(site_id=site.id)
    db.add(change)
    db.commit()
    db.refresh(change)

    log = AuditLog(
        run_id="run-1",
        site_id=site.id,
        change_id=change.id,
        actor="scout",
        action="scrape",
        reasoning="no previous snapshot",
        cost_usd=0.001,
        latency_ms=120.0,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    assert log.id > 0
    assert log.site_id == site.id
    assert log.change_id == change.id


def test_approval_request_creation(db):
    user = User(
        email=f"approval-{uuid.uuid4()}@example.com", hashed_password="x"
    )
    db.add(user)
    db.commit()

    req = ApprovalRequest(
        run_id="run-1",
        change_id=None,
        action_type="slack_post",
        risk_score=0.5,
        payload={"channel": "#deals"},
        status="pending",
        user_id=user.id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    assert req.id > 0
    assert req.user_id == user.id
    assert req.change_id is None


def test_approval_request_resolution_columns_default(db):
    user = User(email=f"approval-{uuid.uuid4()}@example.com", hashed_password="x")
    db.add(user)
    db.commit()

    ar = ApprovalRequest(
        run_id="r1",
        action_type="slack",
        risk_score=0.4,
        payload={"text": "hi"},
        status="pending",
        user_id=user.id,
    )
    db.add(ar)
    db.commit()
    db.refresh(ar)

    assert ar.resolved_by is None
    assert ar.output is None
    assert ar.error_message is None
    assert ar.status == "pending"


def test_site_has_monitor_mode(db):
    user = User(email=f"site-{uuid.uuid4()}@example.com", hashed_password="x")
    db.add(user)
    db.commit()

    site = MonitorSite(
        user_id=user.id,
        instruction="test",
        monitor_mode="competitive",
        approval_policy="high_risk",
    )
    db.add(site)
    db.commit()
    db.refresh(site)

    assert site.monitor_mode == "competitive"
    assert site.user_id == user.id


def test_site_actions_config_defaults(db):
    user = User(email=f"actions-{uuid.uuid4()}@example.com", hashed_password="x")
    db.add(user)
    db.commit()

    site = MonitorSite(user_id=user.id, instruction="test")
    db.add(site)
    db.commit()
    db.refresh(site)

    assert site.actions_enabled == []
    assert site.integration_config == {}
