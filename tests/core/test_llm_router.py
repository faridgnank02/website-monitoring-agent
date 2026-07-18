from unittest.mock import patch, MagicMock
from core.llm.config import TaskProfile
from core.llm.router import LLMRouter


def test_router_chooses_vision_model_for_vision_task():
    router = LLMRouter({
        "fast": {"provider": "openai_compatible", "base_url": "http://fast", "api_env": "FAST_KEY", "model": "fast-model"},
        "vision": {"provider": "openai_compatible", "base_url": "http://vision", "api_env": "VISION_KEY", "model": "vision-model", "supports_vision": True},
    })
    profile = TaskProfile(name="analyze", requires_vision=True)
    selected = router.route(profile)
    assert selected.model == "vision-model"


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
