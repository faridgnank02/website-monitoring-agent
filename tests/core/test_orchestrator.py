import hashlib
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session

from core.orchestrator import MonitoringOrchestrator
from core.agents.events import ScoutEvent
from core.visual.diff import VisualDiffEngine
from core.visual.screenshot import StaticScreenshotProvider
from core.visual.storage import ScreenshotStorage
from db.models import MonitorSite, MonitorSnapshot, MonitorChange, User


def test_orchestrator_runs_pipeline():
    db = MagicMock(spec=Session)
    site = MonitorSite(
        id=1, user_id=1, instruction="test", threshold=1.0, approval_policy="auto"
    )
    site.url = "https://example.com"

    orch = MonitoringOrchestrator(db)
    with patch.object(orch, "_latest_snapshot", return_value=None), patch.object(
        orch.scout,
        "run",
        return_value=ScoutEvent(
            run_id="r1",
            site_id=1,
            has_change=False,
            url="https://example.com",
            content_markdown="",
            content_hash="abc",
            entities=[],
        ),
    ):
        result = orch.run(site)

    assert result["success"] is True
    assert result["change_detected"] is False


def test_orchestrator_first_run_no_change_detected():
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    site = MagicMock()
    site.id = 1
    site.instruction = "Monitor https://example.com"
    site.url = None
    site.threshold = 1.0
    site.active = True
    site.user_id = 1

    with patch("core.orchestrator.LLMRouter") as mock_llm_router, \
         patch("core.orchestrator.parse_instruction") as mock_parse, \
         patch("core.orchestrator.scrape_url") as mock_scrape:
        mock_llm_router.return_value = MagicMock()
        mock_parse.return_value = MagicMock(success=True, url="https://example.com", error=None)
        mock_scrape.return_value = MagicMock(success=True, markdown="Hello", html="", metadata={}, error=None)
        orch = MonitoringOrchestrator(db)
        result = orch.run(site)

    assert result["success"] is True
    assert result["change_detected"] is False
    assert result["change_score"] == 0.0


def test_orchestrator_identical_content_no_change():
    db = MagicMock(spec=Session)
    previous = MagicMock()
    previous.content_hash = hashlib.md5(b"Hello").hexdigest()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

    site = MagicMock()
    site.id = 1
    site.instruction = "Monitor https://example.com"
    site.url = "https://example.com"
    site.threshold = 1.0
    site.active = True
    site.user_id = 1

    with patch("core.orchestrator.LLMRouter") as mock_llm_router, \
         patch("core.orchestrator.parse_instruction") as mock_parse, \
         patch("core.orchestrator.scrape_url") as mock_scrape:
        mock_llm_router.return_value = MagicMock()
        mock_parse.return_value = MagicMock(success=True, url="https://example.com", error=None)
        mock_scrape.return_value = MagicMock(success=True, markdown="Hello", html="", metadata={}, error=None)
        orch = MonitoringOrchestrator(db)
        result = orch.run(site)

    assert result["success"] is True
    assert result["change_detected"] is False


def test_orchestrator_scrape_failure_returns_error():
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    site = MagicMock()
    site.id = 1
    site.instruction = "Monitor https://example.com"
    site.url = None
    site.threshold = 1.0
    site.active = True
    site.user_id = 1

    with patch("core.orchestrator.LLMRouter") as mock_llm_router, \
         patch("core.orchestrator.parse_instruction") as mock_parse, \
         patch("core.orchestrator.scrape_url") as mock_scrape:
        mock_llm_router.return_value = MagicMock()
        mock_parse.return_value = MagicMock(success=True, url="https://example.com", error=None)
        mock_scrape.return_value = MagicMock(success=False, markdown="", html="", metadata={}, error="Connection failed")
        orch = MonitoringOrchestrator(db)
        result = orch.run(site)

    assert result["success"] is False
    assert "Connection failed" in result["error"]


def test_orchestrator_parse_instruction_failure_returns_error():
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    site = MagicMock()
    site.id = 1
    site.instruction = "bad instruction"
    site.url = None
    site.threshold = 1.0
    site.active = True
    site.user_id = 1

    with patch("core.orchestrator.LLMRouter") as mock_llm_router, \
         patch("core.orchestrator.parse_instruction") as mock_parse, \
         patch("core.orchestrator.scrape_url") as mock_scrape:
        mock_llm_router.return_value = MagicMock()
        mock_parse.return_value = MagicMock(success=False, url="", error="Could not parse instruction")
        mock_scrape.return_value = MagicMock(success=True, markdown="", html="", metadata={}, error=None)
        orch = MonitoringOrchestrator(db)
        result = orch.run(site)

    assert result["success"] is False
    assert "Could not parse instruction" in result["error"]


class _MemoryStorage(ScreenshotStorage):
    def __init__(self):
        self._data: dict[str, bytes] = {}

    def save_snapshot(self, site_id: int, snapshot_id: int, data: bytes) -> str:
        key = f"site_{site_id}/snap_{snapshot_id}.png"
        self._data[key] = data
        return key

    def load_snapshot(self, site_id: int, snapshot_id: int) -> Optional[bytes]:
        return self._data.get(f"site_{site_id}/snap_{snapshot_id}.png")

    def save_diff(self, site_id: int, change_id: int, data: bytes) -> str:
        key = f"site_{site_id}/diff_{change_id}.png"
        self._data[key] = data
        return key

    def load_diff(self, site_id: int, change_id: int) -> Optional[bytes]:
        return self._data.get(f"site_{site_id}/diff_{change_id}.png")

    def exists(self, relative_path: str) -> bool:
        return relative_path in self._data

    def load(self, relative_path: str) -> Optional[bytes]:
        return self._data.get(relative_path)


def _parsed_instruction():
    return MagicMock(success=True, url="https://example.com", error=None)


def _scraped_content(markdown: str):
    return MagicMock(
        success=True, markdown=markdown, html="", metadata={}, error=None
    )


@pytest.fixture
def screenshot_site(db: Session):
    user = User(email="screenshot@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    site = MonitorSite(
        user_id=user.id,
        instruction="monitor https://example.com",
        url="https://example.com",
        threshold=1.0,
        screenshot_enabled=True,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def test_orchestrator_persists_screenshot_and_diff(db: Session, screenshot_site):
    storage = _MemoryStorage()
    provider = StaticScreenshotProvider(width=20, height=20, color=(0, 0, 0))

    with patch("core.orchestrator.parse_instruction", return_value=_parsed_instruction()), \
         patch("core.orchestrator.scrape_url", return_value=_scraped_content("first")):
        orchestrator = MonitoringOrchestrator(
            db=db,
            screenshot_provider=provider,
            screenshot_storage=storage,
            visual_diff_engine=VisualDiffEngine(),
        )
        result1 = orchestrator.run(screenshot_site)

    assert result1["success"] is True
    assert result1["change_detected"] is False

    snapshots = db.query(MonitorSnapshot).filter(MonitorSnapshot.site_id == screenshot_site.id).all()
    assert len(snapshots) == 1
    first_snapshot = snapshots[0]
    assert first_snapshot.screenshot_path is not None
    assert storage.load(first_snapshot.screenshot_path) is not None

    provider2 = StaticScreenshotProvider(width=20, height=20, color=(255, 255, 255))

    with patch("core.orchestrator.parse_instruction", return_value=_parsed_instruction()), \
         patch("core.orchestrator.scrape_url", return_value=_scraped_content("second")):
        orchestrator2 = MonitoringOrchestrator(
            db=db,
            screenshot_provider=provider2,
            screenshot_storage=storage,
            visual_diff_engine=VisualDiffEngine(),
        )
        result2 = orchestrator2.run(screenshot_site)

    assert result2["success"] is True
    assert result2["change_detected"] is True

    changes = db.query(MonitorChange).filter(MonitorChange.site_id == screenshot_site.id).all()
    assert len(changes) == 1
    change = changes[0]
    assert change.visual_diff_path is not None
    assert storage.load(change.visual_diff_path) is not None


def test_orchestrator_skips_screenshot_when_disabled(db: Session, screenshot_site):
    screenshot_site.screenshot_enabled = False
    db.commit()

    storage = _MemoryStorage()
    provider = StaticScreenshotProvider(width=20, height=20, color=(0, 0, 0))

    with patch("core.orchestrator.parse_instruction", return_value=_parsed_instruction()), \
         patch("core.orchestrator.scrape_url", return_value=_scraped_content("only")):
        orchestrator = MonitoringOrchestrator(
            db=db,
            screenshot_provider=provider,
            screenshot_storage=storage,
        )
        result = orchestrator.run(screenshot_site)

    assert result["success"] is True

    snapshots = db.query(MonitorSnapshot).filter(MonitorSnapshot.site_id == screenshot_site.id).all()
    assert len(snapshots) == 1
    assert snapshots[0].screenshot_path is None
