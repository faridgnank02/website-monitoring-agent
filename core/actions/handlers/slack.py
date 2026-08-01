import requests

from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult
from core.security.site_encryption import resolve_token


class SlackActionHandler(ActionHandler):
    name = "slack"
    risk_score = 0.4

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        if self.name not in (getattr(context.site, "actions_enabled", None) or []):
            return []
        webhook = getattr(context.site, "slack_webhook", None)
        if not webhook:
            return []
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={
                    "webhook": webhook,
                    "text": context.report.summary or context.report.title,
                    "url": getattr(context.site, "url", None) or "",
                    "change_score": self._change_score(context),
                    "severity": self._severity(context),
                    "site_id": getattr(context.site, "id", None),
                },
                description="Post to Slack",
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
        payload = proposed.payload
        try:
            webhook = resolve_token(payload.get("site_id"), payload.get("webhook", ""))
            text = payload.get("text", "")
            change_score = float(payload.get("change_score", 0.0) or 0.0)
            severity = payload.get("severity", "low")
            url = payload.get("url", "")
            message = text
            if change_score:
                message += f"\n*Change score:* {change_score:.2f}% (*{severity}*)"
            if url:
                message += f"\n*Site:* {url}"
            response = requests.post(
                webhook,
                json={"text": message},
                timeout=10,
            )
            if response.status_code >= 400:
                return ActionResult(
                    success=False,
                    type=self.name,
                    message=f"Slack returned HTTP {response.status_code}",
                )
            return ActionResult(
                success=True,
                type=self.name,
                message="Slack message posted",
            )
        except Exception:
            return ActionResult(success=False, type=self.name, message="Slack post failed")
