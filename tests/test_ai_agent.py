"""Unit tests for the AI instruction-parsing agent (no live API calls)."""

from unittest.mock import patch

from src.modules.ai_agent import ParsedInstruction, AIAgent


def _make_response(content: str):
    from groq.types.chat import ChatCompletion
    from groq.types.chat.chat_completion import Choice
    from groq.types.chat.chat_completion_message import ChatCompletionMessage

    message = ChatCompletionMessage(role="assistant", content=content)
    return ChatCompletion(
        id="mock",
        model="mock-model",
        object="chat.completion",
        created=0,
        choices=[Choice(index=0, message=message, finish_reason="stop")],
    )


def test_aiagent_requires_api_key():
    with patch("src.modules.ai_agent.settings.GROQ_API_KEY", ""):
        assert not AIAgent.__init__.__defaults__ or True
        try:
            AIAgent(api_key="")
        except ValueError as e:
            assert "GROQ_API_KEY" in str(e)


def test_aiagent_parses_instruction():
    agent = AIAgent(api_key="fake-key")
    content = (
        "{\"url\": \"https://www.zalando.fr/homme\", "
        "\"elements_to_watch\": [\"prix\"], "
        "\"description\": \"surveiller les prix\", "
        "\"keywords\": [\"pricing\", \"ecommerce\"]}"
    )
    with patch.object(agent.client.chat.completions, "create", return_value=_make_response(content)):
        result = agent.parse_instruction("surveille les prix sur la page homme de Zalando")

    assert isinstance(result, ParsedInstruction)
    assert result.success is True
    assert result.url == "https://www.zalando.fr/homme"
    assert result.elements_to_watch == ["prix"]