from typing import Optional
from core.actions.base import ActionHandler


class ActionHandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, handler: ActionHandler) -> None:
        self._handlers[handler.name] = handler

    def get(self, name: str) -> Optional[ActionHandler]:
        return self._handlers.get(name)

    def list(self) -> list[str]:
        return list(self._handlers.keys())

    def propose_all(self, context) -> list:
        proposals = []
        for handler in self._handlers.values():
            proposals.extend(handler.propose(context))
        return proposals


def build_default_registry() -> ActionHandlerRegistry:
    from core.actions.handlers.email import EmailActionHandler
    from core.actions.handlers.slack import SlackActionHandler
    from core.actions.handlers.notion import NotionActionHandler
    from core.actions.handlers.github import GitHubActionHandler
    from core.actions.handlers.n8n import N8NActionHandler
    from core.actions.handlers.webhook import WebhookActionHandler

    registry = ActionHandlerRegistry()
    for handler in (
        EmailActionHandler(),
        SlackActionHandler(),
        NotionActionHandler(),
        GitHubActionHandler(),
        N8NActionHandler(),
        WebhookActionHandler(),
    ):
        registry.register(handler)
    return registry
