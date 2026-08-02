from typing import Any
from core.actions.base import ActionHandler


def handler_to_tool(handler: ActionHandler) -> dict[str, Any]:
    return {
        "name": handler.name,
        "description": f"{handler.name} action handler",
        "inputSchema": handler.input_schema(),
        "outputSchema": handler.output_schema(),
    }