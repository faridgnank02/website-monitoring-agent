from core.actions.base import ActionContext, ProposedAction
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler


def test_registry_finds_handler():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    handler = registry.get("email")
    assert handler is not None
    assert handler.name == "email"


def test_build_default_registry_registers_all_six_handlers():
    from core.actions.registry import build_default_registry
    registry = build_default_registry()
    assert sorted(registry.list()) == ["email", "github", "n8n", "notion", "slack", "webhook"]
