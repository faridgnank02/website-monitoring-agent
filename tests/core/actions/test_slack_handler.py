import responses
from unittest.mock import patch

import requests

from core.actions.base import ActionContext, ProposedAction
from core.actions.handlers.slack import SlackActionHandler
from core.agents.events import ReportEvent
from core.security.site_encryption import encrypt_site_token


class FakeSite:
    id = 1
    actions_enabled = ["slack"]
    slack_webhook = "https://hooks.slack.com/services/T000/B000/XXX"
    url = "https://example.com"


class FakeChange:
    change_score = 14.29
    severity = "high"


def _context(change=None):
    report = ReportEvent(
        run_id="r1", site_id=1, title="Price changed", summary="Price dropped",
    )
    return ActionContext(site=FakeSite(), report=report, change=change)


def test_slack_propose_returns_action_when_enabled_and_webhook_present():
    handler = SlackActionHandler()
    proposals = handler.propose(_context(change=FakeChange()))
    assert len(proposals) == 1
    assert proposals[0].payload["webhook"] == FakeSite.slack_webhook
    assert proposals[0].payload["change_score"] == 14.29
    assert proposals[0].payload["severity"] == "high"
    assert proposals[0].payload["url"] == "https://example.com"


def test_slack_propose_skips_without_webhook():
    class NoWebhookSite(FakeSite):
        slack_webhook = None

    handler = SlackActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=NoWebhookSite(), report=report)) == []


def test_slack_propose_skips_when_not_enabled():
    class DisabledSite(FakeSite):
        actions_enabled = []

    handler = SlackActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=DisabledSite(), report=report)) == []


@responses.activate
def test_slack_execute_posts_message():
    responses.add(
        responses.POST,
        "https://hooks.slack.com/services/T000/B000/XXX",
        status=200,
        json={"ok": True},
    )
    handler = SlackActionHandler()
    result = handler.execute(
        ProposedAction(
            type="slack", risk_score=0.4,
            payload={
                "webhook": "https://hooks.slack.com/services/T000/B000/XXX",
                "text": "Price dropped",
                "url": "https://example.com",
                "change_score": 14.29,
                "severity": "high",
            },
            description="Post to Slack",
        )
    )
    assert result.success is True
    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    assert b"Price dropped" in body
    assert b"14.29" in body
    assert b"https://example.com" in body


@responses.activate
def test_slack_execute_omits_score_and_link_when_absent():
    responses.add(
        responses.POST,
        "https://hooks.slack.com/services/T000/B000/XXX",
        status=200,
        json={"ok": True},
    )
    handler = SlackActionHandler()
    result = handler.execute(
        ProposedAction(
            type="slack", risk_score=0.4,
            payload={"webhook": "https://hooks.slack.com/services/T000/B000/XXX", "text": "Price dropped"},
            description="Post to Slack",
        )
    )
    assert result.success is True
    body = responses.calls[0].request.body
    assert b"Price dropped" in body
    assert b"Change score" not in body
    assert b"Site:" not in body


@responses.activate
def test_slack_execute_returns_failure_on_http_error():
    responses.add(
        responses.POST,
        "https://hooks.slack.com/services/T000/B000/XXX",
        status=500,
    )
    handler = SlackActionHandler()
    result = handler.execute(
        ProposedAction(
            type="slack", risk_score=0.4,
            payload={
                "webhook": "https://hooks.slack.com/services/T000/B000/XXX",
                "text": "Price dropped",
            },
            description="Post to Slack",
        )
    )
    assert result.success is False


@responses.activate
@patch("config.settings.SECRET_KEY", "test-master-secret-key")
def test_slack_execute_resolves_encrypted_webhook():
    webhook_url = "https://hooks.slack.com/services/T000/B000/SECRET"
    encrypted = encrypt_site_token(1, webhook_url)
    responses.add(
        responses.POST,
        webhook_url,
        status=200,
        json={"ok": True},
    )
    handler = SlackActionHandler()
    result = handler.execute(
        ProposedAction(
            type="slack", risk_score=0.4,
            payload={
                "webhook": encrypted,
                "text": "Price dropped",
                "site_id": 1,
            },
            description="Post to Slack",
        )
    )
    assert result.success is True
    assert responses.calls[0].request.url == webhook_url


def test_slack_execute_network_error_does_not_leak_webhook():
    handler = SlackActionHandler()
    proposed = ProposedAction(
        type="slack", risk_score=0.4,
        payload={
            "webhook": "https://hooks.slack.com/services/T000/B000/SECRET",
            "text": "Price dropped",
        },
        description="Post to Slack",
    )
    with patch(
        "core.actions.handlers.slack.requests.post",
        side_effect=requests.ConnectionError(
            "boom https://hooks.slack.com/services/T000/B000/SECRET"
        ),
    ):
        result = handler.execute(proposed)
    assert result.success is False
    assert "hooks.slack.com" not in result.message


@responses.activate
def test_slack_execute_omits_score_when_change_score_zero():
    responses.add(
        responses.POST,
        "https://hooks.slack.com/services/T000/B000/XXX",
        status=200,
        json={"ok": True},
    )
    handler = SlackActionHandler()
    result = handler.execute(
        ProposedAction(
            type="slack", risk_score=0.4,
            payload={
                "webhook": "https://hooks.slack.com/services/T000/B000/XXX",
                "text": "Price dropped",
                "change_score": 0.0,
                "severity": "low",
            },
            description="Post to Slack",
        )
    )
    assert result.success is True
    body = responses.calls[0].request.body
    assert b"Price dropped" in body
    assert b"Change score:" not in body
