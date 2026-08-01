from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from core.actions.base import ActionHandler, ProposedAction, ActionResult
from core.actions.registry import ActionHandlerRegistry
from core.approvals.service import ApprovalService
from db.models import ApprovalRequest


class StubHandler(ActionHandler):
    name = "stub"
    risk_score = 0.4
    executed = 0

    def propose(self, context):  # pragma: no cover
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        StubHandler.executed += 1
        return ActionResult(success=True, type=self.name, message="done", output={"ok": True})


def make_service(db, registry=None):
    return ApprovalService(db, registry=registry)


def make_actor(user_id=7, role="admin"):
    return MagicMock(id=user_id, role=role)


def test_approve_executes_handler_and_records_result():
    db = MagicMock(spec=Session)
    handler = StubHandler()
    registry = ActionHandlerRegistry()
    registry.register(handler)
    svc = make_service(db, registry)
    svc._expire_stale = lambda: None

    req = ApprovalRequest(
        id=1, run_id="r1", action_type="stub", risk_score=0.4,
        payload={"x": 1}, status="pending", user_id=7,
    )
    actor = make_actor()

    result = svc.approve(req, actor)

    assert result.success is True
    assert req.status == "approved"
    assert req.resolved_by == 7
    assert req.output == {"ok": True}
    assert req.resolved_at is not None


def test_approve_unknown_handler_returns_failure_result():
    db = MagicMock(spec=Session)
    svc = make_service(db)
    svc.registry = ActionHandlerRegistry()
    svc._expire_stale = lambda: None
    req = ApprovalRequest(
        id=1, run_id="r1", action_type="ghost", risk_score=0.4,
        payload={}, status="pending", user_id=7,
    )
    result = svc.approve(req, make_actor())
    assert result.success is False
    assert req.status == "approved"
    assert req.error_message == "handler not registered"


def test_reject_records_rejected_without_executing():
    db = MagicMock(spec=Session)
    handler = StubHandler()
    registry = ActionHandlerRegistry()
    registry.register(handler)
    svc = make_service(db, registry)
    svc._expire_stale = lambda: None
    before = StubHandler.executed
    req = ApprovalRequest(
        id=1, run_id="r1", action_type="stub", risk_score=0.4,
        payload={}, status="pending", user_id=7,
    )
    svc.reject(req, make_actor())
    assert req.status == "rejected"
    assert req.resolved_by == 7
    assert StubHandler.executed == before


def test_approve_expired_request_conflicts():
    db = MagicMock(spec=Session)
    svc = make_service(db)
    req = ApprovalRequest(
        id=1, run_id="r1", action_type="stub", risk_score=0.4,
        payload={}, status="expired", user_id=7,
    )
    try:
        svc.approve(req, make_actor())
        raise AssertionError("expected conflict")
    except Exception as e:
        assert type(e).__name__ == "ApprovalConflict"
