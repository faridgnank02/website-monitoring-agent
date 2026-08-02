import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.actions.base import ActionHandler, ProposedAction, ActionResult
from core.actions.registry import ActionHandlerRegistry
from core.approvals.service import ApprovalService, ApprovalConflict
from db.base import Base
from db.models import User, ApprovalRequest


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


class StubHandler(ActionHandler):
    name = "stub"
    risk_score = 0.4

    def __init__(self):
        self.executed = 0

    def propose(self, context):  # pragma: no cover
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        self.executed += 1
        return ActionResult(success=True, type=self.name, message="done", output={"ok": True})


class FailingHandler(ActionHandler):
    name = "stub_fail"
    risk_score = 0.4

    def __init__(self):
        self.executed = 0

    def propose(self, context):  # pragma: no cover
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        self.executed += 1
        return ActionResult(success=False, type=self.name, message="boom")


def make_user(db, email="admin@example.com", role="admin"):
    user = User(email=email, hashed_password="x", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_request(db, user, action_type="stub", status="pending"):
    req = ApprovalRequest(
        run_id="r1",
        action_type=action_type,
        risk_score=0.4,
        payload={"x": 1},
        status=status,
        user_id=user.id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_approve_executes_handler_and_records_result(db):
    actor = make_user(db)
    req = make_request(db, actor)
    handler = StubHandler()
    registry = ActionHandlerRegistry()
    registry.register(handler)
    svc = ApprovalService(db, registry=registry)

    result = svc.approve(req, actor)

    assert handler.executed == 1
    assert result.success is True
    assert req.status == "approved"
    assert req.output == {"ok": True}
    assert req.resolved_by == actor.id
    assert req.resolved_at is not None


def test_approve_failure_records_failed_status(db):
    actor = make_user(db)
    req = make_request(db, actor, action_type="stub_fail")
    handler = FailingHandler()
    registry = ActionHandlerRegistry()
    registry.register(handler)
    svc = ApprovalService(db, registry=registry)

    result = svc.approve(req, actor)

    assert result.success is False
    assert req.status == "failed"
    assert req.error_message == "boom"
    assert req.output is None


def test_approve_unknown_handler_marks_failed(db):
    actor = make_user(db)
    req = make_request(db, actor, action_type="ghost")
    svc = ApprovalService(db, registry=ActionHandlerRegistry())

    result = svc.approve(req, actor)

    assert result.success is False
    assert req.status == "failed"
    assert req.error_message == "handler not registered"


def test_reject_records_rejected_without_executing(db):
    actor = make_user(db)
    req = make_request(db, actor)
    handler = StubHandler()
    registry = ActionHandlerRegistry()
    registry.register(handler)
    svc = ApprovalService(db, registry=registry)

    svc.reject(req, actor)

    assert req.status == "rejected"
    assert req.resolved_by == actor.id
    assert handler.executed == 0


def test_approve_second_time_conflicts(db):
    actor = make_user(db)
    req = make_request(db, actor)
    handler = StubHandler()
    registry = ActionHandlerRegistry()
    registry.register(handler)
    svc = ApprovalService(db, registry=registry)

    svc.approve(req, actor)
    assert handler.executed == 1

    again = db.query(ApprovalRequest).filter(ApprovalRequest.id == req.id).one()

    with pytest.raises(ApprovalConflict):
        svc.approve(again, actor)

    assert handler.executed == 1


def test_approve_expired_request_conflicts(db):
    actor = make_user(db)
    req = make_request(db, actor, status="expired")
    svc = ApprovalService(db, registry=ActionHandlerRegistry())

    with pytest.raises(ApprovalConflict):
        svc.approve(req, actor)


def test_claim_atomic_returns_false_when_already_claimed(db):
    actor = make_user(db)
    req = make_request(db, actor)
    svc = ApprovalService(db, registry=ActionHandlerRegistry())

    assert svc._claim(req.id) is True
    assert svc._claim(req.id) is False

    fresh = make_request(db, actor, action_type="stub")
    assert svc._claim(fresh.id) is True
    assert svc._claim(fresh.id) is False