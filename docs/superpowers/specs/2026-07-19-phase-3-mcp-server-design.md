# Phase 3 — MCP Server Design

**Date:** 2026-07-19  
**Status:** Approved — ready for implementation planning  
**Depends on:** Phase 0 (stable action handler interface)  

---

## 1. Goal

Expose the existing action handler registry to external agents (Claude, Cursor, VS Code) through a separate FastAPI service implementing the Model Context Protocol (MCP) over HTTP+SSE.

---

## 2. Non-goals

- stdio transport (can be added later)
- Per-client API keys (single global key for Phase 3)
- Real implementations for Notion, GitHub, n8n, webhook (Phase 4)
- Database access from MCP server (stateless design)

---

## 3. Architecture

### 3.1 Service Layout

```
mcp/
  main.py           # FastAPI app, lifespan, CORS, /health
  server.py         # MCPServer: list_tools(), call_tool()
  tools.py          # ActionHandler → MCP Tool mapping
  auth.py           # X-API-Key middleware
  transport.py      # SSE endpoints: /mcp/initialize, /mcp/message, /mcp/sse
```

### 3.2 Deployment

- Separate FastAPI service on port 8001
- Stateless: no database, reads handler metadata from `core.actions.registry`
- Shared Docker image with main API (same codebase)
- `MCP_API_KEY` environment variable for authentication

---

## 4. Components

### 4.1 `mcp/main.py`

FastAPI application entry point:
- Creates `MCPServer` instance with handler registry
- Mounts SSE transport routes
- Adds API-key authentication middleware
- Health endpoint: `GET /health → {"status": "ok"}`
- CORS enabled for MCP clients

### 4.2 `mcp/server.py`

```python
class MCPServer:
    def __init__(self, registry: ActionHandlerRegistry):
        self.registry = registry

    def list_tools(self) -> list[Tool]:
        """Return all 6 handlers as MCP Tool definitions."""

    def call_tool(self, name: str, arguments: dict) -> ToolResult:
        """Execute handler and return result."""
```

### 4.3 `mcp/tools.py`

Maps each `ActionHandler` to an MCP `Tool`:
- `name`: handler.name
- `description`: handler description
- `inputSchema`: from `handler.input_schema()`
- `outputSchema`: from `handler.output_schema()`

### 4.4 `mcp/auth.py`

Middleware that validates `X-API-Key` header against `MCP_API_KEY` env var.
- Returns 403 if missing or invalid
- Applied to all `/mcp/*` routes

### 4.5 `mcp/transport.py`

SSE transport endpoints:
- `POST /mcp/initialize` — MCP initialization handshake
- `POST /mcp/message` — JSON-RPC message (tools/list, tools/call)
- `GET /mcp/sse` — Server-Sent Events stream for responses

---

## 5. ActionHandler Extension

Add to `core/actions/base.py`:

```python
class ActionHandler(ABC):
    name: str = ""
    risk_score: float = 0.0

    @abstractmethod
    def propose(self, context: ActionContext) -> list[ProposedAction]: ...

    @abstractmethod
    def execute(self, proposed: ProposedAction) -> ActionResult: ...

    def input_schema(self) -> dict:
        """JSON Schema for tool input. Default: ProposedAction.payload shape."""
        return {"type": "object", "properties": {"payload": {"type": "object"}}, "required": ["payload"]}

    def output_schema(self) -> dict:
        """JSON Schema for tool output. Default: ActionResult shape."""
        return {"type": "object", "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "output": {"type": "object"}
        }}
```

---

## 6. Handler Registry

All 6 handlers registered in `mcp/main.py` on startup:

| Handler | Status | File |
|---------|--------|------|
| email | Real (stub) | `core/actions/handlers/email.py` |
| slack | Real (stub) | `core/actions/handlers/slack.py` |
| notion | Placeholder | `core/actions/handlers/notion.py` |
| github | Placeholder | `core/actions/handlers/github.py` |
| n8n | Placeholder | `core/actions/handlers/n8n.py` |
| webhook | Placeholder | `core/actions/handlers/webhook.py` |

Placeholder `execute()` returns:
```python
ActionResult(success=False, message="Not implemented")
```

---

## 7. Data Flow

### 7.1 List Tools

```
Client → GET /mcp/sse (connect)
Client → POST /mcp/initialize
Server → SSE: initialized event
Client → POST /mcp/message {method: "tools/list"}
Server → SSE: tools/list response with 6 Tool objects
```

### 7.2 Call Tool

```
Client → POST /mcp/message {method: "tools/call", params: {name: "slack", arguments: {...}}}
Server → auth middleware validates X-API-Key
Server → MCPServer.call_tool("slack", arguments)
       → registry.get("slack") → handler
       → handler.propose(context) → ProposedAction
       → handler.execute(proposed) → ActionResult
       → wrap as ToolResult {content: [{type: "text", text: json.dumps(result)}]}
Server → SSE: tools/call response
```

---

## 8. Dependencies

No external MCP package. Manual SSE implementation in `transport.py`.

Add to `requirements-api.txt`:
```text
# No additional dependencies for Phase 3
```

---

## 9. Docker

Add to `docker-compose.yml`:
```yaml
services:
  mcp:
    build: .
    command: python -m mcp.main
    ports:
      - "8001:8001"
    environment:
      - MCP_API_KEY=${MCP_API_KEY}
```

Add `MCP_API_KEY` to `config/.env.example`.

---

## 10. Tests

### 10.1 `tests/mcp/test_mcp_server.py`

- `list_tools` returns all 6 handlers
- `call_tool` delegates to correct handler
- Invalid/missing `X-API-Key` returns 403

### 10.2 `tests/mcp/test_mcp_tools.py`

- Schema generation for each handler type
- Input/output schema matches handler contracts

---

## 11. Acceptance Criteria

- `GET /mcp/sse` streams valid MCP session events
- `list_tools` returns email, slack, notion, github, n8n, webhook
- `call_tool` invokes handler and returns JSON result
- Unauthorized requests return 403
- Test suite reaches ≥80 passing

---

## 12. Rollout Notes

- Phase 3 validates the protocol layer with placeholder handlers
- Phase 4 replaces placeholders with real implementations
- Adding a handler in Phase 4 automatically exposes it via MCP (single source of truth: `core/actions/registry.py`)

---

## 13. Open Questions Resolved

| Question | Decision |
|----------|----------|
| DB access | Stateless — no DB, reads registry only |
| Transport | SSE first, stdio later |
| MCP library | Manual implementation (no external dependency) |
| Deployment | Separate service on port 8001 |
| Auth | Single global `MCP_API_KEY` |
| Placeholders | All 6 handlers exposed in list_tools |