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
from db.base import SessionLocal, init_db
from db.models import User, MonitorSite


def get_test_db():
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "mcp-test@example.com").first()
        if not user:
            user = User(email="mcp-test@example.com", hashed_password="test")
            db.add(user)
            db.commit()
            db.refresh(user)
        site = db.query(MonitorSite).filter(MonitorSite.user_id == user.id).first()
        if not site:
            site = MonitorSite(
                user_id=user.id,
                instruction="test",
                threshold=1.0,
                approval_policy="never",
            )
            db.add(site)
            db.commit()
            db.refresh(site)
        yield db, site.id
    finally:
        db.close()


def test_mcp_package_imports():
    assert app is not None
    assert MCPServer is not None
    assert handler_to_tool is not None
    assert APIKeyMiddleware is not None
    assert sse_router is not None


def test_list_tools_returns_all_six_handlers():
    db_gen = get_test_db()
    db, site_id = next(db_gen)
    try:
        registry = ActionHandlerRegistry()
        registry.register(EmailActionHandler())
        registry.register(SlackActionHandler())
        registry.register(NotionActionHandler())
        registry.register(GitHubActionHandler())
        registry.register(N8NActionHandler())
        registry.register(WebhookActionHandler())

        server = MCPServer(registry, db)
        tools = server.list_tools()

        assert len(tools) == 6
        tool_names = {t["name"] for t in tools}
        assert tool_names == {"email", "slack", "notion", "github", "n8n", "webhook"}
        for tool in tools:
            assert "inputSchema" in tool
            assert "outputSchema" in tool
    finally:
        db.close()


def test_call_tool_email_returns_action_result():
    db_gen = get_test_db()
    db, site_id = next(db_gen)
    try:
        registry = ActionHandlerRegistry()
        registry.register(EmailActionHandler())

        server = MCPServer(registry, db)
        result = server.call_tool("email", {"payload": {"subject": "test", "body": "hello"}}, site_id)

        assert "content" in result
        content = result["content"][0]["text"]
        assert "success" in content
        assert "message" in content
    finally:
        db.close()


def test_call_tool_slack_returns_action_result():
    db_gen = get_test_db()
    db, site_id = next(db_gen)
    try:
        # Set slack_webhook on site
        from db.models import MonitorSite
        site = db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
        site.slack_webhook = "http://slack-webhook"
        db.commit()
        
        registry = ActionHandlerRegistry()
        registry.register(SlackActionHandler())

        server = MCPServer(registry, db)
        result = server.call_tool("slack", {"payload": {"message": "test"}}, site_id)

        assert "content" in result
        content = result["content"][0]["text"]
        assert "success" in content
    finally:
        db.close()


def test_call_tool_unknown_handler_raises():
    db_gen = get_test_db()
    db, site_id = next(db_gen)
    try:
        registry = ActionHandlerRegistry()
        registry.register(EmailActionHandler())

        server = MCPServer(registry, db)
        try:
            server.call_tool("unknown", {}, site_id)
            assert False, "Should have raised"
        except ValueError as e:
            assert "Handler not found" in str(e)
    finally:
        db.close()


def test_sse_endpoint_streams_events():
    import mcp.transport
    assert hasattr(mcp.transport, 'sse_endpoint')
    assert hasattr(mcp.transport, 'sse_router')


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


def test_full_mcp_flow():
    client = TestClient(app)
    headers = {"X-API-Key": "test-secret-key"}
    
    # Initialize
    response = client.post("/mcp/initialize", headers=headers)
    assert response.status_code == 200
    init_data = response.json()
    assert init_data["protocolVersion"] == "2024-11-05"
    
    # List tools
    response = client.post(
        "/mcp/message",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    assert len(tools) == 6
    tool_names = {t["name"] for t in tools}
    assert tool_names == {"email", "slack", "notion", "github", "n8n", "webhook"}
    
    # Get a test site
    db_gen = get_test_db()
    db, site_id = next(db_gen)
    db.close()
    
    # Call email tool with site_id
    response = client.post(
        "/mcp/message",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "email", "arguments": {"payload": {"subject": "Test", "body": "Hello"}}, "site_id": site_id}
        }
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert "content" in result
    content_text = result["content"][0]["text"]
    import json
    parsed = json.loads(content_text)
    assert parsed["success"] is True
    assert parsed["type"] == "email"