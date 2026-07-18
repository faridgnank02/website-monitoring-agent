from typing import Optional, Any, Literal
from pydantic import BaseModel


class ModelConfig(BaseModel):
    """Configuration for an LLM provider endpoint."""

    provider: str = "openai_compatible"
    base_url: str
    api_env: str  # name of the environment variable holding the API key
    model: str
    cost_input_per_1k: float = 0.0
    cost_output_per_1k: float = 0.0
    supports_vision: bool = False
    timeout: float = 60.0


class TaskProfile(BaseModel):
    """Profile describing an LLM task and its routing constraints."""

    name: Literal["parse", "analyze", "vision", "report", "action"]
    complexity: Literal["simple", "complex"] = "simple"
    latency_requirement: Literal["low", "high"] = "low"
    requires_vision: bool = False


class LLMResponse(BaseModel):
    """Response from an LLM call, including token usage and cost."""

    model: str
    content: str
    usage: dict[str, Any]
    cost_input_per_1k: float
    cost_output_per_1k: float
    latency_ms: float = 0.0
    trace_id: Optional[str] = None

    @property
    def total_cost(self) -> float:
        """Compute total cost in USD, rounded to 6 decimal places."""
        input_cost = (self.usage.get("prompt_tokens", 0) / 1000) * self.cost_input_per_1k
        output_cost = (self.usage.get("completion_tokens", 0) / 1000) * self.cost_output_per_1k
        return round(input_cost + output_cost, 6)
