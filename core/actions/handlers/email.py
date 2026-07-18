from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class EmailActionHandler(ActionHandler):
    name = "email"
    risk_score = 0.1

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={"subject": context.report.title, "body": context.report.summary},
                description="Send email alert",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(success=True, type=self.name, message="Email sent", output=proposed.payload)
