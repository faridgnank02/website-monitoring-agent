from unittest.mock import patch

from core.approvals.notifier import ApprovalNotifier
from db.models import MonitorSite


def test_skips_when_no_destinations_configured():
    site = MonitorSite(id=1, user_id=1, instruction="test", slack_webhook="")
    notifier = ApprovalNotifier()
    notifier.notify_pending(site, [])
    assert True  # no exceptions


def test_email_sent_when_recipient_configured():
    site = MonitorSite(id=1, user_id=1, instruction="test")
    notifier = ApprovalNotifier()
    with patch(
        "core.approvals.notifier.GmailNotifier",
        autospec=True,
    ) as MockNotifier:
        instance = MockNotifier.return_value
        with patch("core.approvals.notifier.settings.GMAIL_RECIPIENT_EMAIL", "admin@example.com"):
            notifier.notify_pending(site, [{"action_type": "slack", "risk_score": 0.9}])
    assert instance.send_notification.called


def test_never_raises_when_email_fails():
    site = MonitorSite(id=1, user_id=1, instruction="test")
    notifier = ApprovalNotifier()
    with patch("core.approvals.notifier.GmailNotifier", side_effect=RuntimeError("smtp down")):
        with patch("core.approvals.notifier.settings.GMAIL_RECIPIENT_EMAIL", "admin@example.com"):
            notifier.notify_pending(site, [{"action_type": "slack", "risk_score": 0.9}])
    assert True
