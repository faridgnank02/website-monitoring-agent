from typing import Any
from sqlalchemy.orm import Session
from core.actions.base import ProposedAction
from core.actions.registry import ActionHandlerRegistry
from core.agents.action import ActionAgent
from core.agents.events import ReportEvent
from db.models import MonitorSite
from mcp.tools import handler_to_tool
import json


class MCPServer:
    def __init__(self, registry: ActionHandlerRegistry, db: Session):
        self.registry = registry
        self.db = db
        self.action_agent = ActionAgent(registry)

    def list_tools(self) -> list[dict[str, Any]]:
        tools = []
        for handler_name in self.registry.list():
            handler = self.registry.get(handler_name)
            if handler:
                tools.append(handler_to_tool(handler))
        return tools

    def call_tool(self, name: str, arguments: dict, site_id: int) -> dict[str, Any]:
        handler = self.registry.get(name)
        if not handler:
            raise ValueError(f"Handler not found: {name}")

        site = self.db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
        if not site:
            raise ValueError(f"Site not found: {site_id}")

        report = ReportEvent(
            run_id=f"mcp-{site_id}",
            site_id=site_id,
            title=f"MCP Tool Call: {name}",
            summary=f"Manual tool invocation via MCP: {name}",
        )

        proposal = self._proposal_for(name, arguments, site, report)
        if self._requires_approval(site, proposal):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": False,
                            "type": name,
                            "message": f"Action requires approval (policy: {site.approval_policy}, risk: {proposal.risk_score})",
                            "output": {"approval_required": True}
                        })
                    }
                ]
            }

        safe_payload = self._sanitize_payload(name, arguments.get("payload", {}))
        proposal.payload = {**proposal.payload, **safe_payload}
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

    def _proposal_for(self, name: str, arguments: dict, site: MonitorSite, report: ReportEvent):
        """Resolve the ProposedAction to execute for a tool call.

        Prefers the proposal emitted naturally by the handler from the site
        context. Because some handlers only produce a proposal when the site is
        fully configured (tokens, webhooks, repos), fall back to a synthetic
        proposal built from the handler's declared risk score and the caller's
        (sanitized) arguments so every advertised tool can actually be invoked.
        """
        context = type("Context", (), {"site": site, "report": report, "change": None})()
        for proposal in self.registry.propose_all(context):
            if proposal.type == name:
                return proposal
        handler = self.registry.get(name)
        return ProposedAction(
            type=name,
            risk_score=handler.risk_score,
            payload=arguments.get("payload", {}),
            description=f"MCP Tool Call: {name}",
        )

    def _sanitize_payload(self, handler_name: str, payload: dict) -> dict:
        allowed_fields = {
            "email": ["subject", "body"],
            "slack": ["message"],
            "notion": ["database_id", "title", "content"],
            "github": ["repo", "title", "body"],
            "n8n": ["webhook_url", "data"],
            "webhook": ["url", "method", "headers", "body"],
        }
        allowed = allowed_fields.get(handler_name, [])
        return {k: v for k, v in payload.items() if k in allowed}

    def _requires_approval(self, site: MonitorSite, proposal) -> bool:
        if site.approval_policy == "always":
            return True
        if site.approval_policy == "high_risk" and proposal.risk_score >= 0.7:
            return True
        return False