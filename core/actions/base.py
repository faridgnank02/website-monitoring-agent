from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
from core.agents.events import ReportEvent


@dataclass
class ActionContext:
    site: Any
    report: ReportEvent
    change: Optional[Any] = None


@dataclass
class ProposedAction:
    type: str
    risk_score: float
    payload: dict[str, Any]
    description: str


@dataclass
class ActionResult:
    success: bool
    type: str
    message: str
    output: Optional[dict[str, Any]] = None


class ActionHandler(ABC):
    name: str = ""
    risk_score: float = 0.0

    @abstractmethod
    def propose(self, context: ActionContext) -> list[ProposedAction]: ...

    @abstractmethod
    def execute(self, proposed: ProposedAction) -> ActionResult: ...

    def input_schema(self) -> dict:
        """JSON Schema for tool input. Default: ProposedAction.payload shape."""
        return {
            "type": "object",
            "properties": {
                "payload": {"type": "object"}
            },
            "required": ["payload"]
        }

    def output_schema(self) -> dict:
        """JSON Schema for tool output. Default: ActionResult shape."""
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "output": {"type": "object"}
            }
        }
