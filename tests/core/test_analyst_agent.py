from typing import Optional
from unittest.mock import MagicMock, patch
from core.agents.analyst import AnalystAgent, _parse_price
from core.agents.events import ScoutEvent, AnalysisEvent
from core.entities.models import CorrelatedEntity, Entity
from core.visual.diff import VisualDiffEngine
from core.visual.screenshot import StaticScreenshotProvider
from core.visual.storage import ScreenshotStorage
from db.models import MonitorSnapshot
from src.modules.content_comparator import ComparisonResult


def test_analyst_classifies_price_drop():
    llm_router = MagicMock()
    agent = AnalystAgent(llm_router=llm_router)

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $17.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="17.99", unit="USD")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[Entity(entity_id="t-shirt", name="T-Shirt", value="17.99", unit="USD")]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=2.0,
            added_lines=[],
            removed_lines=[],
            modified_lines=[("T-Shirt $19.99", "T-Shirt $17.99")],
            diff_summary="Price changed",
            total_lines_old=1,
            total_lines_new=1,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "price_drop"
    assert result.severity == "high"
    assert result.correlated_entities[0].changed is True


def test_analyst_classifies_new_product():
    llm_router = MagicMock()
    agent = AnalystAgent(llm_router=llm_router)

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $19.99\nJeans $49.99"
    new_snap.extracted_entities = [
        Entity(entity_id="t-shirt", name="T-Shirt", value="19.99"),
        Entity(entity_id="jeans", name="Jeans", value="49.99"),
    ]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[Entity(entity_id="jeans", name="Jeans", value="49.99")]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=0.5,
            added_lines=["Jeans $49.99"],
            removed_lines=[],
            modified_lines=[],
            diff_summary="Added Jeans",
            total_lines_old=1,
            total_lines_new=2,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "new_product"


def test_no_old_snapshot_returns_no_change():
    agent = AnalystAgent(llm_router=MagicMock())
    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com", entities=[]
    )
    new_snap = MagicMock()
    new_snap.content_markdown = "content"
    new_snap.extracted_entities = []

    result = agent.run(scout, None, new_snap)

    assert result.has_change is False
    assert result.change_type == "content_update"
    assert result.severity == "low"


def test_no_changes_returns_content_update_low_severity():
    agent = AnalystAgent(llm_router=MagicMock())

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $19.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com", entities=[]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=False,
            change_score=0.0,
            added_lines=[],
            removed_lines=[],
            modified_lines=[],
            diff_summary="No changes",
            total_lines_old=1,
            total_lines_new=1,
            hash_old="old",
            hash_new="old",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.has_change is False
    assert result.change_type == "content_update"
    assert result.severity == "low"


def test_price_rise():
    agent = AnalystAgent(llm_router=MagicMock())

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $22.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="22.99", unit="USD")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[Entity(entity_id="t-shirt", name="T-Shirt", value="22.99", unit="USD")]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=2.0,
            added_lines=[],
            removed_lines=[],
            modified_lines=[("T-Shirt $19.99", "T-Shirt $22.99")],
            diff_summary="Price changed",
            total_lines_old=1,
            total_lines_new=1,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "price_rise"
    assert result.severity == "high"


def test_dict_entities_from_db_json():
    agent = AnalystAgent(llm_router=MagicMock())

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = {"entities": [{"entity_id": "t-shirt", "name": "T-Shirt", "value": "19.99", "unit": "USD"}]}

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $17.99"
    new_snap.extracted_entities = {"entities": [{"entity_id": "t-shirt", "name": "T-Shirt", "value": "17.99", "unit": "USD"}]}

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[{"entity_id": "t-shirt", "name": "T-Shirt", "value": "17.99", "unit": "USD"}]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=2.0,
            added_lines=[],
            removed_lines=[],
            modified_lines=[("T-Shirt $19.99", "T-Shirt $17.99")],
            diff_summary="Price changed",
            total_lines_old=1,
            total_lines_new=1,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "price_drop"


def test_removed_entity():
    agent = AnalystAgent(llm_router=MagicMock())

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99\nJeans $49.99"
    old_snap.extracted_entities = [
        Entity(entity_id="t-shirt", name="T-Shirt", value="19.99"),
        Entity(entity_id="jeans", name="Jeans", value="49.99"),
    ]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $19.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com", entities=[]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=0.5,
            added_lines=[],
            removed_lines=["Jeans $49.99"],
            modified_lines=[],
            diff_summary="Removed Jeans",
            total_lines_old=2,
            total_lines_new=1,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "content_update"


def test_parse_price_handles_malformed_and_european():
    assert _parse_price("$.") is None
    assert _parse_price("$1.2.3") is None
    assert _parse_price("19,99 EUR") == 1999.0
    assert _parse_price("$1,234.56") == 1234.56


def test_price_drop_with_malformed_price_continues():
    agent = AnalystAgent(llm_router=MagicMock())
    correlated = [
        CorrelatedEntity(
            entity_id="p",
            name="price",
            old_value="N/A",
            new_value="$.",
            changed=True,
            status="changed",
        )
    ]
    comparison = MagicMock()
    assert agent._classify_change(correlated, comparison) == "content_update"


class _MemoryStorage(ScreenshotStorage):
    def __init__(self):
        self._data: dict[str, bytes] = {}

    def save(self, relative_path: str, data: bytes) -> str:
        self._data[relative_path] = data
        return relative_path

    def load(self, relative_path: str) -> bytes:
        return self._data[relative_path]

    def delete(self, relative_path: str) -> None:
        self._data.pop(relative_path, None)

    def save_snapshot(self, site_id: int, snapshot_id: int, data: bytes) -> str:
        path = f"{site_id}/{snapshot_id}.png"
        self._data[path] = data
        return path

    def load_snapshot(self, site_id: int, snapshot_id: int) -> Optional[bytes]:
        return self._data.get(f"{site_id}/{snapshot_id}.png")

    def save_diff(self, site_id: int, change_id: int, data: bytes) -> str:
        path = f"{site_id}/diffs/{change_id}.png"
        self._data[path] = data
        return path

    def load_diff(self, site_id: int, change_id: int) -> Optional[bytes]:
        return self._data.get(f"{site_id}/diffs/{change_id}.png")

    def exists(self, relative_path: str) -> bool:
        return relative_path in self._data


def test_analyst_computes_visual_diff_when_screenshots_available():
    storage = _MemoryStorage()
    white = StaticScreenshotProvider(width=10, height=10, color=(255, 255, 255))
    black = StaticScreenshotProvider(width=10, height=10, color=(0, 0, 0))
    old_path = storage.save_snapshot(1, 1, white.capture("https://example.com"))
    new_path = storage.save_snapshot(1, 2, black.capture("https://example.com"))

    old_snapshot = MonitorSnapshot(
        id=1, site_id=1, content_markdown="old", content_hash="old",
        extracted_entities=[], screenshot_path=old_path,
    )
    new_snapshot = MonitorSnapshot(
        id=2, site_id=1, content_markdown="new", content_hash="new",
        extracted_entities=[], screenshot_path=new_path,
    )

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        content_markdown="new", content_hash="new",
    )

    agent = AnalystAgent(
        visual_diff_engine=VisualDiffEngine(),
        screenshot_storage=storage,
    )
    event = agent.run(scout, old_snapshot, new_snapshot)

    assert event.has_change is True
    assert event.visual_diff_bytes is not None
    assert event.visual_diff_score is not None
    assert event.visual_diff_score >= 0.0
    assert event.vision_description is not None


def test_analyst_skips_visual_diff_when_old_screenshot_missing():
    storage = _MemoryStorage()
    black = StaticScreenshotProvider(width=10, height=10, color=(0, 0, 0))
    new_path = storage.save_snapshot(1, 2, black.capture("https://example.com"))

    old_snapshot = MonitorSnapshot(
        id=1, site_id=1, content_markdown="old", content_hash="old",
        extracted_entities=[], screenshot_path=None,
    )
    new_snapshot = MonitorSnapshot(
        id=2, site_id=1, content_markdown="new", content_hash="new",
        extracted_entities=[], screenshot_path=new_path,
    )

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        content_markdown="new", content_hash="new",
    )

    agent = AnalystAgent(
        visual_diff_engine=VisualDiffEngine(),
        screenshot_storage=storage,
    )
    event = agent.run(scout, old_snapshot, new_snapshot)

    assert event.has_change is True
    assert event.visual_diff_bytes is None


def test_analyst_skips_visual_diff_when_engine_missing():
    storage = _MemoryStorage()
    white = StaticScreenshotProvider(width=10, height=10, color=(255, 255, 255))
    black = StaticScreenshotProvider(width=10, height=10, color=(0, 0, 0))
    old_path = storage.save_snapshot(1, 1, white.capture("https://example.com"))
    new_path = storage.save_snapshot(1, 2, black.capture("https://example.com"))

    old_snapshot = MonitorSnapshot(
        id=1, site_id=1, content_markdown="old", content_hash="old",
        extracted_entities=[], screenshot_path=old_path,
    )
    new_snapshot = MonitorSnapshot(
        id=2, site_id=1, content_markdown="new", content_hash="new",
        extracted_entities=[], screenshot_path=new_path,
    )

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        content_markdown="new", content_hash="new",
    )

    agent = AnalystAgent(screenshot_storage=storage)
    event = agent.run(scout, old_snapshot, new_snapshot)

    assert event.visual_diff_bytes is None
