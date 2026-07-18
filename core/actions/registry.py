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
