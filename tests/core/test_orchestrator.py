from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from core.orchestrator import MonitoringOrchestrator
from core.agents.events import ScoutEvent
from db.models import MonitorSite


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
