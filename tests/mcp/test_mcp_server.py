from mcp.main import app
from mcp.server import MCPServer
from mcp.tools import handler_to_tool
from mcp.auth import api_key_middleware
from mcp.transport import sse_router
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler


def test_mcp_package_imports():
    assert app is not None
    assert MCPServer is not None
    assert handler_to_tool is not None
    assert api_key_middleware is not None
    assert sse_router is not None


def test_list_tools_returns_all_six_handlers():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    registry.register(SlackActionHandler())
    registry.register(NotionActionHandler())
    registry.register(GitHubActionHandler())
    registry.register(N8NActionHandler())
    registry.register(WebhookActionHandler())

    server = MCPServer(registry)
    tools = server.list_tools()

    assert len(tools) == 6
    tool_names = {t["name"] for t in tools}
    assert tool_names == {"email", "slack", "notion", "github", "n8n", "webhook"}
    for tool in tools:
        assert "inputSchema" in tool
        assert "outputSchema" in tool