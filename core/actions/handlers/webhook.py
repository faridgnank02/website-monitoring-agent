import hashlib
import hmac
import json

import requests

from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult
from core.security.site_encryption import resolve_token


class WebhookActionHandler(ActionHandler):
    name = "webhook"
    risk_score = 0.2

    def _config(self, context: ActionContext) -> dict:
        return (getattr(context.site, "integration_config", None) or {}).get("webhook", {})

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        if self.name not in (getattr(context.site, "actions_enabled", None) or []):
            return []
        cfg = self._config(context)
        url = cfg.get("url", "")
        if not url:
            return []
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={
                    "url": url,
                    "secret": cfg.get("secret", "") or "",
                    "site_id": getattr(context.site, "id", None),
                    "title": context.report.title,
                    "summary": context.report.summary,
                },
                description="POST to webhook",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        try:
            payload = proposed.payload
            url = payload.get("url", "")
            if not url:
                return ActionResult(
                    success=False,
                    type=self.name,
                    message="webhook url not configured",
                )
            body = {
                "event": "monitor_change",
                "site_id": payload.get("site_id"),
                "title": payload.get("title"),
                "summary": payload.get("summary"),
            }
            data = json.dumps(body, default=str)
            headers = {"Content-Type": "application/json"}
            secret = resolve_token(payload.get("site_id"), payload.get("secret", ""))
            if secret:
                signature = hmac.new(
                    secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
                ).hexdigest()
                headers["X-Signature"] = f"sha256={signature}"
            response = requests.post(url, data=data, headers=headers, timeout=10)
            if response.status_code >= 400:
                return ActionResult(
                    success=False,
                    type=self.name,
                    message=f"Webhook returned HTTP {response.status_code}",
                )
            return ActionResult(
                success=True,
                type=self.name,
                message="Webhook delivered",
            )
        except Exception:
            return ActionResult(success=False, type=self.name, message="Webhook delivery failed")
