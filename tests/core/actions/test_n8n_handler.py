import json
from unittest.mock import patch

import responses

from core.actions.base import ActionContext, ProposedAction
from core.actions.handlers.n8n import N8NActionHandler
from core.agents.events import ReportEvent


class FakeSite:
    id = 1
    actions_enabled = ["n8n"]
    url = "https://example.com"


def _context():
    report = ReportEvent(
        run_id="r1", site_id=1, title="Price changed", summary="Price dropped",
    )
    return ActionContext(site=FakeSite(), report=report)


def test_n8n_propose_returns_action_when_enabled(monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings, "N8N_WEBHOOK_URL", "http://localhost:5678/webhook/monitor")

    handler = N8NActionHandler()
    proposals = handler.propose(_context())
    assert len(proposals) == 1
    assert proposals[0].payload["url"] == "http://localhost:5678/webhook/monitor"
    assert proposals[0].payload["site_id"] == 1


def test_n8n_propose_skips_without_webhook_url(monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings, "N8N_WEBHOOK_URL", "")

    handler = N8NActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=FakeSite(), report=report)) == []


def test_n8n_propose_skips_when_not_enabled(monkeypatch):
    import config.settings as settings
    monkeypatch.setattr(settings, "N8N_WEBHOOK_URL", "http://localhost:5678/webhook/monitor")

    class DisabledSite(FakeSite):
        actions_enabled = []

    handler = N8NActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=DisabledSite(), report=report)) == []


@responses.activate
def test_n8n_execute_posts_full_payload():
    responses.add(
        responses.POST,
        "http://localhost:5678/webhook/monitor",
        status=200,
        json={"ok": True},
    )
    handler = N8NActionHandler()
    result = handler.execute(
        ProposedAction(
            type="n8n", risk_score=0.3,
            payload={
                "url": "http://localhost:5678/webhook/monitor",
                "site_id": 1,
                "title": "Price changed",
                "summary": "Price dropped",
                "change_score": 2.5,
                "severity": "high",
            },
            description="Send change payload to n8n",
        )
    )
    assert result.success is True
    body = json.loads(responses.calls[0].request.body)
    assert body["event"] == "monitor_change"
    assert body["site_id"] == 1
    assert body["change_score"] == 2.5
    assert body["severity"] == "high"
    assert len(responses.calls) == 1


@responses.activate
def test_n8n_execute_returns_failure_on_http_error():
    responses.add(responses.POST, "http://localhost:5678/webhook/monitor", status=500)
    handler = N8NActionHandler()
    result = handler.execute(
        ProposedAction(
            type="n8n", risk_score=0.3,
            payload={"url": "http://localhost:5678/webhook/monitor", "site_id": 1},
            description="Send change payload to n8n",
        )
    )
    assert result.success is False


@responses.activate
def test_n8n_execute_network_error_does_not_leak_url():
    import requests as _requests

    with patch(
        "core.actions.handlers.n8n.requests.post",
        side_effect=_requests.ConnectionError("boom http://localhost:5678/webhook/monitor TOKEN"),
    ):
        handler = N8NActionHandler()
        result = handler.execute(
            ProposedAction(
                type="n8n", risk_score=0.3,
                payload={"url": "http://localhost:5678/webhook/monitor", "site_id": 1},
                description="Send change payload to n8n",
            )
        )
    assert result.success is False
    assert len(responses.calls) == 0
    assert "http://localhost:5678" not in result.message
