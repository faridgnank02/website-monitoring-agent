import requests

from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult
from core.security.site_encryption import resolve_token


NOTION_API_URL = "https://api.notion.com/v1/pages"


class NotionActionHandler(ActionHandler):
    name = "notion"
    risk_score = 0.3

    def _database_id(self, context: ActionContext) -> str:
        cfg = (getattr(context.site, "integration_config", None) or {}).get("notion", {})
        return cfg.get("database_id", "") or ""

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        if self.name not in (getattr(context.site, "actions_enabled", None) or []):
            return []
        if not getattr(context.site, "notion_token", None):
            return []
        database_id = self._database_id(context)
        if not database_id:
            return []
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={
                    "token": context.site.notion_token,
                    "site_id": getattr(context.site, "id", None),
                    "database_id": database_id,
                    "title": context.report.title,
                },
                description="Create Notion page",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        payload = proposed.payload
        try:
            token = resolve_token(payload.get("site_id"), payload.get("token", ""))
            headers = {
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            }
            body = {
                "parent": {"database_id": payload.get("database_id", "")},
                "properties": {
                    "title": {
                        "title": [
                            {"text": {"content": payload.get("title", "Monitor Agent alert")}}
                        ]
                    }
                },
            }
            response = requests.post(NOTION_API_URL, headers=headers, json=body, timeout=10)
            if response.status_code >= 400:
                return ActionResult(
                    success=False,
                    type=self.name,
                    message=f"Notion returned HTTP {response.status_code}",
                )
            external_id = response.json().get("id")
            return ActionResult(
                success=True,
                type=self.name,
                message="Notion page created",
                output={"external_id": external_id},
            )
        except Exception:
            return ActionResult(success=False, type=self.name, message="Notion page creation failed")
