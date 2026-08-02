from core.llm.config import ModelConfig, TaskProfile, LLMResponse


def test_model_config_from_dict():
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


def test_task_profile_defaults():
    profile = TaskProfile(name="parse")
    assert profile.name == "parse"
    assert profile.complexity == "simple"
    assert profile.latency_requirement == "low"
    assert profile.requires_vision is False


def test_task_profile_explicit_values():
    profile = TaskProfile(
        name="vision",
        complexity="complex",
        latency_requirement="high",
        requires_vision=True,
    )
    assert profile.name == "vision"
    assert profile.complexity == "complex"
    assert profile.latency_requirement == "high"
    assert profile.requires_vision is True


def test_llm_response_cost_calculation():
    resp = LLMResponse(
        model="test",
        content="hello",
        usage={"prompt_tokens": 1000, "completion_tokens": 500},
        cost_input_per_1k=0.01,
        cost_output_per_1k=0.03,
    )
    assert resp.total_cost == 0.01 + 0.015


def test_llm_response_total_cost_zero_tokens():
    resp = LLMResponse(
        model="test",
        content="hello",
        usage={"prompt_tokens": 0, "completion_tokens": 0},
        cost_input_per_1k=0.01,
        cost_output_per_1k=0.03,
    )
    assert resp.total_cost == 0.0


def test_llm_response_total_cost_rounding():
    resp = LLMResponse(
        model="test",
        content="hello",
        usage={"prompt_tokens": 1, "completion_tokens": 1},
        cost_input_per_1k=0.0006,
        cost_output_per_1k=0.0006,
    )
    assert resp.total_cost == 0.000001
