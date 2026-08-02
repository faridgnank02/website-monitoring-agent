from unittest.mock import MagicMock
from core.agents.action import ActionAgent
from core.agents.events import ReportEvent
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from db.models import MonitorSite


def test_action_agent_proposes_email():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    agent = ActionAgent(registry)

    site = MonitorSite(id=1, user_id=1, instruction="test", threshold=1.0, approval_policy="auto")
    report = ReportEvent(run_id="r1", site_id=1, title="Change", summary="Price dropped", recommended_actions=[])

    event = agent.run(report, site)
    assert len(event.actions) == 1
    assert event.actions[0]["type"] == "email"
    assert event.approval_requests == []


def test_action_agent_creates_approval_for_high_risk():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    agent = ActionAgent(registry)

    site = MonitorSite(id=1, user_id=1, instruction="test", threshold=1.0, approval_policy="always")
    report = ReportEvent(run_id="r1", site_id=1, title="Change", summary="Price dropped", recommended_actions=[])

    event = agent.run(report, site)
    assert len(event.approval_requests) == 1
