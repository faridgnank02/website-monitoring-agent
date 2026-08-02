# Phase 2 — Visual Diff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full-page screenshot capture, visual diff overlay generation, and image-serving API endpoints to Monitor Agent, gated by a per-site `screenshot_enabled` flag.

**Architecture:** A new `core/visual/` package provides `ScreenshotProvider` (capture), `ScreenshotStorage` (persistence), and `VisualDiffEngine` (Pillow-based comparison). `ScoutAgent` captures screenshot bytes, the orchestrator persists them after the snapshot is flushed, and `AnalystAgent` compares old/new screenshots when both exist. Two new API endpoints serve raw screenshots and diff overlays.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy 2.0, Pydantic, Playwright, Pillow, pytest.

---

## File Structure

**New files:**

- `core/visual/__init__.py` — convenience exports
- `core/visual/models.py` — `VisualDiffResult`
- `core/visual/storage.py` — `ScreenshotStorage` protocol + `FileSystemScreenshotStorage`
- `core/visual/screenshot.py` — `ScreenshotProvider` protocol + `PlaywrightScreenshotProvider` + `StaticScreenshotProvider`
- `core/visual/diff.py` — `VisualDiffEngine`
- `tests/core/test_screenshot_storage.py` — storage port tests
- `tests/core/test_screenshot.py` — provider tests
- `tests/core/test_visual_diff.py` — diff engine tests
- `tests/api/test_screenshots.py` — API endpoint tests

**Modified files:**

- `requirements-api.txt` — add `playwright`, `Pillow`
- `README.md` — add `playwright install chromium`
- `db/models.py` — add `MonitorSite.screenshot_enabled`
- `core/agents/events.py` — add `ScoutEvent.screenshot_bytes`
- `core/agents/scout.py` — inject `screenshot_provider`, capture when enabled
- `core/agents/analyst.py` — inject `screenshot_storage` + `diff_engine`, generate visual diff
- `core/orchestrator.py` — inject visual deps, persist screenshot bytes after snapshot flush
- `api/routers/monitor.py` — add `screenshot_enabled` to schemas and two new endpoints

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements-api.txt`
- Modify: `README.md`

- [ ] **Step 1: Add packages to requirements-api.txt**

Append to `requirements-api.txt`:

```text
# Visual diff (screenshots + image processing)
playwright>=1.45.0
Pillow>=10.0.0
```

- [ ] **Step 2: Document Playwright browser install in README.md**

In the README local development section (after `pip install -r requirements.txt -r requirements-api.txt`), add:

```markdown
# Install browser binaries for screenshot capture
playwright install chromium
```

- [ ] **Step 3: Install locally**

Run:

```bash
venv/bin/pip install -r requirements-api.txt
venv/bin/playwright install chromium
```

- [ ] **Step 4: Commit**

```bash
git add requirements-api.txt README.md
git commit -m "deps: add playwright and pillow for visual diff"
```

---

## Task 2: Visual Diff Result Model

**Files:**
- Create: `core/visual/models.py`
- Test: `tests/core/test_visual_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_visual_models.py`:

```python
from core.visual.models import VisualDiffResult


def test_visual_diff_result_defaults():
    result = VisualDiffResult(changed=True, diff_score=0.5, changed_regions=3)
    assert result.changed is True
    assert result.diff_score == 0.5
    assert result.changed_regions == 3
    assert result.diff_bytes is None


def test_visual_diff_result_with_bytes():
    result = VisualDiffResult(changed=True, diff_score=0.1, changed_regions=1, diff_bytes=b"pngdata")
    assert result.diff_bytes == b"pngdata"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/core/test_visual_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.visual.models'`

- [ ] **Step 3: Implement the model**

Create `core/visual/__init__.py`:

```python
from core.visual.models import VisualDiffResult
from core.visual.screenshot import ScreenshotProvider, ScreenshotError, StaticScreenshotProvider, PlaywrightScreenshotProvider
from core.visual.storage import ScreenshotStorage, FileSystemScreenshotStorage
from core.visual.diff import VisualDiffEngine

__all__ = [
    "VisualDiffResult",
    "ScreenshotProvider",
    "ScreenshotError",
    "StaticScreenshotProvider",
    "PlaywrightScreenshotProvider",
    "ScreenshotStorage",
    "FileSystemScreenshotStorage",
    "VisualDiffEngine",
]
```

Create `core/visual/models.py`:

```python
from typing import Optional
from pydantic import BaseModel


class VisualDiffResult(BaseModel):
    changed: bool
    diff_score: float
    changed_regions: int
    diff_bytes: Optional[bytes] = None
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/core/test_visual_models.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/visual/__init__.py core/visual/models.py tests/core/test_visual_models.py
git commit -m "feat(visual): add VisualDiffResult model"
```

---

## Task 3: Screenshot Storage Port

**Files:**
- Create: `core/visual/storage.py`
- Test: `tests/core/test_screenshot_storage.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_screenshot_storage.py`:

```python
import os
import tempfile

from core.visual.storage import FileSystemScreenshotStorage


def test_save_and_load_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        path = storage.save_snapshot(site_id=1, snapshot_id=42, data=b"png")
        assert path == "data/screenshots/1/42.png"
        assert storage.exists(path) is True
        assert storage.load_snapshot(1, 42) == b"png"


def test_save_and_load_diff():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        path = storage.save_diff(site_id=1, change_id=7, data=b"diff")
        assert path == "data/screenshots/1/diffs/7.png"
        assert storage.exists(path) is True
        assert storage.load_diff(1, 7) == b"diff"


def test_load_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        assert storage.load_snapshot(1, 999) is None
        assert storage.load_diff(1, 999) is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/core/test_screenshot_storage.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.visual.storage'`

- [ ] **Step 3: Implement the storage port**

Create `core/visual/storage.py`:

```python
import os
from pathlib import Path
from typing import Optional, Protocol


class ScreenshotStorage(Protocol):
    def save_snapshot(self, site_id: int, snapshot_id: int, data: bytes) -> str: ...
    def load_snapshot(self, site_id: int, snapshot_id: int) -> Optional[bytes]: ...
    def save_diff(self, site_id: int, change_id: int, data: bytes) -> str: ...
    def load_diff(self, site_id: int, change_id: int) -> Optional[bytes]: ...
    def exists(self, relative_path: str) -> bool: ...


class FileSystemScreenshotStorage:
    """Store screenshots under <project_root>/data/screenshots/{site_id}/..."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.screenshots_dir = self.base_dir / "data" / "screenshots"

    def save_snapshot(self, site_id: int, snapshot_id: int, data: bytes) -> str:
        path = self._snapshot_path(site_id, snapshot_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.relative_to(self.base_dir))

    def load_snapshot(self, site_id: int, snapshot_id: int) -> Optional[bytes]:
        path = self._snapshot_path(site_id, snapshot_id)
        if not path.exists():
            return None
        return path.read_bytes()

    def save_diff(self, site_id: int, change_id: int, data: bytes) -> str:
        path = self._diff_path(site_id, change_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.relative_to(self.base_dir))

    def load_diff(self, site_id: int, change_id: int) -> Optional[bytes]:
        path = self._diff_path(site_id, change_id)
        if not path.exists():
            return None
        return path.read_bytes()

    def exists(self, relative_path: str) -> bool:
        return (self.base_dir / relative_path).exists()

    def _snapshot_path(self, site_id: int, snapshot_id: int) -> Path:
        return self.screenshots_dir / str(site_id) / f"{snapshot_id}.png"

    def _diff_path(self, site_id: int, change_id: int) -> Path:
        return self.screenshots_dir / str(site_id) / "diffs" / f"{change_id}.png"
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/core/test_screenshot_storage.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add core/visual/storage.py tests/core/test_screenshot_storage.py
git commit -m "feat(visual): add filesystem screenshot storage port"
```

---

## Task 4: Screenshot Provider

**Files:**
- Create: `core/visual/screenshot.py`
- Test: `tests/core/test_screenshot.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_screenshot.py`:

```python
from unittest.mock import MagicMock

from core.visual.screenshot import PlaywrightScreenshotProvider, StaticScreenshotProvider


def test_static_provider_returns_png_bytes():
    provider = StaticScreenshotProvider(width=100, height=50, color=(255, 0, 0))
    data = provider.capture("https://example.com")
    assert data.startswith(b"\x89PNG")


def test_static_provider_can_produce_different_images():
    red = StaticScreenshotProvider(width=10, height=10, color=(255, 0, 0))
    blue = StaticScreenshotProvider(width=10, height=10, color=(0, 0, 255))
    assert red.capture("x") != blue.capture("x")


def test_playwright_provider_delegates_to_browser():
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_page.return_value = mock_page
    mock_page.screenshot.return_value = b"fakepng"

    provider = PlaywrightScreenshotProvider(_sync_playwright=lambda: mock_playwright)
    result = provider.capture("https://example.com")

    assert result == b"fakepng"
    mock_page.goto.assert_called_once_with("https://example.com", wait_until="networkidle")
    mock_page.screenshot.assert_called_once_with(full_page=True, type="png")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/core/test_screenshot.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.visual.screenshot'`

- [ ] **Step 3: Implement the providers**

Create `core/visual/screenshot.py`:

```python
from typing import Optional, Protocol
from io import BytesIO

from PIL import Image


class ScreenshotProvider(Protocol):
    def capture(self, url: str) -> bytes: ...


class ScreenshotError(Exception):
    pass


class StaticScreenshotProvider:
    """Deterministic PNG provider for tests and CI."""

    def __init__(self, width: int = 1280, height: int = 720, color: Optional[tuple[int, int, int]] = None):
        self.width = width
        self.height = height
        self.color = color or (100, 150, 200)

    def capture(self, url: str) -> bytes:
        image = Image.new("RGB", (self.width, self.height), self.color)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


class PlaywrightScreenshotProvider:
    """Full-page screenshot via Playwright/Chromium."""

    def __init__(
        self,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        _sync_playwright=None,
    ):
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self._sync_playwright = _sync_playwright

    def capture(self, url: str) -> bytes:
        try:
            if self._sync_playwright is not None:
                playwright = self._sync_playwright()
            else:
                from playwright.sync_api import sync_playwright
                playwright = sync_playwright().start()
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport=self.viewport)
            page.goto(url, wait_until="networkidle")
            data = page.screenshot(full_page=True, type="png")
            browser.close()
            if self._sync_playwright is None:
                playwright.stop()
            return data
        except Exception as exc:
            raise ScreenshotError(f"Failed to capture screenshot of {url}: {exc}") from exc
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/core/test_screenshot.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add core/visual/screenshot.py tests/core/test_screenshot.py
git commit -m "feat(visual): add screenshot provider abstraction"
```

---

## Task 5: Visual Diff Engine

**Files:**
- Create: `core/visual/diff.py`
- Test: `tests/core/test_visual_diff.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_visual_diff.py`:

```python
from core.visual.diff import VisualDiffEngine
from core.visual.screenshot import StaticScreenshotProvider


def test_identical_images_produce_no_diff():
    provider = StaticScreenshotProvider(width=20, height=20, color=(255, 255, 255))
    img = provider.capture("x")
    engine = VisualDiffEngine()
    result = engine.compare(img, img)
    assert result.changed is False
    assert result.diff_bytes is None
    assert result.diff_score == 0.0
    assert result.changed_regions == 0


def test_different_images_produce_diff():
    old = StaticScreenshotProvider(width=20, height=20, color=(255, 255, 255)).capture("x")
    new = StaticScreenshotProvider(width=20, height=20, color=(0, 0, 0)).capture("x")
    engine = VisualDiffEngine()
    result = engine.compare(old, new)
    assert result.changed is True
    assert result.diff_bytes is not None
    assert result.diff_score > 0.0
    assert result.changed_regions >= 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/core/test_visual_diff.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.visual.diff'`

- [ ] **Step 3: Implement the diff engine**

Create `core/visual/diff.py`:

```python
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw

from core.visual.models import VisualDiffResult


class VisualDiffEngine:
    """Compare two screenshots and produce a highlighted diff overlay."""

    def __init__(self, threshold: int = 30, min_region_size: int = 10):
        self.threshold = threshold
        self.min_region_size = min_region_size

    def compare(self, old_bytes: bytes, new_bytes: bytes) -> VisualDiffResult:
        old_image = Image.open(BytesIO(old_bytes)).convert("RGB")
        new_image = Image.open(BytesIO(new_bytes)).convert("RGB")

        # Resize to common size (use the larger dimensions)
        width = max(old_image.width, new_image.width)
        height = max(old_image.height, new_image.height)
        old_image = old_image.resize((width, height), Image.Resampling.LANCZOS)
        new_image = new_image.resize((width, height), Image.Resampling.LANCZOS)

        diff_pixels = 0
        total_pixels = width * height
        changed_mask = [[False for _ in range(height)] for _ in range(width)]

        old_pixels = old_image.load()
        new_pixels = new_image.load()

        for x in range(width):
            for y in range(height):
                old_pixel = old_pixels[x, y]
                new_pixel = new_pixels[x, y]
                distance = sum(abs(a - b) for a, b in zip(old_pixel, new_pixel))
                if distance > self.threshold:
                    diff_pixels += 1
                    changed_mask[x][y] = True

        if diff_pixels == 0:
            return VisualDiffResult(changed=False, diff_score=0.0, changed_regions=0, diff_bytes=None)

        regions = self._find_regions(changed_mask, width, height)
        overlay = new_image.copy()
        draw = ImageDraw.Draw(overlay)
        for region in regions:
            draw.rectangle(region, outline="red", width=2)

        buffer = BytesIO()
        overlay.save(buffer, format="PNG")

        return VisualDiffResult(
            changed=True,
            diff_score=round(diff_pixels / total_pixels, 6),
            changed_regions=len(regions),
            diff_bytes=buffer.getvalue(),
        )

    def _find_regions(self, mask: list[list[bool]], width: int, height: int) -> list[tuple[int, int, int, int]]:
        """Group changed pixels into axis-aligned bounding boxes."""
        visited = [[False for _ in range(height)] for _ in range(width)]
        regions: list[tuple[int, int, int, int]] = []

        for x in range(width):
            for y in range(height):
                if not mask[x][y] or visited[x][y]:
                    continue
                min_x, max_x = x, x
                min_y, max_y = y, y
                stack = [(x, y)]
                visited[x][y] = True
                while stack:
                    cx, cy = stack.pop()
                    min_x, max_x = min(min_x, cx), max(max_x, cx)
                    min_y, max_y = min(min_y, cy), max(max_y, cy)
                    for nx, ny in [(cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)]:
                        if 0 <= nx < width and 0 <= ny < height and mask[nx][ny] and not visited[nx][ny]:
                            visited[nx][ny] = True
                            stack.append((nx, ny))

                if max_x - min_x + 1 >= self.min_region_size or max_y - min_y + 1 >= self.min_region_size:
                    regions.append((min_x, min_y, max_x, max_y))

        return regions
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/core/test_visual_diff.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/visual/diff.py tests/core/test_visual_diff.py
git commit -m "feat(visual): add pillow-based visual diff engine"
```

---

## Task 6: Add `screenshot_bytes` to `ScoutEvent`

**Files:**
- Modify: `core/agents/events.py`
- Test: `tests/core/test_agent_events.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_agent_events.py`:

```python
from core.agents.events import ScoutEvent, AnalysisEvent


def test_scout_event_carries_screenshot_bytes():
    event = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        url="https://example.com",
        screenshot_bytes=b"png",
    )
    assert event.screenshot_bytes == b"png"


def test_analysis_event_carries_visual_diff_bytes():
    event = AnalysisEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        visual_diff_bytes=b"diffpng",
        visual_diff_path="data/screenshots/1/diffs/1.png",
    )
    assert event.visual_diff_bytes == b"diffpng"
    assert event.visual_diff_path == "data/screenshots/1/diffs/1.png"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/core/test_agent_events.py::test_scout_event_carries_screenshot_bytes -v
```

Expected: validation error for `screenshot_bytes`

- [ ] **Step 3: Add the field**

Modify `core/agents/events.py`:

Add to `ScoutEvent`:

```python
class ScoutEvent(AgentEvent):
    stage: str = "scout"
    has_change: bool
    snapshot_id: Optional[int] = None
    url: str
    content_markdown: Optional[str] = None
    content_html: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    entities: list[Entity] = Field(default_factory=list)
    screenshot_bytes: Optional[bytes] = None
    error: Optional[str] = None
```

Add to `AnalysisEvent`:

```python
class AnalysisEvent(AgentEvent):
    stage: str = "analyst"
    has_change: bool
    change_type: str = "content_update"
    severity: str = "low"
    change_score: float = 0.0
    added_lines: int = 0
    removed_lines: int = 0
    modified_lines: int = 0
    visual_diff_path: Optional[str] = None
    visual_diff_bytes: Optional[bytes] = None
    vision_description: Optional[str] = None
    semantic_diff_summary: Optional[str] = None
    correlated_entities: list[CorrelatedEntity] = Field(default_factory=list)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/core/test_agent_events.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add core/agents/events.py tests/core/test_agent_events.py
git commit -m "feat(events): add screenshot_bytes and visual_diff_bytes"
```

---

## Task 7: Wire Screenshot Capture into `ScoutAgent`

**Files:**
- Modify: `core/agents/scout.py`
- Test: `tests/core/test_scout_agent.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_scout_agent.py`:

```python
from unittest.mock import MagicMock
from core.visual.screenshot import StaticScreenshotProvider


def test_scout_captures_screenshot_when_enabled():
    site = MonitorSite(id=1, instruction="test", threshold=1.0, screenshot_enabled=True, url="https://example.com")
    provider = StaticScreenshotProvider(width=10, height=10, color=(0, 0, 0))
    agent = ScoutAgent(screenshot_provider=provider)
    event = agent.run(site, previous_snapshot=None)
    assert event.screenshot_bytes is not None
    assert event.screenshot_bytes.startswith(b"\x89PNG")


def test_scout_skips_screenshot_when_disabled():
    site = MonitorSite(id=1, instruction="test", threshold=1.0, screenshot_enabled=False, url="https://example.com")
    provider = StaticScreenshotProvider(width=10, height=10, color=(0, 0, 0))
    agent = ScoutAgent(screenshot_provider=provider)
    event = agent.run(site, previous_snapshot=None)
    assert event.screenshot_bytes is None


def test_scout_continues_when_provider_is_none():
    site = MonitorSite(id=1, instruction="test", threshold=1.0, screenshot_enabled=True, url="https://example.com")
    agent = ScoutAgent(screenshot_provider=None)
    event = agent.run(site, previous_snapshot=None)
    assert event.screenshot_bytes is None
    assert event.error is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/core/test_scout_agent.py::test_scout_captures_screenshot_when_enabled -v
```

Expected: `TypeError: ScoutAgent.__init__() got an unexpected keyword argument 'screenshot_provider'`

- [ ] **Step 3: Update `ScoutAgent` implementation**

Modify `core/agents/scout.py`:

```python
import hashlib
import time
from typing import Optional
from sqlalchemy.orm import Session

from core.agents.events import ScoutEvent
from core.entities.extractor import extract_entities
from core.entities.models import Entity
from core.llm.router import LLMRouter
from core.visual.screenshot import ScreenshotProvider
from db.models import MonitorSite, MonitorSnapshot
from src.modules import parse_instruction, scrape_url


class ScoutAgent:
    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        db: Optional[Session] = None,
        parse_instruction=parse_instruction,
        scrape_url=scrape_url,
        screenshot_provider: Optional[ScreenshotProvider] = None,
    ):
        self.llm_router = llm_router
        self.db = db
        self.parse_instruction = parse_instruction
        self.scrape_url = scrape_url
        self.screenshot_provider = screenshot_provider

    def run(self, site: MonitorSite, previous_snapshot: Optional[MonitorSnapshot] = None) -> ScoutEvent:
        start = time.time()
        parsed = self.parse_instruction(site.instruction)
        if not parsed.success:
            return ScoutEvent(
                run_id="", site_id=site.id, has_change=False, url="", error=parsed.error
            )

        if not site.url:
            site.url = parsed.url
            if self.db:
                self.db.commit()

        scraped = self.scrape_url(parsed.url)
        if not scraped.success:
            return ScoutEvent(
                run_id="", site_id=site.id, has_change=False, url=parsed.url, error=scraped.error
            )

        content_hash = hashlib.md5(scraped.markdown.encode("utf-8")).hexdigest()
        has_change = previous_snapshot is None or previous_snapshot.content_hash != content_hash

        entities: list[Entity] = []
        if has_change:
            entities = extract_entities(scraped.markdown, self.llm_router)

        screenshot_bytes = self._capture_screenshot(parsed.url, site)

        latency_ms = (time.time() - start) * 1000
        return ScoutEvent(
            run_id="",
            site_id=site.id,
            has_change=has_change,
            url=parsed.url,
            content_markdown=scraped.markdown,
            content_html=scraped.html,
            content_hash=content_hash,
            metadata=scraped.metadata if isinstance(scraped.metadata, dict) else {},
            entities=entities,
            screenshot_bytes=screenshot_bytes,
            latency_ms=latency_ms,
        )

    def _capture_screenshot(self, url: str, site: MonitorSite) -> Optional[bytes]:
        if not site.screenshot_enabled or self.screenshot_provider is None:
            return None
        try:
            return self.screenshot_provider.capture(url)
        except Exception:
            # Log warning in production; swallow in agent to avoid failing the check.
            return None
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/core/test_scout_agent.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add core/agents/scout.py tests/core/test_scout_agent.py
git commit -m "feat(scout): capture screenshots when site.screenshot_enabled is true"
```

---

## Task 8: Wire Visual Diff into `AnalystAgent`

**Files:**
- Modify: `core/agents/analyst.py`
- Test: `tests/core/test_analyst_agent.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_analyst_agent.py`:

```python
import tempfile

from core.visual.diff import VisualDiffEngine
from core.visual.storage import FileSystemScreenshotStorage
from core.visual.screenshot import StaticScreenshotProvider


def test_analyst_generates_visual_diff_for_different_screenshots():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        old_snapshot = MonitorSnapshot(
            id=1,
            site_id=1,
            content_markdown="old",
            content_hash="a",
            screenshot_path=storage.save_snapshot(1, 1, StaticScreenshotProvider(20, 20, (255, 255, 255)).capture("x")),
        )
        new_snapshot = MonitorSnapshot(
            id=2,
            site_id=1,
            content_markdown="new",
            content_hash="b",
            screenshot_path=storage.save_snapshot(1, 2, StaticScreenshotProvider(20, 20, (0, 0, 0)).capture("x")),
        )
        scout = ScoutEvent(run_id="r1", site_id=1, has_change=True, url="x")
        agent = AnalystAgent(screenshot_storage=storage, diff_engine=VisualDiffEngine())
        analysis = agent.run(scout, old_snapshot, new_snapshot)
        assert analysis.visual_diff_bytes is not None
        assert analysis.visual_diff_path is None
        assert "changed in" in (analysis.vision_description or "").lower()


def test_analyst_skips_visual_diff_for_identical_screenshots():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        img = StaticScreenshotProvider(20, 20, (255, 255, 255)).capture("x")
        old_snapshot = MonitorSnapshot(
            id=1,
            site_id=1,
            content_markdown="old",
            content_hash="a",
            screenshot_path=storage.save_snapshot(1, 1, img),
        )
        new_snapshot = MonitorSnapshot(
            id=2,
            site_id=1,
            content_markdown="new",
            content_hash="b",
            screenshot_path=storage.save_snapshot(1, 2, img),
        )
        scout = ScoutEvent(run_id="r1", site_id=1, has_change=True, url="x")
        agent = AnalystAgent(screenshot_storage=storage, diff_engine=VisualDiffEngine())
        analysis = agent.run(scout, old_snapshot, new_snapshot)
        assert analysis.visual_diff_bytes is None
        assert analysis.visual_diff_path is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/core/test_analyst_agent.py::test_analyst_generates_visual_diff_for_different_screenshots -v
```

Expected: `TypeError: AnalystAgent.__init__() got an unexpected keyword argument 'screenshot_storage'`

- [ ] **Step 3: Update `AnalystAgent` implementation**

Modify `core/agents/analyst.py` to import and use visual modules:

```python
import re
import time
from typing import Optional, Union

from core.agents.events import ScoutEvent, AnalysisEvent
from core.llm.router import LLMRouter
from core.visual.diff import VisualDiffEngine
from core.visual.storage import ScreenshotStorage
from db.models import MonitorSnapshot
from src.modules import compare_content
from core.entities.correlator import correlate_entities
from core.entities.models import CorrelatedEntity, Entity
```

Update the constructor and `run`:

```python
class AnalystAgent:
    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        screenshot_storage: Optional[ScreenshotStorage] = None,
        diff_engine: Optional[VisualDiffEngine] = None,
    ):
        self.llm_router = llm_router
        self.screenshot_storage = screenshot_storage
        self.diff_engine = diff_engine or VisualDiffEngine()

    def run(self, scout: ScoutEvent, old_snapshot: Optional[MonitorSnapshot], new_snapshot: Optional[MonitorSnapshot]) -> AnalysisEvent:
        start = time.time()
        if not scout.has_change or old_snapshot is None or new_snapshot is None:
            return AnalysisEvent(
                run_id=scout.run_id,
                site_id=scout.site_id,
                has_change=False,
                change_type="content_update",
                severity="low",
            )

        comparison = compare_content(
            old_snapshot.content_markdown or "",
            new_snapshot.content_markdown or "",
            threshold=0.0,
        )

        old_entities = _normalize_snapshot_entities(old_snapshot.extracted_entities or [])
        new_entities = _normalize_snapshot_entities(new_snapshot.extracted_entities or [])
        correlated = correlate_entities(old_entities, new_entities)

        change_type = self._classify_change(correlated, comparison)
        severity = self._severity(change_type, comparison.change_score)
        summary = comparison.diff_summary if comparison.has_changes else "No significant changes"

        visual_diff_bytes, vision_description = self._compare_screenshots(
            old_snapshot, new_snapshot
        )

        latency_ms = (time.time() - start) * 1000
        return AnalysisEvent(
            run_id=scout.run_id,
            site_id=scout.site_id,
            has_change=comparison.has_changes,
            change_type=change_type,
            severity=severity,
            change_score=comparison.change_score,
            added_lines=len(comparison.added_lines),
            removed_lines=len(comparison.removed_lines),
            modified_lines=len(comparison.modified_lines),
            semantic_diff_summary=summary,
            visual_diff_bytes=visual_diff_bytes,
            vision_description=vision_description,
            latency_ms=latency_ms,
            correlated_entities=correlated,
        )

    def _compare_screenshots(
        self,
        old_snapshot: MonitorSnapshot,
        new_snapshot: MonitorSnapshot,
    ) -> tuple[Optional[bytes], Optional[str]]:
        if self.screenshot_storage is None:
            return None, None
        if not old_snapshot.screenshot_path or not new_snapshot.screenshot_path:
            return None, None
        old_bytes = self.screenshot_storage.load_snapshot(old_snapshot.site_id, old_snapshot.id)
        new_bytes = self.screenshot_storage.load_snapshot(new_snapshot.site_id, new_snapshot.id)
        if old_bytes is None or new_bytes is None:
            return None, None
        try:
            result = self.diff_engine.compare(old_bytes, new_bytes)
            if not result.changed or result.diff_bytes is None:
                return None, None
            return result.diff_bytes, f"Screenshot changed in {result.changed_regions} regions"
        except Exception:
            return None, None
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/core/test_analyst_agent.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add core/agents/analyst.py tests/core/test_analyst_agent.py
git commit -m "feat(analyst): compare screenshots and generate visual diff overlays"
```

---

## Task 9: Wire Visual Deps into `MonitoringOrchestrator`

**Files:**
- Modify: `core/orchestrator.py`
- Test: `tests/core/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_orchestrator.py`:

```python
import tempfile
from unittest.mock import patch, MagicMock

from core.visual.screenshot import StaticScreenshotProvider
from core.visual.storage import FileSystemScreenshotStorage
from core.visual.diff import VisualDiffEngine
from core.orchestrator import MonitoringOrchestrator


def test_orchestrator_persists_screenshot():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        provider = StaticScreenshotProvider(width=20, height=20, color=(0, 0, 0))

        db = SessionLocal()
        try:
            user = User(email="visual@example.com", hashed_password="x")
            db.add(user)
            db.commit()
            site = MonitorSite(
                user_id=user.id,
                instruction="test",
                threshold=1.0,
                url="https://example.com",
                screenshot_enabled=True,
            )
            db.add(site)
            db.commit()

            orchestrator = MonitoringOrchestrator(
                db,
                screenshot_provider=provider,
                screenshot_storage=storage,
                diff_engine=VisualDiffEngine(),
            )

            with patch.object(orchestrator.scout, "parse_instruction") as mock_parse, \
                 patch.object(orchestrator.scout, "scrape_url") as mock_scrape:
                mock_parse.return_value = MagicMock(success=True, url="https://example.com")
                mock_scrape.return_value = MagicMock(
                    success=True,
                    markdown="hello",
                    html="<html></html>",
                    metadata={},
                )
                result = orchestrator.run(site)

            assert result["success"] is True
            snapshots = db.query(MonitorSnapshot).filter(MonitorSnapshot.site_id == site.id).all()
            assert len(snapshots) == 1
            assert snapshots[0].screenshot_path is not None
            assert storage.exists(snapshots[0].screenshot_path)
        finally:
            db.close()


def test_orchestrator_persists_visual_diff_on_change():
    with tempfile.TemporaryDirectory() as tmp:
        storage = FileSystemScreenshotStorage(base_dir=tmp)
        black = StaticScreenshotProvider(width=20, height=20, color=(0, 0, 0))
        white = StaticScreenshotProvider(width=20, height=20, color=(255, 255, 255))

        db = SessionLocal()
        try:
            user = User(email="visual-diff@example.com", hashed_password="x")
            db.add(user)
            db.commit()
            site = MonitorSite(
                user_id=user.id,
                instruction="test",
                threshold=1.0,
                url="https://example.com",
                screenshot_enabled=True,
            )
            db.add(site)
            db.commit()

            # Seed previous snapshot with a white screenshot
            prev = MonitorSnapshot(
                site_id=site.id,
                content_markdown="old",
                content_hash="a",
                content_length=3,
                status="success",
                screenshot_path=storage.save_snapshot(site.id, 1, white.capture("x")),
            )
            db.add(prev)
            db.commit()

            orchestrator = MonitoringOrchestrator(
                db,
                screenshot_provider=black,
                screenshot_storage=storage,
                diff_engine=VisualDiffEngine(),
            )

            with patch.object(orchestrator.scout, "parse_instruction") as mock_parse, \
                 patch.object(orchestrator.scout, "scrape_url") as mock_scrape:
                mock_parse.return_value = MagicMock(success=True, url="https://example.com")
                mock_scrape.return_value = MagicMock(
                    success=True,
                    markdown="new content",
                    html="<html></html>",
                    metadata={},
                )
                result = orchestrator.run(site)

            assert result["success"] is True
            assert result["change_detected"] is True
            changes = db.query(MonitorChange).filter(MonitorChange.site_id == site.id).all()
            assert len(changes) == 1
            assert changes[0].visual_diff_path is not None
            assert storage.exists(changes[0].visual_diff_path)
        finally:
            db.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/core/test_orchestrator.py::test_orchestrator_persists_screenshot -v
```

Expected: `TypeError: MonitoringOrchestrator.__init__() got an unexpected keyword argument 'screenshot_provider'`

- [ ] **Step 3: Update `MonitoringOrchestrator` implementation**

Modify `core/orchestrator.py`:

```python
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session

from core.agents.events import ScoutEvent, AnalysisEvent, ReportEvent, ActionEvent
from core.agents.scout import ScoutAgent
from core.agents.analyst import AnalystAgent
from core.agents.reporter import ReporterAgent
from core.agents.action import ActionAgent
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.llm.router import LLMRouter
from core.visual.diff import VisualDiffEngine
from core.visual.screenshot import ScreenshotProvider
from core.visual.storage import FileSystemScreenshotStorage, ScreenshotStorage
from db.models import MonitorSite, MonitorSnapshot, MonitorChange, AuditLog, ApprovalRequest
from config.settings import load_llm_router_config
from src.modules import parse_instruction, scrape_url


class MonitoringOrchestrator:
    def __init__(
        self,
        db: Session,
        screenshot_provider: Optional[ScreenshotProvider] = None,
        screenshot_storage: Optional[ScreenshotStorage] = None,
        diff_engine: Optional[VisualDiffEngine] = None,
    ):
        self.db = db
        self.llm_router = LLMRouter(load_llm_router_config())
        self.screenshot_storage = screenshot_storage or FileSystemScreenshotStorage()
        self.diff_engine = diff_engine or VisualDiffEngine()
        self.scout = ScoutAgent(
            llm_router=self.llm_router,
            db=db,
            parse_instruction=parse_instruction,
            scrape_url=scrape_url,
            screenshot_provider=screenshot_provider,
        )
        self.analyst = AnalystAgent(
            llm_router=self.llm_router,
            screenshot_storage=self.screenshot_storage,
            diff_engine=self.diff_engine,
        )
        self.reporter = ReporterAgent(llm_router=self.llm_router)
        self.action_registry = ActionHandlerRegistry()
        self.action_registry.register(EmailActionHandler())
        self.action_registry.register(SlackActionHandler())
        self.action_agent = ActionAgent(self.action_registry)
```

Update `_save_snapshot` to persist screenshot bytes and `_save_change` to persist visual diff bytes:

```python
    def _save_snapshot(self, site: MonitorSite, run_id: str, event: ScoutEvent) -> MonitorSnapshot:
        content = event.content_markdown or ""
        snap = MonitorSnapshot(
            site_id=site.id,
            content_markdown=content,
            content_hash=event.content_hash or hashlib.md5(content.encode("utf-8")).hexdigest(),
            content_length=len(content),
            status="success",
            extracted_entities=[e.model_dump() for e in event.entities],
            model_calls={"run_id": run_id},
        )
        self.db.add(snap)
        self.db.flush()

        if event.screenshot_bytes is not None:
            try:
                path = self.screenshot_storage.save_snapshot(site.id, snap.id, event.screenshot_bytes)
                snap.screenshot_path = path
            except Exception:
                # Screenshot persistence must not fail the check.
                pass

        site.last_checked_at = datetime.utcnow()
        self.db.commit()
        return snap

    def _save_change(self, site, run_id, old, new, analysis: AnalysisEvent) -> MonitorChange:
        change = MonitorChange(
            site_id=site.id,
            change_score=analysis.change_score,
            added_lines=analysis.added_lines,
            removed_lines=analysis.removed_lines,
            modified_lines=analysis.modified_lines,
            change_type=analysis.change_type,
            severity=analysis.severity,
            diff_summary=analysis.semantic_diff_summary,
            vision_description=analysis.vision_description,
            old_snapshot_id=old.id if old else None,
            new_snapshot_id=new.id if new else None,
            alert_sent=False,
            agent_reasoning={"run_id": run_id},
        )
        self.db.add(change)
        self.db.flush()

        if analysis.visual_diff_bytes is not None:
            try:
                path = self.screenshot_storage.save_diff(site.id, change.id, analysis.visual_diff_bytes)
                change.visual_diff_path = path
            except Exception:
                # Visual diff persistence must not fail the check.
                pass

        self.db.commit()
        return change
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/core/test_orchestrator.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add core/orchestrator.py tests/core/test_orchestrator.py
git commit -m "feat(orchestrator): inject visual deps and persist screenshot bytes"
```

---

## Task 10: Add `screenshot_enabled` to Site Model and API Schemas

**Files:**
- Modify: `db/models.py`
- Modify: `api/routers/monitor.py`
- Test: `tests/db/test_models.py` (or create it)

- [ ] **Step 1: Write the failing test**

Append to `tests/db/test_models.py`:

```python

def test_site_has_screenshot_enabled(db):
    user = User(email=f"screenshot-{uuid.uuid4()}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    site = MonitorSite(
        user_id=user.id,
        instruction="test",
        threshold=1.0,
        screenshot_enabled=True,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    assert site.screenshot_enabled is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/db/test_models.py -v
```

Expected: `TypeError: MonitorSite.__init__() got an unexpected keyword argument 'screenshot_enabled'`

- [ ] **Step 3: Update the model and schemas**

Modify `db/models.py`, add to `MonitorSite`:

```python
    screenshot_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
```

Modify `api/routers/monitor.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/db/test_models.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Run API schema tests**

Run:

```bash
venv/bin/python -m pytest tests/api/ -v
```

Expected: existing API tests still pass

- [ ] **Step 6: Commit**

```bash
git add db/models.py api/routers/monitor.py tests/db/test_models.py
git commit -m "feat(site): add screenshot_enabled flag to model and API schemas"
```

---

## Task 11: Add Screenshot and Visual Diff API Endpoints

**Files:**
- Modify: `api/routers/monitor.py`
- Test: `tests/api/test_screenshots.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/__init__.py` and `tests/api/test_screenshots.py`:

`tests/api/__init__.py`:

```python
```

`tests/api/test_screenshots.py`:

```python
import tempfile

from fastapi.testclient import TestClient

from api.main import app
from api.deps import get_db, get_current_user
from db.base import SessionLocal, init_db
from db.models import User, MonitorSite, MonitorSnapshot, MonitorChange
from core.visual.storage import FileSystemScreenshotStorage
from core.visual.screenshot import StaticScreenshotProvider


client = TestClient(app)


def _override_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _override_user():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "api@example.com").first()
        if not user:
            user = User(email="api@example.com", hashed_password="x")
            db.add(user)
            db.commit()
        return user
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_current_user] = _override_user


def test_get_screenshot_returns_png():
    init_db()
    db = SessionLocal()
    try:
        user = _override_user()
        site = MonitorSite(user_id=user.id, instruction="test", threshold=1.0, url="x")
        db.add(site)
        db.commit()
        db.refresh(site)
        snapshot = MonitorSnapshot(
            site_id=site.id,
            content_markdown="x",
            content_hash="a",
            content_length=1,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        storage = FileSystemScreenshotStorage()
        path = storage.save_snapshot(site.id, snapshot.id, StaticScreenshotProvider(10, 10).capture("x"))
        snapshot.screenshot_path = path
        db.commit()

        response = client.get(f"/api/monitor/sites/{site.id}/screenshots/{snapshot.id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
    finally:
        db.close()


def test_get_screenshot_missing_returns_404():
    init_db()
    response = client.get("/api/monitor/sites/1/screenshots/99999")
    assert response.status_code == 404


def test_get_visual_diff_returns_png():
    init_db()
    db = SessionLocal()
    try:
        user = _override_user()
        site = MonitorSite(user_id=user.id, instruction="test", threshold=1.0, url="x")
        db.add(site)
        db.commit()
        db.refresh(site)
        change = MonitorChange(
            site_id=site.id,
            change_score=1.0,
        )
        db.add(change)
        db.commit()
        db.refresh(change)

        storage = FileSystemScreenshotStorage()
        path = storage.save_diff(site.id, change.id, StaticScreenshotProvider(10, 10).capture("x"))
        change.visual_diff_path = path
        db.commit()

        response = client.get(f"/api/monitor/changes/{change.id}/visual-diff")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
    finally:
        db.close()


def test_get_visual_diff_missing_returns_404():
    init_db()
    response = client.get("/api/monitor/changes/99999/visual-diff")
    assert response.status_code == 404
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
venv/bin/python -m pytest tests/api/test_screenshots.py -v
```

Expected: `404` for all tests because endpoints don't exist yet

- [ ] **Step 3: Implement the endpoints**

Modify `api/routers/monitor.py`:

Add import:

```python
from fastapi.responses import FileResponse
from pathlib import Path
```

Add endpoints before the `# Helpers` section:

```python
# ---------------------------------------------------------------------------
# Screenshots + visual diff images
# ---------------------------------------------------------------------------

@router.get("/sites/{site_id}/screenshots/{snapshot_id}")
def get_screenshot(
    site_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site = _get_site_or_404(site_id, user.id, db)
    snapshot = (
        db.query(MonitorSnapshot)
        .filter(MonitorSnapshot.id == snapshot_id, MonitorSnapshot.site_id == site.id)
        .first()
    )
    if not snapshot or not snapshot.screenshot_path:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    full_path = Path.cwd() / snapshot.screenshot_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot file missing")
    return FileResponse(str(full_path), media_type="image/png")


@router.get("/changes/{change_id}/visual-diff")
def get_visual_diff(
    change_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    change = db.query(MonitorChange).filter(MonitorChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    site = db.query(MonitorSite).filter(
        MonitorSite.id == change.site_id,
        MonitorSite.user_id == user.id,
    ).first()
    if not site:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not change.visual_diff_path:
        raise HTTPException(status_code=404, detail="Visual diff not found")
    full_path = Path.cwd() / change.visual_diff_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Visual diff file missing")
    return FileResponse(str(full_path), media_type="image/png")
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
venv/bin/python -m pytest tests/api/test_screenshots.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add api/routers/monitor.py tests/api/__init__.py tests/api/test_screenshots.py
git commit -m "feat(api): add screenshot and visual-diff image endpoints"
```

---

## Task 12: Final Verification and README Update

**Files:**
- Modify: `README.md`
- Test: all tests

- [ ] **Step 1: Add visual diff section to README**

In `README.md`, add a "Visual diff" subsection under "What it does" or after "View diffs":

```markdown
### Visual diff

Enable screenshots per site to capture a full-page image on every check and generate a highlighted overlay when the page changes:

```bash
curl -X PUT http://localhost:8000/api/monitor/sites/1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"screenshot_enabled": true}'
```

After the next check, view the latest screenshot:

```bash
curl http://localhost:8000/api/monitor/sites/1/screenshots/<snapshot_id> \
  -H "Authorization: Bearer <token>" --output screenshot.png
```

And the visual diff overlay for any detected change:

```bash
curl http://localhost:8000/api/monitor/changes/<change_id>/visual-diff \
  -H "Authorization: Bearer <token>" --output diff.png
```
```

- [ ] **Step 2: Run the full test suite**

Run:

```bash
venv/bin/python -m pytest tests/ -v
```

Expected: all existing tests pass plus new visual-diff tests (baseline 94 + new tests).

- [ ] **Step 3: Run health check**

Run:

```bash
venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add visual diff usage instructions"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every requirement in `docs/superpowers/specs/2026-07-19-phase-2-visual-diff-design.md` has a corresponding task.
- [ ] **No placeholders:** No TBD/TODO/fill-in-details steps remain.
- [ ] **Type consistency:** `ScreenshotStorage`, `ScreenshotProvider`, `VisualDiffEngine`, and `VisualDiffResult` signatures match across all tasks.
- [ ] **Testability:** All external dependencies (Playwright, filesystem) are injectable or mocked in tests.
- [ ] **No breaking changes:** Existing API site endpoints still serialize correctly after adding `screenshot_enabled`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-phase-2-visual-diff-plan.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
