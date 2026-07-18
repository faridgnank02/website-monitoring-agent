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
