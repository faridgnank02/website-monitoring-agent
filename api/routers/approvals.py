from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from core.approvals.service import ApprovalService, ApprovalConflict, ApprovalNotAuthorized
from core.actions.registry import build_default_registry
from db.models import User, ApprovalRequest


router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _masked(req: ApprovalRequest) -> dict:
    return {
        "id": req.id,
        "run_id": req.run_id,
        "site_id": req.site_id,
        "action_type": req.action_type,
        "risk_score": req.risk_score,
        "status": req.status,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "resolved_at": req.resolved_at.isoformat() if req.resolved_at else None,
        "resolved_by": req.resolved_by,
    }


@router.get("")
def list_approvals(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ApprovalService(db, registry=build_default_registry())
    reqs = service.list(current_user, status=status)
    return [_masked(r) for r in reqs]


@router.post("/{approval_id}/approve")
def approve_approval(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ApprovalService(db, registry=build_default_registry())
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if req is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    try:
        result = service.approve(req, current_user)
    except ApprovalConflict:
        raise HTTPException(status_code=409, detail="request already resolved or expired")
    except ApprovalNotAuthorized:
        raise HTTPException(status_code=403, detail="not authorized")
    return {
        "success": result.success,
        "message": result.message,
        "output": result.output,
        "type": result.type,
    }


@router.post("/{approval_id}/reject")
def reject_approval(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ApprovalService(db, registry=build_default_registry())
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if req is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    try:
        service.reject(req, current_user)
    except ApprovalConflict:
        raise HTTPException(status_code=409, detail="request already resolved or expired")
    except ApprovalNotAuthorized:
        raise HTTPException(status_code=403, detail="not authorized")
    return _masked(req)
