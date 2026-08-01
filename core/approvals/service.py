"""
Human-in-the-loop approval workflow: list, approve (execute), reject, lazy-expire.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from core.actions.base import ProposedAction, ActionResult
from core.actions.registry import ActionHandlerRegistry, build_default_registry
from config.settings import APPROVAL_TTL_HOURS
from db.models import ApprovalRequest, User, MonitorSite


class ApprovalConflict(Exception):
    pass


class ApprovalNotAuthorized(Exception):
    pass


class ApprovalService:
    def __init__(self, db: Session, registry: Optional[ActionHandlerRegistry] = None):
        self.db = db
        self.registry = registry or build_default_registry()

    def _expire_stale(self) -> None:
        cutoff = datetime.utcnow() - timedelta(hours=APPROVAL_TTL_HOURS)
        stale = (
            self.db.query(ApprovalRequest)
            .filter(ApprovalRequest.status == "pending")
            .filter(ApprovalRequest.created_at < cutoff)
            .all()
        )
        for req in stale:
            req.status = "expired"
            req.resolved_at = datetime.utcnow()
        if stale:
            self.db.commit()

    def list(self, actor: User, status: Optional[str] = None):
        self._expire_stale()
        query = self.db.query(ApprovalRequest)
        if actor.role != "admin":
            site_ids = [
                s.id for s in self.db.query(MonitorSite.id).filter(MonitorSite.user_id == actor.id).all()
            ]
            query = query.filter(ApprovalRequest.site_id.in_(site_ids))
        if status:
            query = query.filter(ApprovalRequest.status == status)
        return query.order_by(ApprovalRequest.created_at.desc()).all()

    def _ensure_can_act(self, req: ApprovalRequest, actor: User) -> None:
        if actor.role != "admin":
            site = self.db.query(MonitorSite).filter(MonitorSite.id == req.site_id).first()
            if site is None or site.user_id != actor.id:
                raise ApprovalNotAuthorized()

    def approve(self, req: ApprovalRequest, actor: User) -> ActionResult:
        self._expire_stale()
        if req.status != "pending":
            raise ApprovalConflict("request already resolved or expired")
        self._ensure_can_act(req, actor)
        handler = self.registry.get(req.action_type)
        if handler is None:
            result = ActionResult(
                success=False,
                type=req.action_type,
                message="handler not registered",
            )
        else:
            proposed = ProposedAction(
                type=req.action_type,
                risk_score=req.risk_score or 0.0,
                payload=req.payload or {},
                description="",
            )
            result = handler.execute(proposed)
        req.status = "approved"
        req.resolved_at = datetime.utcnow()
        req.resolved_by = actor.id
        if result.success:
            req.output = result.output
        else:
            req.error_message = result.message
        self.db.commit()
        return result

    def reject(self, req: ApprovalRequest, actor: User) -> None:
        self._expire_stale()
        if req.status != "pending":
            raise ApprovalConflict("request already resolved or expired")
        self._ensure_can_act(req, actor)
        req.status = "rejected"
        req.resolved_at = datetime.utcnow()
        req.resolved_by = actor.id
        self.db.commit()
