from typing import Any
from core.agents.events import AnalysisEvent


class WorkflowEngine:
    def __init__(self, rules: dict[str, Any]):
        self.rules = rules.get("rules", [])

    def evaluate(self, analysis: AnalysisEvent, change_score: float = 0.0) -> list[dict[str, Any]]:
        triggered = []
        context = {
            "change_type": analysis.change_type,
            "severity": analysis.severity,
            "change_score": change_score,
            "has_change": analysis.has_change,
        }
        for rule in self.rules:
            try:
                if self._eval(rule.get("condition", ""), context):
                    triggered.append(rule)
            except Exception:
                continue
        return triggered

    def _eval(self, condition: str, context: dict) -> bool:
        if not condition:
            return False
        # Simple expression evaluation with restricted globals
        allowed = {"__builtins__": {}}
        return bool(eval(condition, allowed, context))
