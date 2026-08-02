# Monitor Agent — Next Phases Design

**Date:** 2026-07-18
**Approach:** Sequential, foundation-first (A)
**Target:** Implementation-ready plan for all four deferred phases

---

## 1. Executive summary

The agentic core of Monitor Agent is now in place: the scout → analyst → reporter → action pipeline is wired into `core/orchestrator.py`, the DB-backed scheduler logs `run_id`, and the dashboard consumes the API. The following four work streams are deferred and should be executed in the order below.

| Phase | Goal | Depends on | Effort estimate |
|---|---|---|---|
| 0 | Harden the core pipeline | Current agentic core | 2–3 sprints |
| 2 | Visual diff | Phase 0 (stable snapshot/change model) | 2 sprints |
| 3 | MCP server | Phase 0 (stable action payload) + existing action handler stubs | 2 sprints |
| 4 | Real integrations | Phase 0 (stable action payload) + Phase 3 (handler registry exposed) | 3 sprints |

> Note: Phase 1 is reserved for the already-completed foundation. The numbering above matches the original deferred table (Phase 2 → visual, Phase 3 → MCP, Phase 4 → integrations).

**Why this order:**
1. Entity correlation in Phase 0 changes the shape of `ScoutEvent` and `AnalysisEvent`, which reporter summaries and action recommendations consume. Stabilizing this first prevents cascading rework.
2. Visual diff builds on the same snapshot/change records and adds file storage; it should not be started until the data model is stable.
3. Real integrations need a stable action payload and per-site configuration, both defined in Phase 0 and Phase 4.
4. The MCP server exposes whatever handlers exist in the registry; it can be built once the action handler interface is stable. Phase 3 uses the existing stubs to validate the protocol layer before Phase 4 replaces them with real integrations.

---

## 2. Cross-cutting decisions

### 2.1 Data-model additions

The following columns are added across all phases:

| Table | Column | Type | Default | Phase |
|---|---|---|---|---|
| `MonitorSite` | `screenshot_enabled` | `Boolean` | `false` | 2 |
| `MonitorSite` | `actions_enabled` | `JSON` | `[]` | 4 |
| `MonitorSite` | `integration_config` | `JSON` | `{}` | 4 |
| `MonitorSnapshot` | `screenshot_path` | `String(2048)` | already exists | 2 |
| `MonitorChange` | `visual_diff_path` | `String(2048)` | already exists | 2 |
| `MonitorChange` | `vision_description` | `Text` | already exists | 2 |

All integration tokens stored on `MonitorSite` (`slack_webhook`, `notion_token`, `github_token`, `n8n_webhook_url`) must be encrypted at rest using `core/security/encryption.py` before Phase 4 is considered complete.

### 2.2 Event payload changes

`ScoutEvent` carries extracted entities; `AnalysisEvent` carries correlated entities:

```python
class ScoutEvent(AgentEvent):
    ...
    entities: list[Entity] = Field(default_factory=list)

class AnalysisEvent(AgentEvent):
    ...
    correlated_entities: list[CorrelatedEntity] = Field(default_factory=list)

class Entity(BaseModel):
    entity_id: str
    name: str
    value: str
    unit: Optional[str] = None
    context: Optional[str] = None

class CorrelatedEntity(BaseModel):
    entity_id: str
    name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    unit: Optional[str] = None
    changed: bool = False
    status: str = "unchanged"  # unchanged | changed | added | removed
```

`AnalysisEvent` keeps `semantic_diff_summary`, `change_type`, `severity`, and `change_score` but the values are now derived from `correlated_entities` when applicable.

### 2.3 Testing policy

- All new modules must have unit tests with mocks for external dependencies (LLM, HTTP, browser, file system).
- API tests are added in `tests/api/` for new endpoints.
- No real network calls or real browsers in CI.
- The existing test suite must remain at ≥46 passing and should reach ~70–80 passing by the end of Phase 4.

### 2.4 Configuration & secrets

- `screenshot_enabled` is per-site, default false, so LLM-only checks remain cheap.
- Integration tokens are per-site and encrypted at rest; the encryption key is `SECRET_KEY` from `config/.env`.
- `docker-compose.yml` documents optional environment variables for integrations but does not require them to start the stack.

---

## 3. Phase 0 — Harden the core pipeline

### 3.1 Problem

`ScoutAgent` extracts entities from the current snapshot but they never include `old_value`. `AnalystAgent._classify_change` reads `entity.get("old_value")`, so price-drop/rise classification never triggers correctly.

### 3.2 Goal

Correlate entities between the previous and current snapshots so the analyst can produce accurate `old_value` / `new_value` pairs and meaningful `change_type` / `severity` values.

### 3.3 Implementation

#### 3.3.1 New module: `core/entities/`

- `core/entities/extractor.py`
  - `extract_entities(markdown: str, llm_router: LLMRouter) -> list[Entity]`
  - Normalizes LLM output to a stable shape: `{entity_id, name, value, unit, context}`.
  - `entity_id` is derived deterministically from `name` + `context` (e.g., `slugify(f"{context}::{name}")`) so it survives content edits. If `context` is absent, `entity_id` is `slugify(name)`.
  - Falls back to empty list on LLM failure; never raises.

- `core/entities/correlator.py`
  - `correlate_entities(old: list[Entity], new: list[Entity]) -> list[CorrelatedEntity]`
  - Matches by `entity_id`.
  - Emits rows for unchanged, changed, added, and removed entities.
  - Handles renames via fuzzy string matching on `name` (optional, threshold 0.8 using `difflib.SequenceMatcher` or `rapidfuzz` if added as a dependency).

- `core/entities/models.py`
  - Pydantic models for `Entity` and `CorrelatedEntity`.

#### 3.3.2 Update `ScoutAgent`

- Replace inline `_extract_entities` with the new `extract_entities` utility.
- Store the extracted (not correlated) entities in `MonitorSnapshot.extracted_entities`.
- Ensure `content_hash` is computed only on the markdown content, not the entities.

#### 3.3.3 Update `AnalystAgent`

- Load `previous_snapshot.extracted_entities`.
- Call `correlate_entities` and attach the result to the returned `AnalysisEvent`.
- Use correlated entities in `_classify_change`:
  - `price_drop` / `price_rise` when a price entity changed.
  - `new_product` when an entity was added and no price entity changed.
  - `content_update` otherwise.
- Use correlated entities in `_severity`:
  - Price changes: `high` if change_score > 1.0, else `medium`.
  - Large content changes: `critical` if change_score > 5.0, `medium` if > 1.0, else `low`.

#### 3.3.4 Update `Orchestrator`

- Pass `previous_snapshot` to `AnalystAgent.run` (already done).
- Ensure `AnalysisEvent` payload is stored in `AuditLog.reasoning`.

#### 3.3.5 Tests

- `tests/core/test_entities_extractor.py`
- `tests/core/test_entities_correlator.py`
- `tests/core/test_scout_agent.py` — add entity persistence test
- `tests/core/test_analyst_agent.py` — add price-drop/rise/new-product classification tests
- `tests/core/test_orchestrator.py` — add:
  - first-run behavior
  - identical content → no change
  - scrape failure → error snapshot, `success=False`
  - LLM extraction failure → graceful fallback

### 3.4 Acceptance criteria

- `AnalystAgent` correctly classifies a price drop when a price entity decreases.
- `AnalystAgent` correctly classifies a new product when an entity is added.
- A scrape failure creates an error snapshot, rolls back no partial data, and returns `success=False`.
- Test suite reaches ≥55 passing.

---

## 4. Phase 2 — Visual diff

### 4.1 Goal

Capture a full-page screenshot during each check, compare it to the previous screenshot, and store the visual diff image so the dashboard can show side-by-side visual changes.

### 4.2 Implementation

#### 4.2.1 New module: `core/visual/`

- `core/visual/screenshot.py`
  - Protocol `ScreenshotProvider` with `capture(url: str) -> bytes`.
  - `PlaywrightScreenshotProvider`:
    - Launches headless Chromium.
    - Viewport 1280×720, full-page scroll.
    - Saves to a temporary PNG and returns bytes.
  - `StaticScreenshotProvider` for tests: returns a deterministic PNG from a fixture.

- `core/visual/diff.py`
  - `compare_images(old_bytes: bytes, new_bytes: bytes) -> VisualDiffResult`
  - Uses Pillow to compute pixel diff and highlight changed regions.
  - Returns `changed: bool`, `diff_score: float`, `diff_bytes: Optional[bytes]`.

- `core/visual/models.py`
  - `VisualDiffResult` Pydantic model.

#### 4.2.2 Data storage

- Screenshot path: `data/screenshots/{site_id}/{snapshot_id}.png`
- Diff overlay path: `data/screenshots/{site_id}/diffs/{change_id}.png`
- The directory is created on demand; missing parent directories are not an error.

#### 4.2.3 Wiring

- `ScoutAgent` receives a `screenshot_provider: Optional[ScreenshotProvider]` parameter.
- If `site.screenshot_enabled` is true and the provider is present, capture a screenshot and store it in `MonitorSnapshot.screenshot_path`.
- If the provider is absent or capture fails, log a warning and continue; the check is not marked as failed.
- `AnalystAgent`:
  - If both old and new snapshots have screenshots, call `compare_images`.
  - If `VisualDiffResult.changed`, set `visual_diff_path` and a `vision_description` (e.g., "Screenshot changed in {n} regions").

#### 4.2.4 API endpoints

- `GET /api/monitor/sites/{id}/screenshots/{snapshot_id}`
  - Returns the PNG file with `image/png` content type.
  - 404 if the screenshot does not exist.
- `GET /api/monitor/changes/{id}/visual-diff`
  - Returns the diff overlay PNG.
  - 404 if no visual diff was generated.

#### 4.2.5 Frontend (optional, deferred)

- The dashboard already has a diff viewer. A future frontend task can add a visual diff tab next to the text diff.
- This phase only guarantees the API and stored files.

#### 4.2.6 Tests

- `tests/core/test_screenshot.py`
- `tests/core/test_visual_diff.py`
- `tests/core/test_scout_agent.py` — add screenshot-enabled test
- `tests/api/test_screenshots.py` — 2–3 API tests

### 4.3 Dependencies

Add to `requirements-api.txt`:

```text
playwright>=1.45.0
Pillow>=10.0.0
```

Document in README:

```bash
playwright install chromium
```

### 4.4 Acceptance criteria

- A site with `screenshot_enabled=true` stores a screenshot on every successful check.
- Two identical screenshots produce `VisualDiffResult.changed=false`.
- Two different screenshots produce a diff overlay file and a non-empty `visual_diff_path`.
- Missing screenshot file returns 404 from the API.
- Test suite reaches ≥70 passing.

---

## 5. Phase 3 — MCP server

### 5.1 Goal

Expose the existing action handler registry to external agents through a separate FastAPI service implementing the Model Context Protocol (MCP).

### 5.2 Implementation

#### 5.2.1 New package: `mcp/`

- `mcp/main.py`
  - FastAPI app with lifespan, CORS, and health endpoint `/health`.
  - Port `8001` by default.

- `mcp/server.py`
  - `MCPServer` class implementing the transport-agnostic MCP server:
    - `list_tools() -> list[Tool]`
    - `call_tool(name: str, arguments: dict) -> ToolResult`
  - Uses `core/actions/registry.py` to enumerate handlers.

- `mcp/tools.py`
  - Maps each `ActionHandler` to an MCP `Tool` definition:
    - `name`: handler name
    - `description`: handler description
    - `inputSchema`: JSON schema from `handler.input_schema()`
    - `outputSchema`: JSON schema from `handler.output_schema()`

- `mcp/auth.py`
  - API-key middleware. Reads `MCP_API_KEY` from environment. Rejects requests without a valid `X-API-Key` header.

- `mcp/transport.py`
  - HTTP+SSE transport endpoints:
    - `POST /mcp/initialize`
    - `POST /mcp/message`
    - `GET /mcp/sse`
  - Keeps the MCP layer separate from internal FastAPI routes.

#### 5.2.2 Reuse

- Extend `core/actions/base.py` `ActionHandler` with `input_schema() -> dict` and `output_schema() -> dict` methods so the MCP server can advertise JSON schemas. Default implementation derives schemas from `ProposedAction` and `ActionResult` dataclasses.
- `core/actions/registry.py` and `core/actions/base.py` are the single source of truth for action handlers.
- Phase 3 registers placeholder handlers for `notion`, `github`, `n8n`, and `webhook` (returning `ActionResult(success=False, message="Not implemented")`) so the MCP server can list the full tool set before Phase 4 replaces them.
- Adding a new handler in Phase 4 automatically makes it available in the MCP server.

#### 5.2.3 Docker

- Add `mcp` service to `docker-compose.yml` using a shared image or a new `Dockerfile.mcp`.
- Expose port `8001`.
- Document `MCP_API_KEY` in `config/.env.example`.

#### 5.2.4 Tests

- `tests/mcp/test_mcp_server.py`
  - `list_tools` returns all registered handlers.
  - `call_tool` delegates to the correct handler.
  - Invalid API key is rejected.
- `tests/mcp/test_mcp_tools.py`
  - Schema generation for each handler.

### 5.3 Dependencies

Add to `requirements-api.txt` (or a new `requirements-mcp.txt`):

```text
mcp>=1.0.0
```

If the official package is unavailable, implement the minimal SSE transport manually in `mcp/transport.py`.

### 5.4 Acceptance criteria

- `GET /mcp/sse` streams valid MCP session events.
- `list_tools` returns at least email, slack, notion, github, n8n, webhook entries.
- `call_tool` invokes a handler and returns a JSON result.
- Unauthorized requests return 403.
- Test suite reaches ≥80 passing.

---

## 6. Phase 4 — Real integrations

### 6.1 Goal

Replace the email and Slack stubs with real integrations, and implement Notion, GitHub, n8n, and generic webhook action handlers behind the existing `core/actions/base.py` interface.

### 6.2 Implementation

#### 6.2.1 Per-site action configuration

- Add `actions_enabled` (JSON list of handler names) and `integration_config` (JSON dict of handler-specific settings) to `MonitorSite`.
- Default `actions_enabled` is `[]` so no actions run unless explicitly configured.
- `ActionAgent.run` reads `site.actions_enabled` and only invokes handlers in that list.

#### 6.2.2 Token encryption

- Encrypt `slack_webhook`, `notion_token`, `github_token`, `n8n_webhook_url` before persistence.
- Decrypt on read inside the respective handlers.
- Mask tokens in the API (show last 4 characters only).

#### 6.2.3 Handler implementations

| Handler | File | Behavior |
|---|---|---|
| Email | `core/actions/handlers/email.py` | Use existing `gmail_notifier` or configurable SMTP. Send HTML report body. |
| Slack | `core/actions/handlers/slack.py` | POST to `slack_webhook` with a message block containing summary, change score, and links. |
| Notion | `core/actions/handlers/notion.py` | Create a page in a configured database using `notion_token`. Include summary and link. |
| GitHub | `core/actions/handlers/github.py` | Create an issue in a configured repo using `github_token`. Optionally create a PR if `create_pr=true`. |
| n8n | `core/actions/handlers/n8n.py` | POST full change payload to `n8n_webhook_url`. |
| Webhook | `core/actions/handlers/webhook.py` | POST to a user-configured URL. Optionally sign with HMAC-SHA256 using a shared secret. |

Each handler returns `{"success": bool, "message": str, "external_id": Optional[str]}`.

#### 6.2.4 API endpoints

- `PUT /api/monitor/sites/{id}/integrations`
  - Accepts encrypted tokens and `actions_enabled` list.
  - Encrypts tokens before saving.
- `GET /api/monitor/sites/{id}/integrations`
  - Returns masked tokens and enabled actions.

#### 6.2.5 Tests

- `tests/core/actions/test_email_handler.py`
- `tests/core/actions/test_slack_handler.py`
- `tests/core/actions/test_notion_handler.py`
- `tests/core/actions/test_github_handler.py`
- `tests/core/actions/test_n8n_handler.py`
- `tests/core/actions/test_webhook_handler.py`
- `tests/api/test_integrations.py`

All external HTTP calls are mocked with `responses` or `unittest.mock`.

### 6.3 Dependencies

Add to `requirements-api.txt`:

```text
requests>=2.32.0
PyGithub>=2.3.0  # optional, or use httpx directly
```

### 6.4 Acceptance criteria

- Each handler can be enabled independently per site.
- Tokens are encrypted in the database and never returned in full via the API.
- A mocked Slack webhook receives the expected payload when a change occurs.
- A mocked Notion API creates a page when configured.
- A mocked GitHub API creates an issue when configured.
- A mocked n8n webhook receives the full change payload.
- Test suite reaches ≥90 passing.

---

## 7. Rollout plan

| Sprint | Phase | Deliverables |
|---|---|---|
| 1 | 0 | `core/entities/`, unit tests, entity correlation in analyst |
| 2 | 0 | Orchestrator edge-case tests, pipeline hardened |
| 3 | 2 | Screenshot provider, visual diff module, storage |
| 4 | 2 | API screenshot endpoints, API tests |
| 5 | 3 | MCP package, `list_tools`/`call_tool`, auth middleware |
| 6 | 3 | Docker service, MCP smoke tests |
| 7 | 4 | Per-site action config, token encryption, email/Slack real handlers |
| 8 | 4 | Notion/GitHub/n8n/webhook handlers + API endpoints |
| 9 | 4 | Integration tests, docs, final verification |

### 7.1 Verification gates

After each phase:

1. Run `python -m pytest tests/ -v` and confirm the expected passing count.
2. Run `python -m uvicorn api.main:app` and `curl /health` returns `{"status":"ok"}`.
3. Run `python src/scheduler_db.py` and confirm scheduled checks still log `run_id`.
4. For Phase 2: capture a screenshot and verify the file exists.
5. For Phase 3: `curl` the MCP `list_tools` endpoint and see expected handlers.
6. For Phase 4: trigger a mock-enabled handler and verify the HTTP request was sent.

---

## 8. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Playwright/Chromium install friction | Phase 2 tests fail in CI | Use `StaticScreenshotProvider` as default in tests; only run Playwright tests when `SCREENSHOT_PROVIDER=playwright` is set. |
| LLM entity extraction is flaky | Phase 0 classification is unreliable | Make extraction best-effort; always fall back to content-based classification. |
| MCP protocol changes | Phase 3 code breaks | Pin `mcp` package version; implement minimal transport manually if package is unstable. |
| Token encryption key rotation | Phase 4 tokens become unreadable | Document key rotation process: decrypt/re-encrypt on admin command. |
| External API rate limits | Phase 4 actions fail | Add per-handler retry/backoff and log failures without blocking the pipeline. |

---

## 9. Open questions

1. Should visual diffs be enabled globally or per-site? (Design assumes per-site `screenshot_enabled`.)
2. Should the MCP server share the API database or be stateless? (Design assumes stateless; it reads handler metadata only.)
3. Should GitHub handler create PRs or only issues? (Design supports optional PR creation via `create_pr=true`.)
4. Which integrations are highest priority if Phase 4 needs to be split further? (Default order: email, Slack, webhook, n8n, Notion, GitHub.)

---

## 10. Related documents

- `README.md` — quickstart and environment variables
- `docs/TECHNICAL_DOC.md` — agentic architecture
- `docs/SCHEDULING.md` — scheduler behavior
- `core/orchestrator.py` — current orchestration
- `db/models.py` — current data model
- `core/actions/base.py` — action handler interface
