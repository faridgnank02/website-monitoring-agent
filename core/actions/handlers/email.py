from datetime import datetime

from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult
from src.modules.gmail_notifier import GmailNotifier, ChangeNotification


class EmailActionHandler(ActionHandler):
    name = "email"
    risk_score = 0.1

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        if self.name not in (getattr(context.site, "actions_enabled", None) or []):
            return []
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={
                    "subject": context.report.title,
                    "body": context.report.summary,
                    "url": getattr(context.site, "url", None) or "",
                    "site_id": getattr(context.site, "id", None),
                },
                description="Send email alert",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        payload = proposed.payload
        try:
            notification = ChangeNotification(
                url=payload.get("url", ""),
                instruction=payload.get("subject") or "Monitor Agent alert",
                change_score=float(payload.get("change_score", 0.0)),
                threshold=float(payload.get("threshold", 1.0)),
                added_lines=int(payload.get("added_lines", 0)),
                removed_lines=int(payload.get("removed_lines", 0)),
                modified_lines=int(payload.get("modified_lines", 0)),
                diff_summary=payload.get("body") or "",
                timestamp=datetime.now().strftime("%d/%m/%Y à %H:%M:%S"),
                elements_watched=payload.get("elements_watched", ["contenu surveillé"]),
            )
            ok = GmailNotifier().send_notification(notification)
            return ActionResult(
                success=ok,
                type=self.name,
                message="Email sent" if ok else "Email failed",
            )
        except Exception as exc:
            return ActionResult(success=False, type=self.name, message=str(exc))
