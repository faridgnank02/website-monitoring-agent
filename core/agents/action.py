import time
from typing import Optional, Any
from core.agents.events import ReportEvent, ActionEvent
from core.actions.registry import ActionHandlerRegistry
from core.actions.base import ActionContext
from db.models import MonitorSite


class ActionAgent:
    def __init__(self, registry: ActionHandlerRegistry):
        self.registry = registry

    def run(self, report: ReportEvent, site: MonitorSite, change: Optional[Any] = None) -> ActionEvent:
        start = time.time()
        enabled = set(getattr(site, "actions_enabled", None) or [])
        context = ActionContext(site=site, report=report, change=change)
        proposals = [
            p for p in self.registry.propose_all(context) if p.type in enabled
        ]

        actions = []
        approval_requests = []
        for proposal in proposals:
            if self._requires_approval(site, proposal):
                approval_requests.append({
                    "type": proposal.type,
                    "risk_score": proposal.risk_score,
                    "payload": proposal.payload,
                    "description": proposal.description,
                })
            else:
                handler = self.registry.get(proposal.type)
                result = handler.execute(proposal)
                actions.append({
                    "type": proposal.type,
                    "success": result.success,
                    "message": result.message,
                    "output": result.output,
                })

        latency_ms = (time.time() - start) * 1000
        return ActionEvent(
            run_id=report.run_id,
            site_id=report.site_id,
            actions=actions,
            approval_requests=approval_requests,
            latency_ms=latency_ms,
        )

    def _requires_approval(self, site: MonitorSite, proposal) -> bool:
        if site.approval_policy == "always":
            return True
        if site.approval_policy == "high_risk" and proposal.risk_score >= 0.7:
            return True
        return False
