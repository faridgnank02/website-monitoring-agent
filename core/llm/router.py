import os
import time
from typing import Any, Optional

from openai import OpenAI

from core.llm.config import LLMResponse, ModelConfig, TaskProfile


class LLMError(Exception):
    """Raised when an LLM request fails."""


class LLMRouter:
    """Routes LLM tasks to the most appropriate model and exposes a unified chat interface.

    The router picks a model based on the task profile (vision requirements, task name,
    etc.) and returns a structured response. All public methods return plain Python or
    Pydantic objects; the OpenAI-compatible client details are hidden internally.
    """

    def __init__(self, models: dict[str, dict[str, Any]]):
        """Initialize the router with a mapping of model names to model configurations.

        Args:
            models: Dictionary mapping model names to configuration dictionaries.

        Raises:
            ValueError: If ``models`` is empty.
        """
        if not models:
            raise ValueError("At least one model configuration is required")
        self.models: dict[str, ModelConfig] = {k: ModelConfig(**v) for k, v in models.items()}
        self._clients: dict[str, OpenAI] = {}

    @classmethod
    def from_settings(cls) -> "LLMRouter":
        """Create an ``LLMRouter`` from the application settings.

        Returns:
            An ``LLMRouter`` instance configured with ``load_llm_router_config()``.
        """
        from config.settings import load_llm_router_config

        return cls(load_llm_router_config())

    def route(self, task: TaskProfile) -> ModelConfig:
        """Select the best model configuration for the given task profile.

        Vision tasks prefer a model with ``supports_vision=True``. The ``parse`` task
        prefers a model named ``fast`` if available, otherwise falls back to the default
        model.

        Args:
            task: The task profile describing the LLM request.

        Returns:
            The selected ``ModelConfig``.
        """
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
        """Return the model configuration with the given name, if it exists."""
        return self.models.get(name)

    def _default_model(self) -> ModelConfig:
        """Return the default model (the first configured one)."""
        return next(iter(self.models.values()))

    def _get_client(self, config: ModelConfig) -> OpenAI:
        """Return (creating if needed) an OpenAI-compatible client for the given model.

        Clients are cached by both ``base_url`` and ``api_env`` so that two models sharing
        the same endpoint but using different API keys do not collide.

        Args:
            config: The model configuration to build the client for.

        Returns:
            An ``OpenAI`` client instance.
        """
        cache_key = f"{config.base_url}|{config.api_env}"
        if cache_key not in self._clients:
            api_key = os.getenv(config.api_env, "")
            self._clients[cache_key] = OpenAI(
                base_url=config.base_url,
                api_key=api_key,
                timeout=config.timeout,
            )
        return self._clients[cache_key]

    def chat(self, messages: list[dict[str, str]], task: TaskProfile, **kwargs) -> LLMResponse:
        """Send a chat request to the routed model and return a structured response.

        Args:
            messages: List of messages in the OpenAI chat format.
            task: Task profile used to route the request.
            **kwargs: Extra arguments forwarded to the chat completion call, such as
                ``temperature`` and ``max_tokens``.

        Returns:
            An ``LLMResponse`` containing the generated content, token usage, and latency.

        Raises:
            LLMError: If the underlying API call fails.
        """
        config = self.route(task)
        client = self._get_client(config)
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=kwargs.get("max_tokens", 500),
            )
        except Exception as exc:
            raise LLMError(f"LLM request failed for model {config.model}: {exc}") from exc
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

    def chat_text(self, messages: list[dict[str, str]], task: TaskProfile, **kwargs) -> str:
        """Send a chat request and return only the generated text content.

        Args:
            messages: List of messages in the OpenAI chat format.
            task: Task profile used to route the request.
            **kwargs: Extra arguments forwarded to the chat completion call.

        Returns:
            The generated text content as a plain string.
        """
        return self.chat(messages, task, **kwargs).content
