import requests

from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class N8NActionHandler(ActionHandler):
    name = "n8n"
    risk_score = 0.3

    def _webhook_url(self) -> str:
        from config import settings
        return settings.N8N_WEBHOOK_URL or ""

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        if self.name not in (getattr(context.site, "actions_enabled", None) or []):
            return []
        webhook_url = self._webhook_url()
        if not webhook_url:
            return []
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={
                    "url": webhook_url,
                    "site_id": getattr(context.site, "id", None),
                    "title": context.report.title,
                    "summary": context.report.summary,
                    "change_score": self._change_score(context),
                    "severity": self._severity(context),
                },
                description="Send change payload to n8n",
            )
        ]

    @staticmethod
    def _change_score(context: ActionContext) -> float:
        if context.change is None:
            return 0.0
        return float(getattr(context.change, "change_score", 0.0) or 0.0)

    @staticmethod
    def _severity(context: ActionContext) -> str:
        if context.change is None:
            return "low"
        return getattr(context.change, "severity", "low") or "low"

    def execute(self, proposed: ProposedAction) -> ActionResult:
        try:
            payload = proposed.payload
            body = {
                "event": "monitor_change",
                "site_id": payload.get("site_id"),
                "title": payload.get("title"),
                "summary": payload.get("summary"),
                "change_score": float(payload.get("change_score", 0.0) or 0.0),
                "severity": payload.get("severity", "low"),
            }
            url = payload.get("url", "")
            if not url:
                return ActionResult(
                    success=False,
                    type=self.name,
                    message="n8n webhook url not configured",
                )
            response = requests.post(url, json=body, timeout=10)
            if response.status_code >= 400:
                return ActionResult(
                    success=False,
                    type=self.name,
                    message=f"n8n returned HTTP {response.status_code}",
                )
            return ActionResult(
                success=True,
                type=self.name,
                message="n8n webhook called",
            )
        except Exception:
            return ActionResult(success=False, type=self.name, message="n8n webhook call failed")
