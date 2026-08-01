"""
Pending-approval notifications: one email digest + one Slack message per batch.
Each channel fails independently (log-and-continue). Never raises.
"""

import logging
from datetime import datetime

from config import settings
from core.actions.base import ProposedAction
from core.actions.handlers.slack import SlackActionHandler
from src.modules.gmail_notifier import GmailNotifier, ChangeNotification

logger = logging.getLogger(__name__)


class ApprovalNotifier:
    def __init__(self):
        self.slack_handler = SlackActionHandler()

    def notify_pending(self, site, requests) -> None:
        if not requests:
            return
        self._notify_email(site, requests)
        self._notify_slack(site, requests)

    def _notify_email(self, site, requests) -> None:
        try:
            if not settings.GMAIL_RECIPIENT_EMAIL:
                return
            summary = "\n".join(
                f"- {r['action_type']} (risk {r['risk_score']:.2f})" for r in requests
            )
            notification = ChangeNotification(
                url=getattr(site, "url", None) or "",
                instruction="Actions awaiting your approval",
                change_score=0.0,
                threshold=1.0,
                added_lines=0,
                removed_lines=0,
                modified_lines=0,
                diff_summary=f"{len(requests)} action(s) need approval on site {site.id}:\n{summary}",
                timestamp=datetime.now().strftime("%d/%m/%Y à %H:%M:%S"),
                elements_watched=[],
            )
            ok = GmailNotifier().send_notification(notification)
            if not ok:
                logger.warning("approval email notification failed")
        except Exception:
            logger.exception("approval email notification failed")

    def _notify_slack(self, site, requests) -> None:
        try:
            webhook = getattr(site, "slack_webhook", None) or ""
            if not webhook:
                return
            text = "\n".join(
                f"- {r['action_type']} (risk {r['risk_score']:.2f})" for r in requests
            )
            proposed = ProposedAction(
                type="slack",
                risk_score=0.0,
                payload={
                    "webhook": webhook,
                    "text": f"{len(requests)} action(s) need approval on site {site.id}:\n{text}",
                    "url": getattr(site, "url", None) or "",
                    "change_score": 0.0,
                    "severity": "info",
                    "site_id": site.id,
                },
                description="Pending approvals notification",
            )
            result = self.slack_handler.execute(proposed)
            if not result.success:
                logger.warning("slack approval notification failed: %s", result.message)
        except Exception:
            logger.exception("slack approval notification failed")
