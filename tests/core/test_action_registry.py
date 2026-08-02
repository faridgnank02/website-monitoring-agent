from core.actions.base import ActionContext, ProposedAction
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler


def test_registry_finds_handler():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    handler = registry.get("email")
    assert handler is not None
    assert handler.name == "email"
