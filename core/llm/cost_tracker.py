from dataclasses import dataclass, field
from typing import Optional
from core.llm.config import LLMResponse


@dataclass
class CostTracker:
    calls: list[dict] = field(default_factory=list)

    def track(self, run_id: str, task: str, response: LLMResponse) -> None:
        self.calls.append({
            "run_id": run_id,
            "task": task,
            "model": response.model,
            "cost": response.total_cost,
            "latency_ms": response.latency_ms,
            "prompt_tokens": response.usage.get("prompt_tokens", 0),
            "completion_tokens": response.usage.get("completion_tokens", 0),
        })

    def summary(self, run_id: Optional[str] = None) -> dict:
        items = [c for c in self.calls if run_id is None or c["run_id"] == run_id]
        return {
            "calls": len(items),
            "total_cost": round(sum(c["cost"] for c in items), 6),
            "total_latency_ms": sum(c["latency_ms"] for c in items),
            "total_prompt_tokens": sum(c["prompt_tokens"] for c in items),
            "total_completion_tokens": sum(c["completion_tokens"] for c in items),
        }

    def reset(self, run_id: Optional[str] = None) -> None:
        if run_id is None:
            self.calls = []
        else:
            self.calls = [c for c in self.calls if c["run_id"] != run_id]
