from datetime import datetime
from db.base import init_db, SessionLocal
from db.models import User, MonitorSite, AuditLog, ApprovalRequest


def test_audit_log_creation():
    init_db()
    db = SessionLocal()
    try:
        log = AuditLog(
            run_id="run-1",
            site_id=1,
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
    finally:
        db.close()


def test_approval_request_creation():
    init_db()
    db = SessionLocal()
    try:
        req = ApprovalRequest(
            run_id="run-1",
            change_id=1,
            action_type="slack_post",
            risk_score=0.5,
            payload={"channel": "#deals"},
            status="pending",
            user_id=1,
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        assert req.id > 0
    finally:
        db.close()


def test_site_has_monitor_mode():
    init_db()
    db = SessionLocal()
    try:
        user = User(email="test@example.com", hashed_password="x")
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
    finally:
        db.close()
