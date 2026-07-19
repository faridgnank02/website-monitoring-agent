from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class GitHubActionHandler(ActionHandler):
    name = "github"
    risk_score = 0.5

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        return []

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(
            success=False,
            type=self.name,
            message="Not implemented"
        )