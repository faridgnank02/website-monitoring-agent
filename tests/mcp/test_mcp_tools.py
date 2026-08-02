from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler


def test_email_handler_has_input_schema():
    handler = EmailActionHandler()
    schema = handler.input_schema()
    assert schema["type"] == "object"
    assert "payload" in schema["properties"]
    assert schema["required"] == ["payload"]


def test_email_handler_has_output_schema():
    handler = EmailActionHandler()
    schema = handler.output_schema()
    assert schema["type"] == "object"
    assert "success" in schema["properties"]
    assert "message" in schema["properties"]
    assert "output" in schema["properties"]


def test_notion_handler_execute_handles_missing_proposal():
    handler = NotionActionHandler()
    assert handler.name == "notion"
    result = handler.execute(None)
    assert result.success is False


def test_github_handler_execute_handles_missing_proposal():
    handler = GitHubActionHandler()
    assert handler.name == "github"
    result = handler.execute(None)
    assert result.success is False


def test_n8n_handler_execute_handles_missing_proposal():
    handler = N8NActionHandler()
    assert handler.name == "n8n"
    result = handler.execute(None)
    assert result.success is False


def test_webhook_handler_execute_handles_missing_proposal():
    handler = WebhookActionHandler()
    assert handler.name == "webhook"
    result = handler.execute(None)
    assert result.success is False