import responses

from core.actions.base import ActionContext, ProposedAction
from core.actions.handlers.notion import NotionActionHandler
from core.agents.events import ReportEvent


class FakeSite:
    id = 1
    actions_enabled = ["notion"]
    notion_token = "secret_abc123"
    url = "https://example.com"
    integration_config = {"notion": {"database_id": "db-123"}}


def _context():
    report = ReportEvent(
        run_id="r1", site_id=1, title="Price changed", summary="Price dropped",
    )
    return ActionContext(site=FakeSite(), report=report)


def test_notion_propose_returns_action_when_configured():
    handler = NotionActionHandler()
    proposals = handler.propose(_context())
    assert len(proposals) == 1
    assert proposals[0].payload["database_id"] == "db-123"
    assert proposals[0].payload["token"] == "secret_abc123"
    assert proposals[0].payload["site_id"] == 1


def test_notion_propose_skips_without_database_id():
    class NoDbSite(FakeSite):
        integration_config = {"notion": {}}

    handler = NotionActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=NoDbSite(), report=report)) == []


def test_notion_propose_skips_when_not_enabled():
    class DisabledSite(FakeSite):
        actions_enabled = []

    handler = NotionActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=DisabledSite(), report=report)) == []


@responses.activate
def test_notion_execute_creates_page():
    responses.add(
        responses.POST,
        "https://api.notion.com/v1/pages",
        status=200,
        json={"id": "page-999", "url": "https://notion.so/page-999"},
    )
    handler = NotionActionHandler()
    result = handler.execute(
        ProposedAction(
            type="notion", risk_score=0.3,
            payload={
                "token": "secret_abc123",
                "database_id": "db-123",
                "title": "Price changed",
                "summary": "Price dropped",
            },
            description="Create Notion page",
        )
    )
    assert result.success is True
    assert result.output["external_id"] == "page-999"
    assert responses.calls[0].request.headers["Authorization"] == "Bearer secret_abc123"
    assert responses.calls[0].request.headers["Notion-Version"] == "2022-06-28"


@responses.activate
def test_notion_execute_returns_failure_on_http_error():
    responses.add(responses.POST, "https://api.notion.com/v1/pages", status=400, body="bad request")
    handler = NotionActionHandler()
    result = handler.execute(
        ProposedAction(
            type="notion", risk_score=0.3,
            payload={"token": "t", "database_id": "db", "title": "t", "summary": "s"},
            description="Create Notion page",
        )
    )
    assert result.success is False


@responses.activate
def test_notion_execute_network_error_does_not_leak_token():
    import pytest
    from unittest.mock import patch
    import requests as _requests

    with patch("core.actions.handlers.notion.requests.post", side_effect=_requests.ConnectionError("boom https://api.notion.com/v1/pages TOKEN_SECRET")):
        handler = NotionActionHandler()
        result = handler.execute(
            ProposedAction(
                type="notion", risk_score=0.3,
                payload={"token": "TOKEN_SECRET", "database_id": "db", "title": "t", "summary": "s"},
                description="Create Notion page",
            )
        )
    assert result.success is False
    assert "TOKEN_SECRET" not in result.message
