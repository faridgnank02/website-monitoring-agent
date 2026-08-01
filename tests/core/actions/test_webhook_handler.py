import hashlib
import hmac
import json

import responses

from core.actions.base import ActionContext, ProposedAction
from core.actions.handlers.webhook import WebhookActionHandler
from core.agents.events import ReportEvent


class FakeSite:
    id = 1
    actions_enabled = ["webhook"]
    url = "https://example.com"
    integration_config = {"webhook": {"url": "https://example.com/hooks/monitor", "secret": "shared-secret"}}


def _context():
    report = ReportEvent(
        run_id="r1", site_id=1, title="Price changed", summary="Price dropped",
    )
    return ActionContext(site=FakeSite(), report=report)


def test_webhook_propose_returns_action_when_configured():
    handler = WebhookActionHandler()
    proposals = handler.propose(_context())
    assert len(proposals) == 1
    assert proposals[0].payload["url"] == "https://example.com/hooks/monitor"
    assert proposals[0].payload["secret"] == "shared-secret"
    assert proposals[0].payload["site_id"] == 1


def test_webhook_propose_skips_without_url():
    class NoUrlSite(FakeSite):
        integration_config = {"webhook": {}}

    handler = WebhookActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=NoUrlSite(), report=report)) == []


def test_webhook_propose_skips_when_not_enabled():
    class DisabledSite(FakeSite):
        actions_enabled = []

    handler = WebhookActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=DisabledSite(), report=report)) == []


@responses.activate
def test_webhook_execute_posts_payload():
    responses.add(responses.POST, "https://example.com/hooks/monitor", status=200)
    handler = WebhookActionHandler()
    result = handler.execute(
        ProposedAction(
            type="webhook", risk_score=0.2,
            payload={"url": "https://example.com/hooks/monitor", "secret": "", "site_id": 1},
            description="POST to webhook",
        )
    )
    assert result.success is True
    body = json.loads(responses.calls[0].request.body)
    assert body["event"] == "monitor_change"
    assert body["site_id"] == 1
    assert len(responses.calls) == 1


@responses.activate
def test_webhook_execute_signs_with_hmac():
    responses.add(responses.POST, "https://example.com/hooks/monitor", status=200)
    handler = WebhookActionHandler()
    secret = "shared-secret"
    result = handler.execute(
        ProposedAction(
            type="webhook", risk_score=0.2,
            payload={
                "url": "https://example.com/hooks/monitor",
                "secret": secret,
                "site_id": 1,
            },
            description="POST to webhook",
        )
    )
    assert result.success is True
    request = responses.calls[0].request
    raw_body = request.body
    if isinstance(raw_body, bytes):
        raw_body = raw_body.decode("utf-8")
    expected = hmac.new(secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
    assert request.headers["X-Signature"] == f"sha256={expected}"


@responses.activate
def test_webhook_execute_returns_failure_on_http_error():
    responses.add(responses.POST, "https://example.com/hooks/monitor", status=500)
    handler = WebhookActionHandler()
    result = handler.execute(
        ProposedAction(
            type="webhook", risk_score=0.2,
            payload={"url": "https://example.com/hooks/monitor", "secret": "", "site_id": 1},
            description="POST to webhook",
        )
    )
    assert result.success is False


@responses.activate
def test_webhook_execute_network_error_does_not_leak_secret():
    from unittest.mock import patch
    import requests as _requests

    with patch(
        "core.actions.handlers.webhook.requests.post",
        side_effect=_requests.ConnectionError("boom https://example.com/hooks/monitor SECRET_XYZ"),
    ):
        handler = WebhookActionHandler()
        result = handler.execute(
            ProposedAction(
                type="webhook", risk_score=0.2,
                payload={"url": "https://example.com/hooks/monitor", "secret": "SECRET_XYZ", "site_id": 1},
                description="POST to webhook",
            )
        )
    assert result.success is False
    assert len(responses.calls) == 0
    assert "SECRET_XYZ" not in result.message
