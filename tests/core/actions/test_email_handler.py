from unittest.mock import patch

from core.actions.base import ActionContext, ProposedAction
from core.actions.handlers.email import EmailActionHandler
from core.agents.events import ReportEvent


class FakeSite:
    id = 1
    actions_enabled = ["email"]
    url = "https://example.com"
    instruction = "monitor prices"


def _context():
    report = ReportEvent(
        run_id="r1", site_id=1, title="Price changed",
        summary="Price dropped from 99 to 89",
    )
    return ActionContext(site=FakeSite(), report=report)


def test_email_propose_returns_action_when_enabled():
    handler = EmailActionHandler()
    proposals = handler.propose(_context())
    assert len(proposals) == 1
    assert proposals[0].type == "email"
    assert "subject" in proposals[0].payload
    assert "body" in proposals[0].payload


def test_email_propose_skips_when_not_enabled():
    class DisabledSite(FakeSite):
        actions_enabled = []

    handler = EmailActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    proposals = handler.propose(ActionContext(site=DisabledSite(), report=report))
    assert proposals == []


@patch("core.actions.handlers.email.GmailNotifier")
def test_email_execute_sends_via_gmail(mock_notifier):
    mock_notifier.return_value.send_notification.return_value = True
    handler = EmailActionHandler()
    result = handler.execute(
        ProposedAction(
            type="email", risk_score=0.1,
            payload={"subject": "Price changed", "body": "Price dropped", "url": "https://example.com"},
            description="Send email alert",
        )
    )
    assert result.success is True
    assert result.type == "email"
    mock_notifier.return_value.send_notification.assert_called_once()


@patch("core.actions.handlers.email.GmailNotifier")
def test_email_execute_returns_failure_on_exception(mock_notifier):
    mock_notifier.return_value.send_notification.side_effect = RuntimeError("SMTP down")
    handler = EmailActionHandler()
    result = handler.execute(
        ProposedAction(
            type="email", risk_score=0.1,
            payload={"subject": "t", "body": "b"},
            description="Send email alert",
        )
    )
    assert result.success is False
    assert "SMTP down" in result.message
