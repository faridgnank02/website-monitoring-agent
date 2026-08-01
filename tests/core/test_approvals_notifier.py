import logging
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


def test_email_failure_returns_false_logs_warning(caplog):
    site = MonitorSite(id=1, user_id=1, instruction="test")
    notifier = ApprovalNotifier()
    with patch("core.approvals.notifier.GmailNotifier", autospec=True) as MockNotifier:
        MockNotifier.return_value.send_notification.return_value = False
        with patch("core.approvals.notifier.settings.GMAIL_RECIPIENT_EMAIL", "admin@example.com"):
            with caplog.at_level(logging.WARNING, logger="core.approvals.notifier"):
                notifier.notify_pending(site, [{"action_type": "slack", "risk_score": 0.9}])
    assert any("approval email notification failed" in r.message for r in caplog.records)
