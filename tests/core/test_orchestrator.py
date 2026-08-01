import hashlib
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
