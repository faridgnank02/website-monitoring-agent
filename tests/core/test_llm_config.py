from core.llm.config import ModelConfig, TaskProfile, LLMResponse


def test_model_config_parses_yaml():
    data = {
        "provider": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "api_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
        "cost_input_per_1k": 0.0001,
        "cost_output_per_1k": 0.0002,
    }
    config = ModelConfig(**data)
    assert config.model == "llama-3.3-70b-versatile"
    assert config.supports_vision is False


def test_llm_response_cost_calculation():
    resp = LLMResponse(
        model="test",
        content="hello",
        usage={"prompt_tokens": 1000, "completion_tokens": 500},
        cost_input_per_1k=0.01,
        cost_output_per_1k=0.03,
    )
    assert resp.total_cost == 0.01 + 0.015
