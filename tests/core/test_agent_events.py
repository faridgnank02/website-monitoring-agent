from core.agents.events import ScoutEvent, AnalysisEvent, ReportEvent, ActionEvent


def test_scout_event_serialization():
    event = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        snapshot_id=10,
        url="https://example.com",
        entities=[{"name": "price", "value": "10"}],
    )
    data = event.model_dump()
    assert data["stage"] == "scout"
    assert data["has_change"] is True


def test_action_event_serializes_result():
    event = ActionEvent(
        run_id="r1",
        site_id=1,
        actions=[{"type": "email", "success": True}],
        approval_requests=[],
    )
    assert event.model_dump()["stage"] == "action"
