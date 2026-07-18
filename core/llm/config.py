from typing import Optional, Any
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    provider: str = "openai_compatible"
    base_url: str
    api_env: str  # name of the environment variable holding the API key
    model: str
    cost_input_per_1k: float = 0.0
    cost_output_per_1k: float = 0.0
    supports_vision: bool = False
    timeout: float = 60.0


class TaskProfile(BaseModel):
    name: str  # parse | analyze | vision | report | action
    complexity: str = "simple"  # simple | complex
    latency_requirement: str = "low"  # low | high
    requires_vision: bool = False


class LLMResponse(BaseModel):
    model: str
    content: str
    usage: dict[str, Any]
    cost_input_per_1k: float
    cost_output_per_1k: float
    latency_ms: float = 0.0
    trace_id: Optional[str] = None

    @property
    def total_cost(self) -> float:
        input_cost = (self.usage.get("prompt_tokens", 0) / 1000) * self.cost_input_per_1k
        output_cost = (self.usage.get("completion_tokens", 0) / 1000) * self.cost_output_per_1k
        return round(input_cost + output_cost, 6)
