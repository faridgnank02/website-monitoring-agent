# Phase 2 — Visual Diff Design

**Date:** 2026-07-19  
**Status:** Approved — ready for implementation planning  
**Depends on:** Phase 0 (stable snapshot/change model)  

---

## 1. Goal

Capture a full-page screenshot during each monitoring check, compare it to the previous screenshot, store a highlighted diff overlay, and expose raw screenshot/diff images through the REST API so the dashboard can render side-by-side visual changes.

---

## 2. Non-goal

- Vision-model-generated natural-language descriptions are out of scope. `MonitorChange.vision_description` is populated with a simple computed string (`"Screenshot changed in {n} regions"`).
- Object storage (S3/MinIO) is out of scope; files live on the local filesystem under `data/screenshots/`.
- Front-end visual diff tab is out of scope; this phase only guarantees the API and stored files.

---

## 3. Architecture

We add a `core/visual/` package with two clean ports: capture (provider) and persistence (storage). Agents stay agnostic of filesystem details, and tests can inject deterministic fakes.

```
core/visual/
  __init__.py          # convenience exports
  models.py            # VisualDiffResult
  screenshot.py        # ScreenshotProvider protocol + implementations
  storage.py           # ScreenshotStorage port + FileSystemScreenshotStorage
  diff.py              # VisualDiffEngine

db/models.py           # + MonitorSite.screenshot_enabled
core/agents/scout.py   # inject provider, capture when enabled
core/agents/analyst.py # inject storage + diff engine, compare screenshots
core/orchestrator.py   # inject provider + storage + diff engine, persist screenshot/diff bytes
api/routers/monitor.py # + screenshot / visual-diff endpoints, + screenshot_enabled in schemas
```

---

## 4. Components

### 4.1 `core/visual/models.py`

Pydantic model for the diff result:

```python
class VisualDiffResult(BaseModel):
    changed: bool
    diff_score: float
    changed_regions: int
    diff_bytes: Optional[bytes] = None
```

- `diff_score`: ratio of changed pixels after resizing to a common dimension (0.0–1.0+).
- `changed_regions`: number of bounding boxes drawn on the overlay.

### 4.2 `core/visual/screenshot.py`

`ScreenshotProvider` protocol:

```python
class ScreenshotProvider(Protocol):
    def capture(self, url: str) -> bytes: ...
```

Implementations:

- `PlaywrightScreenshotProvider`
  - Launches headless Chromium.
  - Viewport 1280×720.
  - Full-page scroll/capture.
  - Returns PNG bytes.
  - Raises `ScreenshotError` on failure.
- `StaticScreenshotProvider`
  - Returns a deterministic PNG fixture for tests/CI.
  - Constructor accepts `width`, `height`, and optional `color` so tests can produce distinct images.

### 4.3 `core/visual/storage.py`

`ScreenshotStorage` port:

```python
class ScreenshotStorage(Protocol):
    def save_snapshot(self, site_id: int, snapshot_id: int, data: bytes) -> str: ...
    def load_snapshot(self, site_id: int, snapshot_id: int) -> Optional[bytes]: ...
    def save_diff(self, site_id: int, change_id: int, data: bytes) -> str: ...
    def load_diff(self, site_id: int, change_id: int) -> Optional[bytes]: ...
    def exists(self, relative_path: str) -> bool: ...
```

`FileSystemScreenshotStorage` writes to:

- `data/screenshots/{site_id}/{snapshot_id}.png`
- `data/screenshots/{site_id}/diffs/{change_id}.png`

It creates parent directories on demand and returns relative paths.

### 4.4 `core/visual/diff.py`

`VisualDiffEngine`:

- Resizes both images to the same dimensions using Pillow.
- Computes a per-pixel difference.
- Groups changed pixels into bounding boxes (contiguous regions).
- Draws red rectangles on a copy of the new image.
- Returns `VisualDiffResult`.

Identical images produce `changed=False`, `diff_bytes=None`.

---

## 5. Data flow

### 5.1 Scout capture

1. `ScoutAgent.run(site, previous_snapshot)` scrapes markdown as today.
2. If `site.screenshot_enabled` is `True` and `screenshot_provider` is not `None`:
   - `provider.capture(parsed.url)` returns PNG bytes.
   - Bytes are attached to the returned `ScoutEvent` in a new `screenshot_bytes` field.
3. If capture fails or provider is absent, log a warning and continue; the check is **not** marked failed.

### 5.1b Orchestrator persistence

After the orchestrator persists the new `MonitorSnapshot` and obtains its `id`:

1. If `scout_event.screenshot_bytes` is not `None`:
   - `screenshot_storage.save_snapshot(site_id, snapshot.id, bytes)` persists the file.
   - Set `snapshot.screenshot_path` to the returned relative path and commit.

The orchestrator receives `screenshot_provider` (default `None` to keep Playwright optional) and `screenshot_storage` (default `FileSystemScreenshotStorage`). Tests can inject a `StaticScreenshotProvider` and an in-memory storage fake.

### 5.2 Analyst diff

1. `AnalystAgent.run(scout_event, old_snapshot, new_snapshot)` runs the semantic diff as today.
2. If both `old_snapshot` and `new_snapshot` have non-null `screenshot_path`:
   - Load both PNGs from storage.
   - `diff_engine.compare(old_bytes, new_bytes)` returns `VisualDiffResult`.
   - If `changed` is `True`:
     - Set `AnalysisEvent.visual_diff_bytes` and `vision_description = f"Screenshot changed in {result.changed_regions} regions"`.
     - The orchestrator persists `visual_diff_bytes` after it creates the `MonitorChange` record and obtains the `change_id`.
3. If diff comparison fails, log a warning and leave `visual_diff_path` as `None`.

### 5.3 API serving

Endpoints read the requested relative path from storage and stream the PNG bytes with `Content-Type: image/png`. They return `404 Not Found` if the DB record or file is missing.

---

## 6. Storage layout

All paths are relative to the project root:

| Resource | Path |
|---|---|
| Raw screenshot | `data/screenshots/{site_id}/{snapshot_id}.png` |
| Diff overlay | `data/screenshots/{site_id}/diffs/{change_id}.png` |

Directory creation is lazy. Orphaned files are not cleaned up in this phase.

---

## 7. Error handling

| Scenario | Behavior |
|---|---|
| `screenshot_enabled=False` | Skip capture entirely. |
| Provider is `None` and `screenshot_enabled=True` | Log warning; check succeeds; no screenshot. |
| Capture raises exception | Log warning; check succeeds; no screenshot. |
| Only one of old/new snapshots has a screenshot | Skip diff; no visual diff. |
| Diff engine raises exception | Log warning; no visual diff. |
| API requests missing file | Return `404`. |

---

## 8. API endpoints

Both endpoints require the same JWT authentication used by the existing monitor routes.

The `SiteCreate`, `SiteUpdate`, and `SiteOut` Pydantic schemas in `api/routers/monitor.py` are extended with `screenshot_enabled: bool = False` so users can opt a site into screenshot capture and see the current setting.

- `GET /api/monitor/sites/{id}/screenshots/{snapshot_id}`
  - Returns the PNG file with `Content-Type: image/png`.
  - `404` if the snapshot or screenshot file does not exist.

- `GET /api/monitor/changes/{id}/visual-diff`
  - Returns the diff overlay PNG.
  - `404` if the change or diff file does not exist.

---

## 9. Data model changes

Add one column to `MonitorSite` in `db/models.py`:

```python
screenshot_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
```

Existing columns used by this phase:

- `MonitorSnapshot.screenshot_path`
- `MonitorChange.visual_diff_path`
- `MonitorChange.vision_description`

---

## 10. Dependencies

Append to `requirements-api.txt`:

```text
playwright>=1.45.0
Pillow>=10.0.0
```

Update `README.md` local development section:

```bash
playwright install chromium
```

---

## 11. Tests

### 11.1 Unit tests

- `tests/core/test_screenshot.py`
  - `PlaywrightScreenshotProvider.capture` delegates to the injected playwright object.
  - `StaticScreenshotProvider` returns deterministic bytes and can produce distinct images.

- `tests/core/test_visual_diff.py`
  - Identical images → `changed=False`, `diff_bytes=None`, `diff_score=0.0`.
  - Different images → `changed=True`, non-empty overlay, `changed_regions >= 1`.

- `tests/core/test_scout_agent.py`
  - `screenshot_enabled=True` + provider → `ScoutEvent.screenshot_bytes` is set.
  - Provider absent → `ScoutEvent.screenshot_bytes` is `None` and event succeeds.

- `tests/core/test_analyst_agent.py`
  - Both snapshots have screenshots and they differ → `visual_diff_path` set.
  - Identical screenshots → `visual_diff_path=None`.

### 11.2 API tests

- `tests/api/test_screenshots.py`
  - Existing snapshot with path → returns PNG.
  - Missing snapshot path → `404`.
  - Change with visual diff path → returns PNG.
  - Missing diff → `404`.

### 11.3 Acceptance criteria

- A site with `screenshot_enabled=True` stores a screenshot on every successful check.
- Two identical screenshots produce `VisualDiffResult.changed=False`.
- Two different screenshots produce a diff overlay file and a non-empty `visual_diff_path`.
- Missing screenshot/diff file returns `404` from the API.
- All existing tests continue to pass and the new visual-diff tests pass (baseline before Phase 2: 94 passing).

---

## 12. Rollout notes

- Playwright/Chromium install is optional for normal development; tests use `StaticScreenshotProvider` by default.
- CI should install `playwright` and run `playwright install chromium` only if dedicated browser tests are added later.
- No database migration is required for the new `screenshot_enabled` column when using SQLite with `init_db()`; for production PostgreSQL, add a migration.

---

## 13. Open questions resolved

| Question | Decision |
|---|---|
| Vision description source | Simple computed string; no LLM vision call in this phase. |
| Storage backend | Local filesystem only. |
| Capture architecture | Abstracted `ScreenshotProvider` + `ScreenshotStorage` ports (Approach B). |
| Cleanup of old screenshots | Deferred. |
