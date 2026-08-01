import json
from unittest.mock import patch

import responses

from core.actions.base import ActionContext, ProposedAction
from core.actions.handlers.github import GitHubActionHandler
from core.agents.events import ReportEvent
from core.security.site_encryption import encrypt_site_token


class FakeSite:
    id = 1
    actions_enabled = ["github"]
    github_token = "ghp_abc123"
    url = "https://example.com"
    integration_config = {"github": {"repo": "acme/monitor", "create_pr": False}}


def _context():
    report = ReportEvent(
        run_id="r1", site_id=1, title="Price changed", summary="Price dropped",
    )
    return ActionContext(site=FakeSite(), report=report)


def test_github_propose_returns_action_when_configured():
    handler = GitHubActionHandler()
    proposals = handler.propose(_context())
    assert len(proposals) == 1
    assert proposals[0].payload["repo"] == "acme/monitor"
    assert proposals[0].payload["token"] == "ghp_abc123"
    assert proposals[0].payload["site_id"] == 1


def test_github_propose_skips_without_repo():
    class NoRepoSite(FakeSite):
        integration_config = {"github": {}}

    handler = GitHubActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=NoRepoSite(), report=report)) == []


def test_github_propose_skips_when_not_enabled():
    class DisabledSite(FakeSite):
        actions_enabled = []

    handler = GitHubActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=DisabledSite(), report=report)) == []


def test_github_propose_skips_without_token():
    class NoTokenSite(FakeSite):
        github_token = None

    handler = GitHubActionHandler()
    report = ReportEvent(run_id="r1", site_id=1, title="t", summary="s")
    assert handler.propose(ActionContext(site=NoTokenSite(), report=report)) == []


@responses.activate
def test_github_execute_creates_issue():
    responses.add(
        responses.POST,
        "https://api.github.com/repos/acme/monitor/issues",
        status=201,
        json={"number": 42, "html_url": "https://github.com/acme/monitor/issues/42"},
    )
    handler = GitHubActionHandler()
    result = handler.execute(
        ProposedAction(
            type="github", risk_score=0.5,
            payload={
                "token": "ghp_abc123",
                "repo": "acme/monitor",
                "title": "Price changed",
                "body": "Price dropped",
            },
            description="Create GitHub issue",
        )
    )
    assert result.success is True
    assert result.output["external_id"] == "42"
    assert responses.calls[0].request.headers["Authorization"] == "Bearer ghp_abc123"
    body = json.loads(responses.calls[0].request.body)
    assert body["title"] == "Price changed"
    assert body["body"] == "Price dropped"


@responses.activate
def test_github_execute_returns_failure_on_http_error():
    responses.add(
        responses.POST,
        "https://api.github.com/repos/acme/monitor/issues",
        status=401,
    )
    handler = GitHubActionHandler()
    result = handler.execute(
        ProposedAction(
            type="github", risk_score=0.5,
            payload={"token": "t", "repo": "acme/monitor", "title": "t", "body": "b"},
            description="Create GitHub issue",
        )
    )
    assert result.success is False
    assert "ghp" not in result.message


@responses.activate
def test_github_execute_network_error_does_not_leak_token():
    import requests as _requests

    with patch(
        "core.actions.handlers.github.requests.post",
        side_effect=_requests.ConnectionError("boom https://api.github.com GHP_SECRET"),
    ):
        handler = GitHubActionHandler()
        result = handler.execute(
            ProposedAction(
                type="github", risk_score=0.5,
                payload={"token": "GHP_SECRET", "repo": "acme/monitor", "title": "t", "body": "b"},
                description="Create GitHub issue",
            )
        )
    assert result.success is False
    assert len(responses.calls) == 0
    assert "GHP_SECRET" not in result.message


@responses.activate
@patch("config.settings.SECRET_KEY", "test-master-secret-key")
def test_github_execute_resolves_encrypted_token():
    plaintext = "ghp_encrypted"
    encrypted = encrypt_site_token(1, plaintext)
    responses.add(
        responses.POST,
        "https://api.github.com/repos/acme/monitor/issues",
        status=201,
        json={"number": 7},
    )
    handler = GitHubActionHandler()
    result = handler.execute(
        ProposedAction(
            type="github", risk_score=0.5,
            payload={"token": encrypted, "site_id": 1, "repo": "acme/monitor", "title": "t"},
            description="Create GitHub issue",
        )
    )
    assert result.success is True
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {plaintext}"
