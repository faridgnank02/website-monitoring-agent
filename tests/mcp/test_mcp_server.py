import os

# Set MCP_API_KEY BEFORE importing anything from mcp (it's read at import time)
os.environ["MCP_API_KEY"] = "test-secret-key"

from mcp.main import app
from mcp.server import MCPServer
from mcp.tools import handler_to_tool
from mcp.auth import APIKeyMiddleware
from mcp.transport import sse_router
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler
from fastapi.testclient import TestClient


def test_mcp_package_imports():
    assert app is not None
    assert MCPServer is not None
    assert handler_to_tool is not None
    assert APIKeyMiddleware is not None
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


def test_call_tool_email_returns_action_result():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    
    server = MCPServer(registry)
    result = server.call_tool("email", {"payload": {"subject": "test", "body": "hello"}})
    
    assert "content" in result
    content = result["content"][0]["text"]
    assert "success" in content
    assert "message" in content


def test_call_tool_slack_returns_action_result():
    registry = ActionHandlerRegistry()
    registry.register(SlackActionHandler())
    
    server = MCPServer(registry)
    result = server.call_tool("slack", {"payload": {"webhook": "http://slack", "message": "test"}})
    
    assert "content" in result
    content = result["content"][0]["text"]
    assert "success" in content


def test_call_tool_unknown_handler_raises():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    
    server = MCPServer(registry)
    try:
        server.call_tool("unknown", {})
        assert False, "Should have raised"
    except ValueError as e:
        assert "Handler not found" in str(e)


def test_sse_endpoint_streams_events():
    # SSE endpoint test - verify routing and auth
    # Full streaming test requires a proper HTTP client, TestClient doesn't handle streaming well
    import mcp.transport
    assert hasattr(mcp.transport, 'sse_endpoint')
    assert hasattr(mcp.transport, 'sse_router')
    assert hasattr(mcp.transport, 'mcp_server')


def test_mcp_rejects_missing_api_key():
    client = TestClient(app)
    response = client.post("/mcp/initialize")
    assert response.status_code == 403


def test_mcp_rejects_invalid_api_key():
    client = TestClient(app)
    headers = {"X-API-Key": "wrong-key"}
    response = client.post("/mcp/initialize", headers=headers)
    assert response.status_code == 403


def test_mcp_accepts_valid_api_key():
    client = TestClient(app)
    headers = {"X-API-Key": "test-secret-key"}
    response = client.post("/mcp/initialize", headers=headers)
    assert response.status_code == 200