# Phase 3 — MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the action handler registry via a separate FastAPI MCP service over HTTP+SSE.

**Architecture:** Separate stateless FastAPI service on port 8001. Reads handler metadata from `core.actions.registry`. Manual SSE transport (no external MCP library). Single global `MCP_API_KEY` auth.

**Tech Stack:** Python 3.9, FastAPI, httpx (for tests), pytest.

---

## File Structure

**New files:**
- `mcp/__init__.py` — package exports
- `mcp/main.py` — FastAPI app, lifespan, CORS, /health, mounts routers
- `mcp/server.py` — MCPServer class: list_tools(), call_tool()
- `mcp/tools.py` — handler_to_tool() mapping
- `mcp/auth.py` — API-key middleware
- `mcp/transport.py` — SSE endpoints: /mcp/initialize, /mcp/message, /mcp/sse
- `core/actions/handlers/notion.py` — placeholder handler
- `core/actions/handlers/github.py` — placeholder handler
- `core/actions/handlers/n8n.py` — placeholder handler
- `core/actions/handlers/webhook.py` — placeholder handler
- `tests/mcp/test_mcp_server.py` — server tests
- `tests/mcp/test_mcp_tools.py` — schema tests

**Modified files:**
- `core/actions/base.py` — add input_schema(), output_schema() methods
- `docker-compose.yml` — add mcp service
- `config/.env.example` — add MCP_API_KEY
- `README.md` — document MCP server startup

---

## Task 1: Add input/output schema methods to ActionHandler base

**Files:**
- Modify: `core/actions/base.py`
- Test: `tests/mcp/test_mcp_tools.py` (schema validation)

- [ ] **Step 1: Write failing test for schema methods**

```python
# tests/mcp/test_mcp_tools.py (create file)
from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult
from core.actions.handlers.email import EmailActionHandler


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_tools.py -v`
Expected: `ModuleNotFoundError` or `AttributeError: 'EmailActionHandler' object has no attribute 'input_schema'`

- [ ] **Step 3: Add schema methods to base class**

Modify `core/actions/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
from core.agents.events import ReportEvent


@dataclass
class ActionContext:
    site: Any
    report: ReportEvent
    change: Optional[Any] = None


@dataclass
class ProposedAction:
    type: str
    risk_score: float
    payload: dict[str, Any]
    description: str


@dataclass
class ActionResult:
    success: bool
    type: str
    message: str
    output: Optional[dict[str, Any]] = None


class ActionHandler(ABC):
    name: str = ""
    risk_score: float = 0.0

    @abstractmethod
    def propose(self, context: ActionContext) -> list[ProposedAction]: ...

    @abstractmethod
    def execute(self, proposed: ProposedAction) -> ActionResult: ...

    def input_schema(self) -> dict:
        """JSON Schema for tool input. Default: ProposedAction.payload shape."""
        return {
            "type": "object",
            "properties": {
                "payload": {"type": "object"}
            },
            "required": ["payload"]
        }

    def output_schema(self) -> dict:
        """JSON Schema for tool output. Default: ActionResult shape."""
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "output": {"type": "object"}
            }
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_tools.py::test_email_handler_has_input_schema tests/mcp/test_mcp_tools.py::test_email_handler_has_output_schema -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/actions/base.py tests/mcp/test_mcp_tools.py
git commit -m "feat(actions): add input_schema/output_schema to ActionHandler base"
```

---

## Task 2: Create placeholder handlers

**Files:**
- Create: `core/actions/handlers/notion.py`
- Create: `core/actions/handlers/github.py`
- Create: `core/actions/handlers/n8n.py`
- Create: `core/actions/handlers/webhook.py`
- Modify: `core/actions/handlers/__init__.py` (export new handlers)

- [ ] **Step 1: Write failing test for handler registration**

```python
# tests/mcp/test_mcp_tools.py (append)
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler


def test_notion_handler_is_placeholder():
    handler = NotionActionHandler()
    assert handler.name == "notion"
    result = handler.execute(None)
    assert result.success is False
    assert result.message == "Not implemented"


def test_github_handler_is_placeholder():
    handler = GitHubActionHandler()
    assert handler.name == "github"
    result = handler.execute(None)
    assert result.success is False
    assert result.message == "Not implemented"


def test_n8n_handler_is_placeholder():
    handler = N8NActionHandler()
    assert handler.name == "n8n"
    result = handler.execute(None)
    assert result.success is False
    assert result.message == "Not implemented"


def test_webhook_handler_is_placeholder():
    handler = WebhookActionHandler()
    assert handler.name == "webhook"
    result = handler.execute(None)
    assert result.success is False
    assert result.message == "Not implemented"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_tools.py -k "placeholder" -v`
Expected: `ModuleNotFoundError` for new handler modules

- [ ] **Step 3: Create placeholder handlers**

Create `core/actions/handlers/notion.py`:
```python
from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class NotionActionHandler(ActionHandler):
    name = "notion"
    risk_score = 0.3

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(
            success=False,
            type=self.name,
            message="Not implemented"
        )
```

Create `core/actions/handlers/github.py`:
```python
from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class GitHubActionHandler(ActionHandler):
    name = "github"
    risk_score = 0.5

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(
            success=False,
            type=self.name,
            message="Not implemented"
        )
```

Create `core/actions/handlers/n8n.py`:
```python
from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class N8NActionHandler(ActionHandler):
    name = "n8n"
    risk_score = 0.3

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(
            success=False,
            type=self.name,
            message="Not implemented"
        )
```

Create `core/actions/handlers/webhook.py`:
```python
from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class WebhookActionHandler(ActionHandler):
    name = "webhook"
    risk_score = 0.2

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(
            success=False,
            type=self.name,
            message="Not implemented"
        )
```

Update `core/actions/handlers/__init__.py`:
```python
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler

__all__ = [
    "EmailActionHandler",
    "SlackActionHandler",
    "NotionActionHandler",
    "GitHubActionHandler",
    "N8NActionHandler",
    "WebhookActionHandler",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_tools.py -k "placeholder" -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add core/actions/handlers/notion.py core/actions/handlers/github.py core/actions/handlers/n8n.py core/actions/handlers/webhook.py core/actions/handlers/__init__.py
git commit -m "feat(actions): add placeholder handlers for notion, github, n8n, webhook"
```

---

## Task 3: Create MCP server package structure

**Files:**
- Create: `mcp/__init__.py`
- Create: `mcp/main.py` (minimal FastAPI app)
- Create: `mcp/server.py` (MCPServer class skeleton)
- Create: `mcp/tools.py` (handler_to_tool function)
- Create: `mcp/auth.py` (middleware)
- Create: `mcp/transport.py` (SSE endpoints skeleton)

- [ ] **Step 1: Write failing test for MCP package imports**

```python
# tests/mcp/test_mcp_server.py (create file)
from mcp.main import app
from mcp.server import MCPServer
from mcp.tools import handler_to_tool
from mcp.auth import api_key_middleware
from mcp.transport import sse_router


def test_mcp_package_imports():
    assert app is not None
    assert MCPServer is not None
    assert handler_to_tool is not None
    assert api_key_middleware is not None
    assert sse_router is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py::test_mcp_package_imports -v`
Expected: `ModuleNotFoundError: No module named 'mcp'`

- [ ] **Step 3: Create minimal package files**

Create `mcp/__init__.py`:
```python
from mcp.main import app
from mcp.server import MCPServer
from mcp.tools import handler_to_tool
from mcp.auth import api_key_middleware
from mcp.transport import sse_router

__all__ = [
    "app",
    "MCPServer",
    "handler_to_tool",
    "api_key_middleware",
    "sse_router",
]
```

Create `mcp/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mcp.transport import sse_router
from mcp.auth import api_key_middleware


app = FastAPI(
    title="Monitor Agent MCP Server",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(api_key_middleware)

app.include_router(sse_router, prefix="/mcp")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

Create `mcp/server.py`:
```python
from typing import Any
from core.actions.registry import ActionHandlerRegistry


class MCPServer:
    def __init__(self, registry: ActionHandlerRegistry):
        self.registry = registry

    def list_tools(self) -> list[dict[str, Any]]:
        tools = []
        for handler in self.registry._handlers.values():
            tools.append(handler_to_tool(handler))
        return tools

    def call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        handler = self.registry.get(name)
        if not handler:
            raise ValueError(f"Handler not found: {name}")
        # Implementation in Task 5
        return {"content": [{"type": "text", "text": "not implemented"}]}
```

Create `mcp/tools.py`:
```python
from typing import Any
from core.actions.base import ActionHandler


def handler_to_tool(handler: ActionHandler) -> dict[str, Any]:
    return {
        "name": handler.name,
        "description": f"{handler.name} action handler",
        "inputSchema": handler.input_schema(),
        "outputSchema": handler.output_schema(),
    }
```

Create `mcp/auth.py`:
```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import os


MCP_API_KEY = os.getenv("MCP_API_KEY", "")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            api_key = request.headers.get("X-API-Key")
            if not api_key or api_key != MCP_API_KEY:
                raise HTTPException(status_code=403, detail="Invalid API key")
        return await call_next(request)


def api_key_middleware(app):
    app.add_middleware(APIKeyMiddleware)
    return app
```

Create `mcp/transport.py`:
```python
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
import json


sse_router = APIRouter()


@sse_router.post("/initialize")
async def initialize(request: Request):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}


@sse_router.post("/message")
async def message(request: Request):
    body = await request.json()
    method = body.get("method")
    if method == "tools/list":
        return {"tools": []}
    elif method == "tools/call":
        return {"content": [{"type": "text", "text": "not implemented"}]}
    return {"error": {"code": -32601, "message": "Method not found"}}


@sse_router.get("/sse")
async def sse_endpoint(request: Request):
    async def event_stream():
        yield "data: {}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py::test_mcp_package_imports -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add mcp/__init__.py mcp/main.py mcp/server.py mcp/tools.py mcp/auth.py mcp/transport.py
git commit -m "feat(mcp): add package structure with minimal FastAPI app"
```

---

## Task 4: Implement list_tools endpoint

**Files:**
- Modify: `mcp/server.py` — implement list_tools
- Modify: `mcp/transport.py` — wire tools/list to MCPServer
- Test: `tests/mcp/test_mcp_server.py`

- [ ] **Step 1: Write failing test for list_tools**

```python
# tests/mcp/test_mcp_server.py (append)
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler
from mcp.server import MCPServer


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py::test_list_tools_returns_all_six_handlers -v`
Expected: Fail (implementation incomplete)

- [ ] **Step 3: Implement list_tools in MCPServer**

Modify `mcp/server.py`:
```python
from typing import Any
from core.actions.registry import ActionHandlerRegistry
from mcp.tools import handler_to_tool


class MCPServer:
    def __init__(self, registry: ActionHandlerRegistry):
        self.registry = registry

    def list_tools(self) -> list[dict[str, Any]]:
        tools = []
        for handler in self.registry._handlers.values():
            tools.append(handler_to_tool(handler))
        return tools

    def call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        handler = self.registry.get(name)
        if not handler:
            raise ValueError(f"Handler not found: {name}")
        return {"content": [{"type": "text", "text": "not implemented"}]}
```

Modify `mcp/transport.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py::test_list_tools_returns_all_six_handlers -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add mcp/server.py mcp/transport.py tests/mcp/test_mcp_server.py
git commit -m "feat(mcp): implement list_tools with all 6 handlers"
```

---

## Task 5: Implement call_tool endpoint

**Files:**
- Modify: `mcp/server.py` — implement call_tool to execute handler
- Modify: `mcp/transport.py` — ensure tools/call passes arguments correctly
- Test: `tests/mcp/test_mcp_server.py`

- [ ] **Step 1: Write failing test for call_tool**

```python
# tests/mcp/test_mcp_server.py (append)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py -k "call_tool" -v`
Expected: Fail (placeholder implementation)

- [ ] **Step 3: Implement call_tool in MCPServer**

Modify `mcp/server.py`:
```python
from typing import Any
from core.actions.registry import ActionHandlerRegistry
from core.actions.base import ActionContext, ProposedAction
from mcp.tools import handler_to_tool
import json


class MCPServer:
    def __init__(self, registry: ActionHandlerRegistry):
        self.registry = registry

    def list_tools(self) -> list[dict[str, Any]]:
        tools = []
        for handler in self.registry._handlers.values():
            tools.append(handler_to_tool(handler))
        return tools

    def call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        handler = self.registry.get(name)
        if not handler:
            raise ValueError(f"Handler not found: {name}")
        
        # Build a minimal context for propose/execute
        # In real usage, context would come from the monitoring pipeline
        # For MCP, we create a minimal context with the arguments as payload
        class MockSite:
            slack_webhook = "http://slack"
            approval_policy = "never"
        
        class MockReport:
            run_id = "mcp-test"
            site_id = 1
            title = "MCP Test Report"
            summary = "Test summary"
        
        context = ActionContext(
            site=MockSite(),
            report=MockReport()
        )
        
        # Execute: propose then execute
        proposals = handler.propose(context)
        if not proposals:
            # For placeholders, propose returns empty list
            # Create a proposal from the arguments
            proposal = ProposedAction(
                type=name,
                risk_score=handler.risk_score,
                payload=arguments.get("payload", {}),
                description=f"MCP call to {name}"
            )
        else:
            proposal = proposals[0]
            # Merge payload from arguments
            if "payload" in arguments:
                proposal.payload = arguments["payload"]
        
        result = handler.execute(proposal)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "success": result.success,
                        "type": result.type,
                        "message": result.message,
                        "output": result.output
                    })
                }
            ]
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py -k "call_tool" -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add mcp/server.py tests/mcp/test_mcp_server.py
git commit -m "feat(mcp): implement call_tool endpoint"
```

---

## Task 6: Implement SSE transport properly

**Files:**
- Modify: `mcp/transport.py` — proper SSE with session management
- Test: `tests/mcp/test_mcp_server.py`

- [ ] **Step 1: Write failing test for SSE streaming**

```python
# tests/mcp/test_mcp_server.py (append)
from fastapi.testclient import TestClient
from mcp.main import app


def test_sse_endpoint_streams_events():
    client = TestClient(app)
    with client.stream("GET", "/mcp/sse") as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        # Read first event
        for line in response.iter_lines():
            if line.startswith("data:"):
                break
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py::test_sse_endpoint_streams_events -v`
Expected: Fail (SSE not properly implemented)

- [ ] **Step 3: Implement proper SSE with session management**

Modify `mcp/transport.py`:
```python
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
import asyncio
from typing import AsyncGenerator


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
async def message(request: Request):
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
        try:
            result = mcp_server.call_tool(name, arguments)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except ValueError as e:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": str(e)}}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}


async def sse_event_generator(session_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for a session."""
    # Send initial connection event
    yield f"data: {json.dumps({'type': 'connected', 'sessionId': session_id})}\n\n"
    
    # Keep connection alive
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py::test_sse_endpoint_streams_events -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add mcp/transport.py tests/mcp/test_mcp_server.py
git commit -m "feat(mcp): implement proper SSE transport with session management"
```

---

## Task 7: Add API key authentication

**Files:**
- Modify: `mcp/auth.py` — complete middleware
- Test: `tests/mcp/test_mcp_server.py`

- [ ] **Step 1: Write failing test for auth**

```python
# tests/mcp/test_mcp_server.py (append)
from fastapi.testclient import TestClient
from mcp.main import app
import os


def test_mcp_rejects_missing_api_key():
    # Ensure MCP_API_KEY is set
    os.environ["MCP_API_KEY"] = "test-secret-key"
    client = TestClient(app)
    
    response = client.post("/mcp/initialize")
    assert response.status_code == 403


def test_mcp_rejects_invalid_api_key():
    os.environ["MCP_API_KEY"] = "test-secret-key"
    client = TestClient(app)
    
    response = client.post("/mcp/initialize", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 403


def test_mcp_accepts_valid_api_key():
    os.environ["MCP_API_KEY"] = "test-secret-key"
    client = TestClient(app)
    
    response = client.post("/mcp/initialize", headers={"X-API-Key": "test-secret-key"})
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py -k "api_key" -v`
Expected: Fail (auth not working)

- [ ] **Step 3: Fix auth middleware**

Modify `mcp/auth.py`:
```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import os


MCP_API_KEY = os.getenv("MCP_API_KEY", "")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            api_key = request.headers.get("X-API-Key")
            if not api_key or api_key != MCP_API_KEY:
                return Response(
                    content='{"error": "Invalid API key"}',
                    status_code=403,
                    media_type="application/json"
                )
        return await call_next(request)


def api_key_middleware(app):
    app.add_middleware(APIKeyMiddleware)
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py -k "api_key" -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add mcp/auth.py tests/mcp/test_mcp_server.py
git commit -m "feat(mcp): add API key authentication middleware"
```

---

## Task 8: Add Docker Compose service and config

**Files:**
- Modify: `docker-compose.yml` — add mcp service
- Modify: `config/.env.example` — add MCP_API_KEY
- Modify: `README.md` — document MCP server

- [ ] **Step 1: Add mcp service to docker-compose.yml**

```yaml
# docker-compose.yml (add to services)
  mcp:
    build: .
    command: python -m mcp.main
    ports:
      - "8001:8001"
    environment:
      - MCP_API_KEY=${MCP_API_KEY}
    depends_on:
      - api
```

- [ ] **Step 2: Add MCP_API_KEY to config/.env.example**

```
# MCP Server
MCP_API_KEY=your-mcp-api-key-here
```

- [ ] **Step 3: Update README.md with MCP server instructions**

Add to README.md:
```markdown
## MCP Server

The MCP server exposes action handlers to external agents (Claude, Cursor, VS Code) via the Model Context Protocol.

### Start MCP Server

```bash
# Set API key
export MCP_API_KEY=your-secret-key

# Run directly
python -m mcp.main

# Or via docker-compose
docker-compose up mcp
```

The server runs on port 8001 with SSE transport at `/mcp/sse`.

### MCP Client Configuration

For Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "monitor-agent": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8001/mcp/sse"],
      "env": {
        "MCP_API_KEY": "your-secret-key"
      }
    }
  }
}
```

Available tools: `email`, `slack`, `notion`, `github`, `n8n`, `webhook`.
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml config/.env.example README.md
git commit -m "chore(mcp): add docker service, env config, and docs"
```

---

## Task 9: Integration test full MCP flow

**Files:**
- Test: `tests/mcp/test_mcp_server.py`

- [ ] **Step 1: Write end-to-end test**

```python
# tests/mcp/test_mcp_server.py (append)
from fastapi.testclient import TestClient
from mcp.main import app
import os
import json


def test_full_mcp_flow():
    os.environ["MCP_API_KEY"] = "test-secret-key"
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
    
    # Call email tool
    response = client.post(
        "/mcp/message",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "email", "arguments": {"payload": {"subject": "Test", "body": "Hello"}}}
        }
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert "content" in result
    content_text = result["content"][0]["text"]
    parsed = json.loads(content_text)
    assert parsed["success"] is True
    assert parsed["type"] == "email"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/mcp/test_mcp_server.py::test_full_mcp_flow -v`
Expected: `1 passed`

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/test_mcp_server.py
git commit -m "test(mcp): add end-to-end MCP flow test"
```

---

## Task 10: Run full test suite and verify ≥80 passing

**Files:**
- None (verification)

- [ ] **Step 1: Run all tests**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: ≥80 tests passing (94 baseline + new MCP tests)

- [ ] **Step 2: Verify MCP tests specifically**

Run: `venv/bin/python -m pytest tests/mcp/ -v`
Expected: All MCP tests pass

- [ ] **Step 3: Commit final verification**

```bash
git commit -m "chore: verify Phase 3 complete - all tests passing"
```

---

## Self-Review Checklist

- [ ] Spec coverage: All 11 acceptance criteria mapped to tasks
- [ ] No placeholders: Every step has complete code
- [ ] Type consistency: handler_to_tool returns dict with name, description, inputSchema, outputSchema
- [ ] MCP protocol compliance: initialize, tools/list, tools/call all implemented
- [ ] Auth: Single global key via X-API-Key header
- [ ] Transport: SSE with proper media type and keepalive
- [ ] Placeholders: All 6 handlers exposed, 4 return "Not implemented"
- [ ] Docker: mcp service on port 8001
- [ ] Tests: Unit + integration tests for all endpoints