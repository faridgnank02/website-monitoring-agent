"""
Monitor API routes.
All endpoints are scoped to the authenticated user (user_id isolation).
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Union

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from db.models import User, MonitorSite, MonitorSnapshot, MonitorChange, NotificationLog
from core.monitor_service import run_monitor_for_site

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

# In-memory SSE subscriber queues  {user_id: [queue, ...]}
_sse_subscribers: dict[int, list[asyncio.Queue]] = {}


def _broadcast(user_id: int, event: dict):
    """Push an SSE event to all open streams for this user."""
    for q in _sse_subscribers.get(user_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SiteCreate(BaseModel):
    instruction: str
    threshold: float = 1.0
    schedule_cron: str = "0 */6 * * *"
    use_case: str = "general"
    tags: list = []
    screenshot_enabled: bool = False


class SiteUpdate(BaseModel):
    instruction: Optional[str] = None
    threshold: Optional[float] = None
    schedule_cron: Optional[str] = None
    use_case: Optional[str] = None
    tags: Optional[list] = None
    active: Optional[bool] = None
    screenshot_enabled: Optional[bool] = None


class SiteOut(BaseModel):
    id: int
    instruction: str
    url: Optional[str]
    threshold: float
    schedule_cron: str
    use_case: str
    tags: list
    active: bool
    screenshot_enabled: bool
    created_at: datetime
    last_checked_at: Optional[datetime]
    last_change_score: Optional[float]

    class Config:
        from_attributes = True


class SnapshotOut(BaseModel):
    id: int
    scraped_at: datetime
    content_hash: str
    content_length: int
    status: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


class ChangeOut(BaseModel):
    id: int
    detected_at: datetime
    change_score: float
    added_lines: int
    removed_lines: int
    modified_lines: int
    diff_summary: Optional[str]
    alert_sent: bool
    old_snapshot_id: Optional[int]
    new_snapshot_id: Optional[int]

    class Config:
        from_attributes = True


class SiteHistoryOut(BaseModel):
    site: SiteOut
    snapshots: List[SnapshotOut]
    changes: List[ChangeOut]


class StatsOut(BaseModel):
    total_sites: int
    active_sites: int
    changes_this_week: int
    alerts_sent_this_week: int
    avg_change_score: float
    use_case_breakdown: dict


class DiffOut(BaseModel):
    old_content: Optional[str]
    new_content: Optional[str]
    change_id: int
    change_score: float
    diff_summary: Optional[str]


# ---------------------------------------------------------------------------
# Sites CRUD
# ---------------------------------------------------------------------------

@router.get("/sites", response_model=List[SiteOut])
def list_sites(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(MonitorSite).filter(MonitorSite.user_id == user.id).order_by(MonitorSite.created_at.desc()).all()


@router.post("/sites", response_model=SiteOut, status_code=201)
def create_site(body: SiteCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    site = MonitorSite(
        user_id=user.id,
        instruction=body.instruction,
        threshold=body.threshold,
        schedule_cron=body.schedule_cron,
        use_case=body.use_case,
        tags=body.tags,
        screenshot_enabled=body.screenshot_enabled,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.put("/sites/{site_id}", response_model=SiteOut)
def update_site(
    site_id: int,
    body: SiteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site = _get_site_or_404(site_id, user.id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    site = _get_site_or_404(site_id, user.id, db)
    db.delete(site)
    db.commit()


# ---------------------------------------------------------------------------
# Site history + diff viewer
# ---------------------------------------------------------------------------

@router.get("/sites/{site_id}/history", response_model=SiteHistoryOut)
def get_site_history(
    site_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site = _get_site_or_404(site_id, user.id, db)
    snapshots = (
        db.query(MonitorSnapshot)
        .filter(MonitorSnapshot.site_id == site_id)
        .order_by(MonitorSnapshot.scraped_at.desc())
        .limit(limit)
        .all()
    )
    changes = (
        db.query(MonitorChange)
        .filter(MonitorChange.site_id == site_id)
        .order_by(MonitorChange.detected_at.desc())
        .limit(limit)
        .all()
    )
    return SiteHistoryOut(site=site, snapshots=snapshots, changes=changes)


@router.get("/changes/{change_id}/diff", response_model=DiffOut)
def get_diff(
    change_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    change = db.query(MonitorChange).filter(MonitorChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    # Ownership check via site
    site = db.query(MonitorSite).filter(MonitorSite.id == change.site_id, MonitorSite.user_id == user.id).first()
    if not site:
        raise HTTPException(status_code=403, detail="Not authorized")

    old_content = change.old_snapshot.content_markdown if change.old_snapshot else None
    new_content = change.new_snapshot.content_markdown if change.new_snapshot else None

    return DiffOut(
        old_content=old_content,
        new_content=new_content,
        change_id=change.id,
        change_score=change.change_score,
        diff_summary=change.diff_summary,
    )


# ---------------------------------------------------------------------------
# Screenshot & Visual Diff endpoints
# ---------------------------------------------------------------------------

@router.get("/sites/{site_id}/screenshots/{snapshot_id}")
def get_screenshot(
    site_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the raw screenshot PNG for a snapshot."""
    site = _get_site_or_404(site_id, user.id, db)
    snapshot = db.query(MonitorSnapshot).filter(
        MonitorSnapshot.id == snapshot_id,
        MonitorSnapshot.site_id == site_id,
    ).first()
    if not snapshot or not snapshot.screenshot_path:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    from core.visual.storage import FileSystemScreenshotStorage
    storage = FileSystemScreenshotStorage(".")
    data = storage.load(snapshot.screenshot_path)
    if data is None:
        raise HTTPException(status_code=404, detail="Screenshot file missing")
    return StreamingResponse(iter([data]), media_type="image/png")


@router.get("/changes/{change_id}/visual-diff")
def get_visual_diff(
    change_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the visual diff overlay PNG for a change."""
    change = db.query(MonitorChange).filter(MonitorChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    # Ownership check via site
    site = db.query(MonitorSite).filter(
        MonitorSite.id == change.site_id,
        MonitorSite.user_id == user.id,
    ).first()
    if not site:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not change.visual_diff_path:
        raise HTTPException(status_code=404, detail="Visual diff not found")

    from core.visual.storage import FileSystemScreenshotStorage
    storage = FileSystemScreenshotStorage(".")
    data = storage.load(change.visual_diff_path)
    if data is None:
        raise HTTPException(status_code=404, detail="Visual diff file missing")
    return StreamingResponse(iter([data]), media_type="image/png")


# ---------------------------------------------------------------------------
# Recent changes feed + stats
# ---------------------------------------------------------------------------

@router.get("/changes", response_model=List[ChangeOut])
def list_changes(
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site_ids = [s.id for s in db.query(MonitorSite.id).filter(MonitorSite.user_id == user.id)]
    return (
        db.query(MonitorChange)
        .filter(MonitorChange.site_id.in_(site_ids))
        .order_by(MonitorChange.detected_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    week_ago = datetime.utcnow() - timedelta(days=7)
    sites = db.query(MonitorSite).filter(MonitorSite.user_id == user.id).all()
    site_ids = [s.id for s in sites]

    changes_this_week = db.query(MonitorChange).filter(
        MonitorChange.site_id.in_(site_ids),
        MonitorChange.detected_at >= week_ago,
    ).count()

    alerts_this_week = db.query(MonitorChange).filter(
        MonitorChange.site_id.in_(site_ids),
        MonitorChange.detected_at >= week_ago,
        MonitorChange.alert_sent == True,
    ).count()

    avg_score_row = db.query(func.avg(MonitorChange.change_score)).filter(
        MonitorChange.site_id.in_(site_ids),
        MonitorChange.detected_at >= week_ago,
    ).scalar()

    use_case_breakdown = {}
    for site in sites:
        use_case_breakdown[site.use_case] = use_case_breakdown.get(site.use_case, 0) + 1

    return StatsOut(
        total_sites=len(sites),
        active_sites=sum(1 for s in sites if s.active),
        changes_this_week=changes_this_week,
        alerts_sent_this_week=alerts_this_week,
        avg_change_score=round(avg_score_row or 0.0, 2),
        use_case_breakdown=use_case_breakdown,
    )


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------

@router.post("/sites/{site_id}/trigger")
def trigger_check(
    site_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site = _get_site_or_404(site_id, user.id, db)

    def _run():
        # Need a new DB session in the background task
        from db.base import SessionLocal as SL
        bg_db = SL()
        try:
            bg_site = bg_db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
            result = run_monitor_for_site(bg_site, bg_db)
            if result.get("change_detected"):
                _broadcast(user.id, {
                    "type": "change_detected",
                    "site_id": site_id,
                    "change_score": result["change_score"],
                    "alert_sent": result["alert_sent"],
                    "run_id": result.get("run_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                })
        finally:
            bg_db.close()

    background_tasks.add_task(_run)
    return {"status": "triggered", "site_id": site_id}


# ---------------------------------------------------------------------------
# SSE real-time stream
# ---------------------------------------------------------------------------

@router.get("/stream")
async def sse_stream(token: Optional[str] = None):
    """
    SSE endpoint — accepts token as a query param since EventSource can't set headers.
    Connect with: new EventSource(`/api/monitor/stream?token=${jwt}`)
    """
    from db.base import SessionLocal as SL
    from api.auth.service import decode_token as _decode
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    payload = _decode(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = SL()
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    uid = user.id
    _sse_subscribers.setdefault(uid, []).append(queue)

    async def event_generator():
        try:
            # Send a heartbeat immediately so the connection is confirmed
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"  # keep-alive comment
        finally:
            _sse_subscribers[uid].remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Screenshot & Visual Diff endpoints
# ---------------------------------------------------------------------------

@router.get("/sites/{site_id}/screenshots/{snapshot_id}")
def get_screenshot(
    site_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the raw screenshot PNG for a snapshot."""
    site = _get_site_or_404(site_id, user.id, db)
    snapshot = db.query(MonitorSnapshot).filter(
        MonitorSnapshot.id == snapshot_id,
        MonitorSnapshot.site_id == site_id,
    ).first()
    if not snapshot or not snapshot.screenshot_path:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    from core.visual.storage import FileSystemScreenshotStorage
    storage = FileSystemScreenshotStorage(".")
    data = storage.load(snapshot.screenshot_path)
    if data is None:
        raise HTTPException(status_code=404, detail="Screenshot file missing")
    return StreamingResponse(iter([data]), media_type="image/png")


@router.get("/changes/{change_id}/visual-diff")
def get_visual_diff(
    change_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the visual diff overlay PNG for a change."""
    change = db.query(MonitorChange).filter(MonitorChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    # Ownership check via site
    site = db.query(MonitorSite).filter(
        MonitorSite.id == change.site_id,
        MonitorSite.user_id == user.id,
    ).first()
    if not site:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not change.visual_diff_path:
        raise HTTPException(status_code=404, detail="Visual diff not found")

    from core.visual.storage import FileSystemScreenshotStorage
    storage = FileSystemScreenshotStorage(".")
    data = storage.load(change.visual_diff_path)
    if data is None:
        raise HTTPException(status_code=404, detail="Visual diff file missing")
    return StreamingResponse(iter([data]), media_type="image/png")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_site_or_404(site_id: int, user_id: int, db: Session) -> MonitorSite:
    site = db.query(MonitorSite).filter(
        MonitorSite.id == site_id,
        MonitorSite.user_id == user_id,
    ).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site
