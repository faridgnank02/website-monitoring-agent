from unittest.mock import patch, MagicMock

import pytest

from core.llm.config import TaskProfile
from core.llm.router import LLMRouter, LLMError


def test_empty_config_raises_value_error():
    with pytest.raises(ValueError):
        LLMRouter({})


def test_router_chooses_vision_model_for_vision_task():
    router = LLMRouter({
        "fast": {"provider": "openai_compatible", "base_url": "http://fast", "api_env": "FAST_KEY", "model": "fast-model"},
        "vision": {"provider": "openai_compatible", "base_url": "http://vision", "api_env": "VISION_KEY", "model": "vision-model", "supports_vision": True},
    })
    profile = TaskProfile(name="analyze", requires_vision=True)
    selected = router.route(profile)
    assert selected.model == "vision-model"


def test_parse_task_routes_to_fast_model():
    router = LLMRouter({
        "fast": {"provider": "openai_compatible", "base_url": "http://fast", "api_env": "FAST_KEY", "model": "fast-model"},
        "default": {"provider": "openai_compatible", "base_url": "http://default", "api_env": "DEFAULT_KEY", "model": "default-model"},
    })
    selected = router.route(TaskProfile(name="parse"))
    assert selected.model == "fast-model"


def test_non_vision_task_uses_default_model():
    router = LLMRouter({
        "default": {"provider": "openai_compatible", "base_url": "http://default", "api_env": "DEFAULT_KEY", "model": "default-model"},
        "fast": {"provider": "openai_compatible", "base_url": "http://fast", "api_env": "FAST_KEY", "model": "fast-model"},
    })
    selected = router.route(TaskProfile(name="analyze"))
    assert selected.model == "default-model"


@patch("core.llm.router.OpenAI")
def test_chat_returns_llm_response(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        model="vision-model",
        choices=[MagicMock(message=MagicMock(content="hello"))],
        usage=MagicMock(prompt_tokens=10, completion_tokens=5),
    )

    router = LLMRouter({
        "fast": {"provider": "openai_compatible", "base_url": "http://fast", "api_env": "FAST_KEY", "model": "fast-model"},
    })
    with patch.dict("os.environ", {"FAST_KEY": "test-key"}):
        resp = router.chat([{"role": "user", "content": "hi"}], TaskProfile(name="parse"))
    assert resp.content == "hello"
    assert resp.total_cost == 0.0


@patch("core.llm.router.OpenAI")
def test_chat_text_returns_plain_string(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="plain text"))],
        usage=MagicMock(prompt_tokens=1, completion_tokens=1),
    )
    router = LLMRouter({
        "default": {"provider": "openai_compatible", "base_url": "http://default", "api_env": "DEFAULT_KEY", "model": "default-model"},
    })
    with patch.dict("os.environ", {"DEFAULT_KEY": "test-key"}):
        result = router.chat_text([{"role": "user", "content": "hi"}], TaskProfile(name="analyze"))
    assert result == "plain text"


@patch("core.llm.router.OpenAI")
def test_chat_raises_llm_error_on_api_failure(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.side_effect = RuntimeError("API down")
    router = LLMRouter({
        "default": {"provider": "openai_compatible", "base_url": "http://default", "api_env": "DEFAULT_KEY", "model": "default-model"},
    })
    with patch.dict("os.environ", {"DEFAULT_KEY": "test-key"}):
        with pytest.raises(LLMError) as exc_info:
            router.chat([{"role": "user", "content": "hi"}], TaskProfile(name="analyze"))
    assert "API down" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeError)


@patch("core.llm.router.OpenAI")
def test_client_caching_uses_correct_api_key_per_model(mock_openai_class):
    mock_openai_class.side_effect = lambda **kwargs: MagicMock()
    router = LLMRouter({
        "model_a": {"provider": "openai_compatible", "base_url": "http://same", "api_env": "KEY_A", "model": "model-a"},
        "model_b": {"provider": "openai_compatible", "base_url": "http://same", "api_env": "KEY_B", "model": "model-b"},
    })
    with patch.dict("os.environ", {"KEY_A": "key-a", "KEY_B": "key-b"}):
        client_a = router._get_client(router.models["model_a"])
        client_b = router._get_client(router.models["model_b"])
    assert client_a is not client_b
    calls = mock_openai_class.call_args_list
    assert calls[0].kwargs["api_key"] == "key-a"
    assert calls[1].kwargs["api_key"] == "key-b"


@patch("core.llm.router.OpenAI")
def test_timeout_passed_to_openai_client(mock_openai_class):
    mock_openai_class.return_value = MagicMock()
    router = LLMRouter({
        "default": {"provider": "openai_compatible", "base_url": "http://default", "api_env": "DEFAULT_KEY", "model": "default-model", "timeout": 42.0},
    })
    with patch.dict("os.environ", {"DEFAULT_KEY": "test-key"}):
        router._get_client(router.models["default"])
    assert mock_openai_class.call_args.kwargs["timeout"] == 42.0


def test_vision_required_but_no_vision_model_raises_llm_error():
    router = LLMRouter({
        "default": {"provider": "openai_compatible", "base_url": "http://default", "api_env": "DEFAULT_KEY", "model": "default-model"},
    })
    with pytest.raises(LLMError, match="No vision-capable model configured"):
        router.route(TaskProfile(name="analyze", requires_vision=True))


@patch("config.settings.load_llm_router_config")
def test_from_settings_factory(mock_load):
    mock_load.return_value = {
        "default": {"provider": "openai_compatible", "base_url": "http://default", "api_env": "DEFAULT_KEY", "model": "default-model"},
    }
    router = LLMRouter.from_settings()
    assert "default" in router.models
    mock_load.assert_called_once()
