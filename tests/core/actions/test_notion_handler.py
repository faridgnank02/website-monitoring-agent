import json
import responses
from unittest.mock import patch

import requests

from core.actions.base import ActionContext, ProposedAction
from core.actions.handlers.notion import NotionActionHandler
from core.agents.events import ReportEvent
from core.security.site_encryption import encrypt_site_token


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


def test_notion_propose_skips_without_token():
    class NoTokenSite(FakeSite):
        notion_token = None

    handler = NotionActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=NoTokenSite(), report=report)) == []


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
    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["Authorization"] == "Bearer secret_abc123"
    assert responses.calls[0].request.headers["Notion-Version"] == "2022-06-28"
    body = json.loads(responses.calls[0].request.body)
    assert body["parent"]["database_id"] == "db-123"
    assert body["properties"]["title"]["title"][0]["text"]["content"] == "Price changed"


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
@patch("config.settings.SECRET_KEY", "test-master-secret-key")
def test_notion_execute_resolves_encrypted_token():
    plaintext = "encrypted-secret"
    encrypted = encrypt_site_token(1, plaintext)
    responses.add(
        responses.POST,
        "https://api.notion.com/v1/pages",
        status=200,
        json={"id": "page-enc"},
    )
    handler = NotionActionHandler()
    result = handler.execute(
        ProposedAction(
            type="notion", risk_score=0.3,
            payload={"token": encrypted, "site_id": 1, "database_id": "db-123", "title": "t"},
            description="Create Notion page",
        )
    )
    assert result.success is True
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {plaintext}"


@responses.activate
def test_notion_execute_network_error_does_not_leak_token():
    handler = NotionActionHandler()
    proposed = ProposedAction(
        type="notion", risk_score=0.3,
        payload={"token": "TOKEN_SECRET", "database_id": "db", "title": "t", "summary": "s"},
        description="Create Notion page",
    )
    with patch(
        "core.actions.handlers.notion.requests.post",
        side_effect=requests.ConnectionError("boom https://api.notion.com/v1/pages TOKEN_SECRET"),
    ):
        result = handler.execute(proposed)
    assert result.success is False
    assert "TOKEN_SECRET" not in result.message
    assert len(responses.calls) == 0
