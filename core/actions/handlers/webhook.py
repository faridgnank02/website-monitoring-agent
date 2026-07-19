from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class WebhookActionHandler(ActionHandler):
    name = "webhook"
    risk_score = 0.2

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(
            success=False,
            type=self.name,
            message="Not implemented"
        )