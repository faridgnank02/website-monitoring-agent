import os
import time
from typing import Any, Optional
from openai import OpenAI

from core.llm.config import LLMResponse, ModelConfig, TaskProfile


class LLMRouter:
    def __init__(self, models: dict[str, dict[str, Any]]):
        self.models: dict[str, ModelConfig] = {k: ModelConfig(**v) for k, v in models.items()}
        self._clients: dict[str, OpenAI] = {}

    def route(self, task: TaskProfile) -> ModelConfig:
        if task.requires_vision:
            candidates = [m for m in self.models.values() if m.supports_vision]
            if candidates:
                return candidates[0]

        if task.name == "parse":
            return self._by_model_name("fast") or self._default_model()
        if task.name in ("analyze", "vision", "report", "action"):
            return self._default_model()
        return self._default_model()

    def _by_model_name(self, name: str) -> Optional[ModelConfig]:
        return self.models.get(name)

    def _default_model(self) -> ModelConfig:
        return next(iter(self.models.values()))

    def _get_client(self, config: ModelConfig) -> OpenAI:
        if config.base_url not in self._clients:
            api_key = os.getenv(config.api_env, "")
            self._clients[config.base_url] = OpenAI(base_url=config.base_url, api_key=api_key)
        return self._clients[config.base_url]

    def chat(self, messages: list[dict[str, str]], task: TaskProfile, **kwargs) -> LLMResponse:
        config = self.route(task)
        client = self._get_client(config)
        start = time.time()
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 500),
        )
        latency_ms = (time.time() - start) * 1000
        usage = response.usage
        return LLMResponse(
            model=config.model,
            content=response.choices[0].message.content or "",
            usage={"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens},
            cost_input_per_1k=config.cost_input_per_1k,
            cost_output_per_1k=config.cost_output_per_1k,
            latency_ms=latency_ms,
        )

    def chat_structured(self, messages: list[dict[str, str]], task: TaskProfile, **kwargs) -> str:
        return self.chat(messages, task, **kwargs).content
