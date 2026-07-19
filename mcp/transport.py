from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from mcp.server import MCPServer
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler
import json


sse_router = APIRouter()

# Initialize MCP server with all handlers
registry = ActionHandlerRegistry()
registry.register(EmailActionHandler())
registry.register(SlackActionHandler())
registry.register(NotionActionHandler())
registry.register(GitHubActionHandler())
registry.register(N8NActionHandler())
registry.register(WebhookActionHandler())
mcp_server = MCPServer(registry)


@sse_router.post("/initialize")
async def initialize(request: Request):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}


@sse_router.post("/message")
async def message(request: Request):
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})

    if method == "tools/list":
        tools = mcp_server.list_tools()
        return {"tools": tools}
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        result = mcp_server.call_tool(name, arguments)
        return result
    return {"error": {"code": -32601, "message": "Method not found"}}


@sse_router.get("/sse")
async def sse_endpoint(request: Request):
    async def event_stream():
        yield "data: {}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")