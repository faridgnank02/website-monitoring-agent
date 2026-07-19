from typing import Any
from core.actions.registry import ActionHandlerRegistry
from core.actions.base import ActionContext, ProposedAction
from core.agents.events import ReportEvent
from mcp.tools import handler_to_tool
import json


class MockSite:
    slack_webhook = "http://slack"
    approval_policy = "never"


class MockReport:
    run_id = "mcp-test"
    site_id = 1
    title = "MCP Test Report"
    summary = "Test summary"


class MockContext:
    def __init__(self):
        self.site = MockSite()
        self.report = MockReport()


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

        context = MockContext()

        proposals = handler.propose(context)
        if not proposals:
            proposal = ProposedAction(
                type=name,
                risk_score=handler.risk_score,
                payload=arguments.get("payload", {}),
                description=f"MCP call to {name}"
            )
        else:
            proposal = proposals[0]
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