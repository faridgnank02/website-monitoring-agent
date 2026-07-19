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