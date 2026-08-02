# Phase 5 — Approval Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the human-in-the-loop approval workflow: an `ApprovalService` owns the approval state machine (lazy expiry, approve → execute, reject), an `ApprovalNotifier` sends email + Slack notifications when requests become pending, and a new `/api/approvals` router lets users list/approve/reject.

**Architecture (Approach 1 — dedicated service + thin router):** `ApprovalService` (`core/approvals/service.py`) handles list/approve/reject and reuses an `ActionHandlerRegistry` to re-execute stored payloads on approval. `ApprovalNotifier` (`core/approvals/notifier.py`) digests pending requests to email (`GmailNotifier`) and Slack (`SlackActionHandler.execute`) using existing credentials. A shared `build_default_registry()` in `core/actions/registry.py` registers the six handlers and is reused by both the orchestrator and the service. `ApprovalRequest` gains `resolved_by`, `output`, `error_message`; `config/settings.py` gains `APPROVAL_TTL_HOURS` (default 24). Responses never include the raw `payload` (it may contain tokens).

**Precondition:** Phase 4 must be merged (real handlers, `resolve_token`, integrations router). This plan runs on the branch containing Phase 4.

**Tech Stack:** Python 3.9, SQLAlchemy 2.0, FastAPI, `requests`, `pytest`, `responses`/`unittest.mock` for network mocking.

**Design doc:** `docs/superpowers/specs/2026-08-01-phase-5-approval-workflow-design.md`.

---

## File Structure

**New files:**
- `core/approvals/__init__.py` — empty package init
- `core/approvals/service.py` — `ApprovalService`
- `core/approvals/notifier.py` — `ApprovalNotifier`
- `api/routers/approvals.py` — `GET /api/approvals`, `POST /api/approvals/{id}/approve|reject`
- `tests/core/test_approvals_service.py`
- `tests/core/test_approvals_notifier.py`
- `tests/api/test_approvals.py`

**Modified files:**
- `core/actions/registry.py` — add `build_default_registry()`
- `core/orchestrator.py` — use `build_default_registry()`, call notifier in `_save_approval_requests`
- `db/models.py` — extend `ApprovalRequest`
- `config/settings.py` — add `APPROVAL_TTL_HOURS`
- `api/main.py` — include approvals router
- `tests/db/test_models.py` — column-default test
- `tests/core/test_orchestrator.py` — tolerate/mock the notifier call

---

### Task 1: Add the new columns to `ApprovalRequest`

**Files:**
- Modify: `db/models.py:174-187`
- Test: `tests/db/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/db/test_models.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/db/test_models.py::test_approval_request_resolution_columns_default -v`
Expected: FAIL — `AttributeError` because columns don't exist.

- [ ] **Step 3: Add the columns**

In `db/models.py`, extend `ApprovalRequest`:

```python
    resolved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

Place them after `resolved_at`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/db/test_models.py::test_approval_request_resolution_columns_default -v`
Expected: PASS.

- [ ] **Step 5: Verify no regression in the models suite**

Run: `python -m pytest tests/db/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `phase5: add resolved_by/output/error_message to ApprovalRequest`

---

### Task 2: Add `APPROVAL_TTL_HOURS` to settings

**Files:**
- Modify: `config/settings.py:70-71`

- [ ] **Step 1: Add the setting**

Near `N8N_WEBHOOK_URL`:

```python
APPROVAL_TTL_HOURS = int(os.getenv('APPROVAL_TTL_HOURS', '24'))
```

- [ ] **Step 2: Verify import works**

Run: `python -c "import config.settings as s; print(s.APPROVAL_TTL_HOURS)"`
Expected: prints `24`.

- [ ] **Step 3: Commit**

Commit message: `phase5: add APPROVAL_TTL_HOURS setting (default 24)`

---

### Task 3: Extract `build_default_registry()` and refactor the orchestrator

**Files:**
- Modify: `core/actions/registry.py`
- Modify: `core/orchestrator.py:12-18,31-36`
- Test: `tests/core/test_action_registry.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_action_registry.py`:

```python
def test_build_default_registry_registers_all_six_handlers():
    from core.actions.registry import build_default_registry
    registry = build_default_registry()
    assert sorted(registry.list()) == ["email", "github", "n8n", "notion", "slack", "webhook"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_action_registry.py::test_build_default_registry_registers_all_six_handlers -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Add `build_default_registry()`**

In `core/actions/registry.py`:

```python
def build_default_registry() -> ActionHandlerRegistry:
    from core.actions.handlers.email import EmailActionHandler
    from core.actions.handlers.slack import SlackActionHandler
    from core.actions.handlers.notion import NotionActionHandler
    from core.actions.handlers.github import GitHubActionHandler
    from core.actions.handlers.n8n import N8NActionHandler
    from core.actions.handlers.webhook import WebhookActionHandler

    registry = ActionHandlerRegistry()
    for handler in (
        EmailActionHandler(),
        SlackActionHandler(),
        NotionActionHandler(),
        GitHubActionHandler(),
        N8NActionHandler(),
        WebhookActionHandler(),
    ):
        registry.register(handler)
    return registry
```

(Local imports avoid a module-cycle risk between handlers and registry.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_action_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Refactor the orchestrator to use it**

In `core/orchestrator.py`:
- Replace the six handler imports (`EmailActionHandler` … `WebhookActionHandler`) and the `ActionHandlerRegistry` import with:

```python
from core.actions.registry import ActionHandlerRegistry, build_default_registry
```

- Replace the `__init__` registration block:

```python
        self.action_registry = build_default_registry()
        self.action_agent = ActionAgent(self.action_registry)
```

- [ ] **Step 6: Verify orchestrator tests still pass**

Run: `python -m pytest tests/core/test_orchestrator.py tests/core/test_action_agent.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

Commit message: `phase5: extract build_default_registry() shared by orchestrator and approval service`

---

### Task 4: Add the `ApprovalService`

**Files:**
- New: `core/approvals/__init__.py`
- New: `core/approvals/service.py`
- New: `tests/core/test_approvals_service.py`

- [ ] **Step 1: Write the failing test file**

Create `tests/core/test_approvals_service.py`:

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from core.actions.base import ActionHandler, ProposedAction, ActionResult
from core.actions.registry import ActionHandlerRegistry
from core.approvals.service import ApprovalService
from db.models import ApprovalRequest, MonitorSite, User


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_approvals_service.py -v`
Expected: FAIL — `ImportError` / `ModuleNotFoundError: core.approvals`.

- [ ] **Step 3: Create `core/approvals/__init__.py`**

Empty file.

- [ ] **Step 4: Implement `core/approvals/service.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/core/test_approvals_service.py -v`
Expected: PASS.

- [ ] **Step 6: Add the remaining service tests**

Append to `tests/core/test_approvals_service.py`:

```python
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
```

Note: if using `MagicMock(spec=Session)` for `db`, the service methods that only touch `req` and `self.registry` work; tests that call `_expire_stale` for real need a real Session — the lazy-expiry behavior is covered in the API test suite where a real in-memory DB is available.

- [ ] **Step 7: Run the full service test file**

Run: `python -m pytest tests/core/test_approvals_service.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

Commit message: `phase5: add ApprovalService (list/approve/reject/lazy-expire)`

---

### Task 5: Add the `ApprovalNotifier`

**Files:**
- New: `core/approvals/notifier.py`
- New: `tests/core/test_approvals_notifier.py`

- [ ] **Step 1: Write the failing test file**

Create `tests/core/test_approvals_notifier.py`:

```python
from unittest.mock import patch, MagicMock

from core.approvals.notifier import ApprovalNotifier
from db.models import MonitorSite


def test_skips_when_no_destinations_configured():
    site = MonitorSite(id=1, user_id=1, instruction="test", slack_webhook="")
    notifier = ApprovalNotifier()
    notifier.notify_pending(site, [])
    assert True  # no exceptions


def test_email_sent_when_recipient_configured():
    site = MonitorSite(id=1, user_id=1, instruction="test")
    notifier = ApprovalNotifier()
    with patch(
        "core.approvals.notifier.GmailNotifier",
        autospec=True,
    ) as MockNotifier:
        instance = MockNotifier.return_value
        with patch("core.approvals.notifier.settings.GMAIL_RECIPIENT_EMAIL", "admin@example.com"):
            notifier.notify_pending(site, [{"action_type": "slack", "risk_score": 0.9}])
    assert instance.send_notification.called
```

Note: `config.settings.GMAIL_RECIPIENT_EMAIL` is read at import time from the env, so the test patches the module attribute directly (`core.approvals.notifier.settings.GMAIL_RECIPIENT_EMAIL`) rather than `os.environ`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_approvals_notifier.py -v`
Expected: FAIL — `ModuleNotFoundError: core.approvals.notifier`.

- [ ] **Step 3: Implement `core/approvals/notifier.py`**

```python
"""
Pending-approval notifications: one email digest + one Slack message per batch.
Each channel fails independently (log-and-continue). Never raises.
"""

import logging
from datetime import datetime

from config import settings
from core.actions.base import ProposedAction
from core.actions.handlers.slack import SlackActionHandler
from src.modules.gmail_notifier import GmailNotifier, ChangeNotification

logger = logging.getLogger(__name__)


class ApprovalNotifier:
    def __init__(self):
        self.slack_handler = SlackActionHandler()

    def notify_pending(self, site, requests) -> None:
        if not requests:
            return
        self._notify_email(site, requests)
        self._notify_slack(site, requests)

    def _notify_email(self, site, requests) -> None:
        try:
            if not settings.GMAIL_RECIPIENT_EMAIL:
                return
            summary = "\n".join(
                f"- {r['action_type']} (risk {r['risk_score']:.2f})" for r in requests
            )
            notification = ChangeNotification(
                url=getattr(site, "url", None) or "",
                instruction="Actions awaiting your approval",
                change_score=0.0,
                threshold=1.0,
                added_lines=0,
                removed_lines=0,
                modified_lines=0,
                diff_summary=f"{len(requests)} action(s) need approval on site {site.id}:\n{summary}",
                timestamp=datetime.now().strftime("%d/%m/%Y à %H:%M:%S"),
                elements_watched=[],
            )
            GmailNotifier().send_notification(notification)
        except Exception:
            logger.exception("approval email notification failed")

    def _notify_slack(self, site, requests) -> None:
        try:
            webhook = getattr(site, "slack_webhook", None) or ""
            if not webhook:
                return
            text = "\n".join(
                f"- {r['action_type']} (risk {r['risk_score']:.2f})" for r in requests
            )
            proposed = ProposedAction(
                type="slack",
                risk_score=0.0,
                payload={
                    "webhook": webhook,
                    "text": f"{len(requests)} action(s) need approval on site {site.id}:\n{text}",
                    "url": getattr(site, "url", None) or "",
                    "change_score": 0.0,
                    "severity": "info",
                    "site_id": site.id,
                },
                description="Pending approvals notification",
            )
            result = self.slack_handler.execute(proposed)
            if not result.success:
                logger.warning("slack approval notification failed: %s", result.message)
        except Exception:
            logger.exception("slack approval notification failed")
```

Implementation note: `GmailNotifier.send_notification` expects a `ChangeNotification`. Reuse the existing call shape from Phase 4's `EmailActionHandler` (which builds a `ChangeNotification`), and build a small local helper to convert requests → `ChangeNotification`. Keep the notifier's public behavior: no exceptions, channel isolation. The `SlackActionHandler.execute` payload keys are `webhook`, `text`, `site_id` (see `core/actions/handlers/slack.py:45-74`); build the `ProposedAction` with those keys rather than a bespoke `MagicProposedAction`.

- [ ] **Step 4: Run the notifier test to verify it passes**

Run: `python -m pytest tests/core/test_approvals_notifier.py -v`
Expected: PASS. If the email call shape differs, adjust the test's assertion to the actual call (e.g., assert `send_notification` received a `ChangeNotification` with the right subject).

- [ ] **Step 5: Add channel-failure test**

Append:

```python
def test_never_raises_when_email_fails():
    site = MonitorSite(id=1, user_id=1, instruction="test")
    notifier = ApprovalNotifier()
    with patch("core.approvals.notifier.GmailNotifier", side_effect=RuntimeError("smtp down")):
        with patch("core.approvals.notifier.settings.GMAIL_RECIPIENT_EMAIL", "admin@example.com"):
            notifier.notify_pending(site, [{"action_type": "slack", "risk_score": 0.9}])
    assert True
```

- [ ] **Step 6: Run the full notifier test file**

Run: `python -m pytest tests/core/test_approvals_notifier.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

Commit message: `phase5: add ApprovalNotifier (email + slack digest, log-and-continue)`

---

### Task 6: Wire the notifier into the orchestrator

**Files:**
- Modify: `core/orchestrator.py:191-204`
- Modify: `tests/core/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_orchestrator.py`:

```python
def test_orchestrator_notifies_on_approval_requests():
    db = MagicMock(spec=Session)
    site = MonitorSite(
        id=1, user_id=1, instruction="test", threshold=1.0, approval_policy="always"
    )
    orch = MonitoringOrchestrator(db)
    with patch.object(orch.approval_notifier, "notify_pending") as mock_notify:
        orch._save_approval_requests(
            "r1",
            site,
            MagicMock(id=1),
            MagicMock(
                approval_requests=[
                    {"type": "slack", "risk_score": 0.4, "payload": {}, "description": "x"}
                ]
            ),
        )
    mock_notify.assert_called_once()
```

Note: the orchestrator must instantiate `self.approval_notifier = ApprovalNotifier()`. The test patches `notify_pending` (a real method on a real notifier) so no network/email is attempted. Because `_save_approval_requests` calls `self.db.commit()`, keep `db` a `MagicMock`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/core/test_orchestrator.py::test_orchestrator_notifies_on_approval_requests -v`
Expected: FAIL — `AttributeError: 'MonitoringOrchestrator' object has no attribute 'approval_notifier'`.

- [ ] **Step 3: Implement the notifier call**

In `core/orchestrator.py`:

- Add import: `from core.approvals.notifier import ApprovalNotifier`
- In `__init__`: `self.approval_notifier = ApprovalNotifier()`
- At the end of `_save_approval_requests`, after `self.db.commit()`:

```python
        try:
            self.approval_notifier.notify_pending(site, event.approval_requests)
        except Exception:
            pass
```

The try/except guards the run: notification failures never break the pipeline.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/core/test_orchestrator.py::test_orchestrator_notifies_on_approval_requests -v`
Expected: PASS.

- [ ] **Step 5: Verify the orchestrator suite still passes**

Run: `python -m pytest tests/core/test_orchestrator.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `phase5: notify on approval requests in orchestrator (non-fatal)`

---

### Task 7: Add the `/api/approvals` router

**Files:**
- New: `api/routers/approvals.py`
- Modify: `api/main.py`
- New: `tests/api/test_approvals.py`

- [ ] **Step 1: Write the failing test file**

Create `tests/api/test_approvals.py` reusing the Phase 4 fixture pattern (in-memory SQLite + StaticPool + override `get_db`):

```python
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
```

Note: the seeded request uses `action_type="slack"` (a real registered handler); approve tests mock `core.actions.handlers.slack.requests.post` so no network is hit. The router builds its `ApprovalService` with `build_default_registry()` per-request (mirrors the orchestrator). For list-scoping tests, extra requests (`r2`, `r3`) are created directly in the DB with an arbitrary `action_type` (`stub`) and are never approved, so no handler registration is needed for them.

- [ ] **Step 2: Run test file to verify it fails**

Run: `python -m pytest tests/api/test_approvals.py -v`
Expected: FAIL — `404`/`ModuleNotFoundError` because router missing.

- [ ] **Step 3: Implement `api/routers/approvals.py`**

```python
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
```

Note on `description`: `ApprovalRequest` has no `description` column (confirmed — `ActionAgent` includes it in the approval dict but the orchestrator does not persist it). The `_masked` helper therefore omits it, matching the spec's masked fields (`id`, `action_type`, `risk_score`, `status`, `created_at`, `resolved_at`).

- [ ] **Step 4: Register the router in `api/main.py`**

```python
from api.routers.approvals import router as approvals_router
...
app.include_router(approvals_router)
```

- [ ] **Step 5: Add approve/reject/403/404/409 API tests**

Add to `tests/api/test_approvals.py` (mocking `requests.post` so approve executes a real `slack` handler without network):

```python
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
    with patch("core.actions.handlers.slack.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        resp = client.post(
            f"/api/approvals/{seeded['request'].id}/approve",
            headers={"Authorization": f"Bearer {seeded['admin_token']}"},
        )
    assert resp.status_code == 200
```

Note: the seeded request's `action_type` is `slack` and its `payload` carries a webhook; the approve tests mock `core.actions.handlers.slack.requests.post` so `SlackActionHandler.execute` never hits the network. Keep any non-approve requests (`r2`, `r3`) as `stub` since they are only used for list-scoping assertions.

- [ ] **Step 6: Run the API test file to verify it passes**

Run: `python -m pytest tests/api/test_approvals.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

Commit message: `phase5: add /api/approvals router (list/approve/reject)`

---

### Task 8: Lazy-expiry API behavior test

**Files:**
- Modify: `tests/api/test_approvals.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/api/test_approvals.py::test_stale_pending_request_auto_expires -v`
Expected: PASS.

- [ ] **Step 3: Commit**

Commit message: `phase5: lazy-expiry coverage for /api/approvals`

---

### Task 9: Full-suite verification & smoke test

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS, ≥ 173 tests (baseline from Phase 4).

- [ ] **Step 2: Confirm server boots and `/health` OK**

Run with a throwaway `SECRET_KEY`:

```
SECRET_KEY=<throwaway> python -m uvicorn api.main:app --port 8000
```

Then `curl -s http://localhost:8000/health` → `{"status": "ok"}` (verify actual shape). Shut the server down.

- [ ] **Step 3: Smoke test the workflow with mocked destinations**

- Start a run that produces an approval request (site with `approval_policy="always"` and `slack` enabled).
- `GET /api/approvals` → request listed, `status: pending`, no `payload` key in response.
- `POST /api/approvals/{id}/approve` (with a stubbed/mocked Slack endpoint or `responses` block) → `success: true`.
- `GET /api/approvals` again → `status: approved`.

- [ ] **Step 4: Update `docs/superpowers/specs/2026-08-01-phase-5-approval-workflow-design.md` if behavior diverged**

Only if implementation revealed a deviation from the spec. Note any differences in the "Implementation notes" section of this plan instead if minor.

- [ ] **Step 5: Commit any remaining changes**

Commit message: `phase5: final verification and cleanup`

---

## Implementation notes / known caveats

- **`GmailNotifier.send_notification`** expects a `ChangeNotification` (see `src/modules/gmail_notifier.py:29-42,251-254`) and returns `bool`. The notifier builds a `ChangeNotification` exactly like Phase 4's `EmailActionHandler.execute` (`core/actions/handlers/email.py:45-60`); do not pass a subject/body string directly.
- **`ApprovalRequest.description`** does not exist in `db/models.py` (confirmed — Phase 4's `ActionAgent` includes `description` in the dict but the orchestrator does not persist it). The `_masked` response omits it; the spec's masked fields are `id`, `action_type`, `risk_score`, `status`, `created_at`, `resolved_at`. If a description is wanted later, add a column — out of scope here.
- **Registry cycle risk:** `build_default_registry()` uses local imports inside the function to avoid importing handlers at module import time of `core/actions/registry.py`.
- **API service construction:** `ApprovalService(db, registry=build_default_registry())` is cheap per-request and mirrors how the orchestrator already builds its registry. If per-request construction feels heavy, module-level `DEFAULT_REGISTRY = build_default_registry()` is acceptable.
- **Network in tests:** never hit real endpoints. Mock `requests.post` (Slack), `GmailNotifier.send_notification` (email), or use `responses`.
- **Legacy rows:** a stored `payload` may be plaintext (pre-Phase-4). Handlers `resolve_token` with a passthrough for non-`gAAAA` values, so plaintext payloads still execute (spec §3.3).
- **`config/settings.py`** uses `os.getenv` with empty defaults; `APPROVAL_TTL_HOURS` follows that pattern.

## Execution log / minor divergences (2026-08-02)

All 9 tasks implemented on branch `feature/phase-5-approval-workflow` (created from `feature/phase-4-integrations`). Full suite: **195 passed** (baseline 173 + 22 new). Smoke test passed: list pending (masked) → approve (mocked Slack) → list approved → double-approve 409; server boots with `/health` OK and `/api/approvals` 401 unauthenticated.

Minor divergences from the plan, all behavior-neutral or small improvements:

- **Notifier email log-and-continue (Task 5):** `GmailNotifier.send_notification` returns `False` (rather than raising) on SMTP failure, so `_notify_email` now does `ok = ...; if not ok: logger.warning(...)` to honor the "log-and-continue" docstring. Added a 4th notifier test (`test_email_failure_returns_false_logs_warning`) via `caplog`.
- **Orchestrator import (Task 3):** dropped the now-unused `ActionHandlerRegistry` import from `core/orchestrator.py` (was only needed for the inline registration the refactor removed). Commit `8deb5f9`.
- **Pruned unused test imports:** `tests/core/test_approvals_service.py` (datetime/timedelta/timezone/MonitorSite/User) and `tests/core/test_approvals_notifier.py` (`MagicMock`). No behavior change.
- **`APPROVAL_TTL_HOURS` not in `config/settings.py` `__all__`:** matches the runtime-env-setting pattern used by other settings; nothing imports it via wildcard, so no functional impact. Could be added when the setting gains its first wildcard consumer.
- **Design spec:** `docs/superpowers/specs/2026-08-01-phase-5-approval-workflow-design.md` was never committed (it only existed untracked in the Phase 4 worktree), so no spec file was updated; divergences are noted here instead.
