from core.agents.events import ScoutEvent, AnalysisEvent, ReportEvent, ActionEvent
from core.entities.models import Entity, CorrelatedEntity


def test_scout_event_serialization():
    event = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        snapshot_id=10,
        url="https://example.com",
        entities=[Entity(entity_id="p1", name="price", value="10")],
    )
    data = event.model_dump()
    assert data["stage"] == "scout"
    assert data["has_change"] is True


def test_scout_event_carries_entities():
    event = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        url="https://example.com",
        entities=[Entity(entity_id="p1", name="Shirt", value="10")],
    )
    assert event.entities[0].name == "Shirt"


def test_analysis_event_carries_correlated_entities():
    event = AnalysisEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        correlated_entities=[
            CorrelatedEntity(entity_id="p1", name="Shirt", old_value="10", new_value="12", changed=True)
        ],
    )
    assert event.correlated_entities[0].changed is True


def test_action_event_serializes_result():
    event = ActionEvent(
        run_id="r1",
        site_id=1,
        actions=[{"type": "email", "success": True}],
        approval_requests=[],
    )
    assert event.model_dump()["stage"] == "action"


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


def test_screenshot_bytes_survives_serialization_roundtrip():
    event = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        url="https://example.com",
        screenshot_bytes=b"pngdata",
    )
    data = event.model_dump(mode="json")
    assert isinstance(data["screenshot_bytes"], str)
    restored = ScoutEvent(**data)
    assert restored.screenshot_bytes == b"pngdata"


def test_visual_diff_bytes_survives_serialization_roundtrip():
    event = AnalysisEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        visual_diff_bytes=b"diffpng",
    )
    data = event.model_dump(mode="json")
    assert isinstance(data["visual_diff_bytes"], str)
    restored = AnalysisEvent(**data)
    assert restored.visual_diff_bytes == b"diffpng"
