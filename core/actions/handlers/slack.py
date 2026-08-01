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
                    "site_id": getattr(context.site, "id", None),
                },
                description="Post to Slack",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        payload = proposed.payload
        try:
            webhook = resolve_token(payload.get("site_id"), payload.get("webhook", ""))
            response = requests.post(
                webhook,
                json={"text": payload.get("text", "")},
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
                output={"external_id": None},
            )
        except Exception as exc:
            return ActionResult(success=False, type=self.name, message=str(exc))
