from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from mcp.server import MCPServer
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler
from db.base import SessionLocal
import json
import asyncio
from typing import AsyncGenerator


sse_router = APIRouter()

# Initialize handler registry (shared)
_registry = ActionHandlerRegistry()
_registry.register(EmailActionHandler())
_registry.register(SlackActionHandler())
_registry.register(NotionActionHandler())
_registry.register(GitHubActionHandler())
_registry.register(N8NActionHandler())
_registry.register(WebhookActionHandler())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_mcp_server(db: Session = Depends(get_db)) -> MCPServer:
    return MCPServer(_registry, db)


# Simple session store for SSE
sessions = {}


@sse_router.post("/initialize")
async def initialize(request: Request):
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "monitor-agent-mcp", "version": "0.1.0"}
    }


@sse_router.post("/message")
async def message(
    request: Request,
    mcp_server: MCPServer = Depends(get_mcp_server)
):
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")
    
    if method == "tools/list":
        tools = mcp_server.list_tools()
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        site_id = params.get("site_id")
        if not site_id:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "site_id required"}}
        try:
            result = mcp_server.call_tool(name, arguments, site_id)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except ValueError as e:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": str(e)}}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}


async def sse_event_generator(session_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for a session."""
    yield f"data: {json.dumps({'type': 'connected', 'sessionId': session_id})}\n\n"
    
    try:
        while True:
            await asyncio.sleep(30)
            yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass


@sse_router.get("/sse")
async def sse_endpoint(request: Request):
    import uuid
    session_id = str(uuid.uuid4())
    sessions[session_id] = True
    
    async def event_stream():
        try:
            async for event in sse_event_generator(session_id):
                yield event
        finally:
            sessions.pop(session_id, None)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )