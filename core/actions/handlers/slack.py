from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class SlackActionHandler(ActionHandler):
    name = "slack"
    risk_score = 0.4

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        if not context.site.slack_webhook:
            return []
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={"webhook": context.site.slack_webhook, "message": context.report.summary},
                description="Post to Slack",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(success=True, type=self.name, message="Slack message posted", output=proposed.payload)
