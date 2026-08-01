# Monitor Agent — Phase 5: Approval Workflow Design

**Date:** 2026-08-01
**Approach:** Dedicated `ApprovalService` + thin API router (Approach 1)
**Target:** Implementation-ready plan for completing the human-in-the-loop approval workflow

---

## 1. Executive summary

Phase 4 delivered real integration handlers, per-site action configuration, and token encryption. However, the approval workflow is half-built: `ActionAgent` routes high-risk or `always`-policy proposals into `approval_requests` (`core/agents/action.py:21-27`), and the orchestrator persists them as `ApprovalRequest` rows (`core/orchestrator.py:183-196`), but nothing ever resolves them. There is no way for a human to list, approve, or reject a pending action, no execution after approval, no pending notification, and no expiry.

Phase 5 completes this workflow so approvals function end-to-end:

- A new `ApprovalService` (`core/approvals/service.py`) owns the approval state machine: lazy expiry, approve (executes the stored action through its real handler), reject.
- A new `ApprovalNotifier` (`core/approvals/notifier.py`) sends email + Slack notifications when pending requests are created, reusing `GmailNotifier` and the existing `SlackActionHandler`.
- A new API router (`api/routers/approvals.py`) exposes `GET /api/approvals` and `POST /api/approvals/{id}/approve|reject`.
- `ApprovalRequest` gains `resolved_by`, `output`, and `error_message` columns; `config/settings.py` gains `APPROVAL_TTL_HOURS`.

### Decisions made during brainstorming

| Decision | Choice |
|---|---|
| Approve outcome | Re-execute the stored action payload through its handler |
| Authorization | Site owner or admin can approve/reject; owner sees own, admin sees all |
| Pending notification | Email + Slack, using existing credentials |
| Expiry | Auto-expire after configurable TTL (default 24h), lazily applied |

---

## 2. Current state & problem

### 2.1 What exists today

- `ApprovalRequest` model (`db/models.py:172-185`): `run_id`, `site_id`, `change_id`, `action_type`, `risk_score`, `payload`, `status` (default `pending`), `user_id` (site owner), `created_at`, `resolved_at`.
- `ActionAgent.run` (`core/agents/action.py:20-27`) splits proposals: those requiring approval go into `approval_requests`; others execute immediately.
- `_requires_approval` (`core/agents/action.py:47-52`): `approval_policy == "always"` → always; `approval_policy == "high_risk"` and `risk_score >= 0.7` → yes; else no.
- `MonitoringOrchestrator._save_approval_requests` (`core/orchestrator.py:183-196`) persists the requests.
- Handlers decrypt tokens just-in-time via `resolve_token(site_id, token)` (Phase 4), so a stored payload containing encrypted tokens works when executed later.

### 2.2 What is missing

- No API to list/approve/reject pending requests.
- No execution after approval.
- No notification when a request becomes pending.
- No expiry of stale pending requests.

---

## 3. Architecture

### 3.1 Component overview

```
                    +---------------------+
  orchestration --> | ApprovalNotifier    |  (email + Slack digest on create)
                    +---------------------+
                              |
                    +---------------------+
  API router -----> | ApprovalService     |  (list / approve / reject / lazy-expire)
                    |   + registry        |  (re-executes handler on approve)
                    +---------------------+
                              |
                    +---------------------+
                    | ActionHandler       |  (six real handlers from Phase 4)
                    +---------------------+
```

### 3.2 New components

**`core/approvals/__init__.py`** — empty package init.

**`core/approvals/service.py`** — `ApprovalService`:

- `__init__(self, db: Session, registry: Optional[ActionHandlerRegistry] = None)` — uses `build_default_registry()` when none is passed.
- `_expire_stale()` — marks any `status == "pending"` request with `created_at < now - APPROVAL_TTL_HOURS` as `expired`. Runs lazily before list/approve/reject.
- `list(actor_user, status: Optional[str] = None) -> list[ApprovalRequest]` — applies lazy expiry, then queries scoped to the actor: admins see all requests; non-admins see only requests for their own sites.
- `approve(approval_id, actor_user) -> ActionResult` — verify pending (else conflict), rebuild `ProposedAction` from stored `payload`/`action_type`/`risk_score`, look up handler, call `handler.execute(...)`, persist `status="approved"`, `resolved_at`, `resolved_by`, and `output` (success) or `error_message` (failure). Returns the handler's `ActionResult`.
- `reject(approval_id, actor_user) -> None` — verify pending, set `status="rejected"`, `resolved_at`, `resolved_by`.

**`core/actions/registry.py`** — add `build_default_registry() -> ActionHandlerRegistry` that registers the six handlers (email, slack, notion, github, n8n, webhook). Refactor `core/orchestrator.py` to use it in `__init__`, and `ApprovalService` uses it too.

**`core/approvals/notifier.py`** — `ApprovalNotifier`:

- `notify_pending(site, requests)` — sends one email digest via `GmailNotifier` (to `GMAIL_RECIPIENT_EMAIL`) when configured, and one Slack message via `SlackActionHandler.execute` using the site's `slack_webhook` (resolved via `resolve_token`) when configured. Each channel wrapped in try/except that logs and continues. Never raises.

**`api/routers/approvals.py`** — `APIRouter(prefix="/api/approvals", tags=["approvals"])`:

- `GET /api/approvals` — list. Auth: any authenticated user sees requests for their own sites; admins see all. Optional `?status=` filter.
- `POST /api/approvals/{approval_id}/approve` — auth: site owner or admin. 404 unknown, 403 unauthorized, 409 already-resolved. Returns execution result.
- `POST /api/approvals/{approval_id}/reject` — auth: same. 404/403/409. Returns the updated request summary.

**`db/models.py`** — extend `ApprovalRequest`:

- `resolved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)`
- `output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)`
- `error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)`

**`config/settings.py`** — add `APPROVAL_TTL_HOURS = int(os.getenv("APPROVAL_TTL_HOURS", "24"))`.

**`api/main.py`** — include `approvals_router`.

### 3.3 Security

- Response shapes never include the raw `payload` dict (it may contain encrypted-or-plaintext tokens). The list endpoint exposes only non-secret fields: `id`, `action_type`, `risk_score`, `description`, `status`, `created_at`, `resolved_at`.
- The approve endpoint executes the stored payload as-is (Phase 4 handlers already `resolve_token`-decrypt; a plaintext payload from a legacy row also works via passthrough).
- Authorization enforced in the router via `get_current_user` + ownership checks (site owner or admin).
- Error messages never contain secrets (established Phase 4 convention: generic messages, no `str(exc)`).

---

## 4. Lifecycle

```
create (orchestrator) → pending → approved → (execute handler) → done
                          │        → rejected
                          └→ expired (lazy, after TTL)
```

### 4.1 Create

Unchanged from today: `ActionAgent.run` routes proposals to `approval_requests`; orchestrator persists them. **New:** orchestrator calls `ApprovalNotifier.notify_pending(site, requests)` after persisting (wrapped so a notification failure never breaks the run).

### 4.2 List

`_expire_stale()` runs first so stale requests surface as `expired`. Query is scoped to the actor (owner's sites, or all for admins).

### 4.3 Approve

1. Auth check (owner/admin) → 403.
2. Pending check + lazy-expire → 409 if already resolved/expired.
3. Rebuild `ProposedAction` from stored fields.
4. Unknown handler → 409 (`handler not registered`).
5. `handler.execute(proposed)` — returns `ActionResult` (never raises).
6. Persist `approved` + `resolved_at` + `resolved_by` + `output`/`error_message`.
7. Respond with execution result.

### 4.4 Reject

Same auth + pending checks; set `rejected` + `resolved_at` + `resolved_by`. No execution.

### 4.5 Expiry

Lazy: `_expire_stale()` marks pending requests older than TTL as `expired`. Approving an expired request → 409.

---

## 5. Testing

### 5.1 `tests/core/test_approvals_service.py`

- approve executes the handler and records `approved`/`resolved_at`/`output` (inject a stub registry; assert `execute` called with rebuilt `ProposedAction`).
- approve on unknown handler returns a failure result (no crash).
- reject records `rejected` + `resolved_by`, no execution.
- lazy expiry: seed stale pending request; list/approve marks it `expired`; approve of expired → conflict.
- handler failure propagates to `error_message`; request still marked `approved`.

### 5.2 `tests/core/test_approvals_notifier.py`

- email digest sent via `GmailNotifier` when recipient configured (mock `send_notification`).
- Slack message posted via `SlackActionHandler` using site `slack_webhook` (mock `requests.post`; assert decrypted URL).
- skips channel when no destination configured.
- never raises when a channel fails (log-and-continue).

### 5.3 `tests/api/test_approvals.py`

Use the same `TestClient` + in-memory SQLite fixture as `tests/api/test_integrations.py` (StaticPool, override `get_db`, create `User` + `MonitorSite`).

- GET list: owner sees own pending; empty when none.
- POST approve: owner can approve; response contains execution result.
- POST approve/reject: non-owner → 403; admin can approve others'; unknown id → 404; already-resolved → 409.
- GET/approve without auth → 401.
- masked response: payload secrets never returned.

### 5.4 `tests/db/test_models.py`

- new columns default correctly.

### 5.5 Existing-suite impact

- `tests/core/test_orchestrator.py` — verify the new notifier call in `_save_approval_requests` does not break existing tests (mock notifier if needed). No real network calls in tests.
- Full suite must pass; `uvicorn` boots; `/health` OK; smoke test covers list→approve→execute with a mocked destination.

---

## 6. Acceptance criteria

1. Pending requests are listed via `GET /api/approvals` with masked payloads (no secrets).
2. Approving a pending request executes the real handler with the stored payload and records the result.
3. Rejecting a pending request marks it rejected without executing.
4. Site owner and admins can act; others get 403; unknown ids 404; already-resolved 409.
5. Pending requests older than `APPROVAL_TTL_HOURS` auto-expire (lazily) and cannot be approved.
6. Creating a pending request sends an email and/or Slack notification using existing credentials; notification failures never break the run.
7. Full test suite passes (≥ current 173 baseline).

---

## 7. Out of scope (YAGNI)

- Manual execution after approval (only auto-execution via handler).
- A background sweeper for expiry (lazy is sufficient at this scale).
- Per-site approval notification destinations (existing global/site credentials only).
- Approval via Slack/email reply (API only).
- `resolved_by` user detail expansion beyond a user id.

---

## 8. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Re-execution fails (rate limit, network) | Action never delivered | Handler returns failure `ActionResult`; recorded in `error_message`; request marked approved so user sees the failure |
| Payload contains stale tokens | Execution fails auth | Handlers `resolve_token` just-in-time; re-encrypted rows still decrypt with the site key |
| Notifications spam on every run | Noise | Digest-style single email/Slack per creation batch |
| Existing tests break from notifier call | CI red | Notifier wrapped in try/except; tests mock or tolerate |

---

## 9. Related documents

- `docs/superpowers/specs/2026-07-18-monitor-agent-next-phases-design.md` — phase roadmap; §6 defined Phase 4, this spec continues the workflow work
- `docs/superpowers/plans/2026-08-01-phase-4-integrations.md` — Phase 4 implementation plan (handlers, encryption, API)
- `core/agents/action.py` — approval gating
- `core/orchestrator.py` — run pipeline + persistence
- `db/models.py` — `ApprovalRequest`
