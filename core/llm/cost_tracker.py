from dataclasses import dataclass, field
from typing import Optional
from core.llm.config import LLMResponse


@dataclass
class TrackedCall:
    """A single tracked LLM call."""

    run_id: str
    task: str
    model: str
    cost: float
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int


@dataclass
class CostTracker:
    """Track cost, latency, and token usage across LLM calls.

    Calls can be grouped by ``run_id`` and summarized or reset independently.

    ``_calls`` is an internal implementation detail and should not be accessed
    directly by consumers.
    """

    _calls: list[TrackedCall] = field(default_factory=list)

    def track(self, run_id: str, task: str, response: LLMResponse) -> None:
        """Record a single LLM call."""
        self._calls.append(
            TrackedCall(
                run_id=run_id,
                task=task,
                model=response.model,
                cost=response.total_cost,
                latency_ms=response.latency_ms,
                prompt_tokens=response.usage.get("prompt_tokens", 0),
                completion_tokens=response.usage.get("completion_tokens", 0),
            )
        )

    def summary(self, run_id: Optional[str] = None) -> dict:
        """Return aggregated metrics for tracked calls.

        If ``run_id`` is provided, only calls for that run are included.
        """
        items = [c for c in self._calls if run_id is None or c.run_id == run_id]
        return {
            "calls": len(items),
            "total_cost": round(sum(c.cost for c in items), 6),
            "total_latency_ms": sum(c.latency_ms for c in items),
            "total_prompt_tokens": sum(c.prompt_tokens for c in items),
            "total_completion_tokens": sum(c.completion_tokens for c in items),
        }

    def reset(self, run_id: Optional[str] = None) -> None:
        """Clear tracked calls.

        If ``run_id`` is provided, only calls for that run are removed.
        """
        if run_id is None:
            self._calls = []
        else:
            self._calls = [c for c in self._calls if c.run_id != run_id]
