from unittest.mock import MagicMock
from core.entities.extractor import extract_entities
from core.entities.models import Entity
from core.llm.config import LLMResponse


def test_extract_entities_parses_valid_json():
    router = MagicMock()
    router.chat.return_value = LLMResponse(
        content='[{"entity_id": "prod-1", "name": "T-Shirt", "value": "19.99", "unit": "USD"}]',
        model="mixtral",
        usage={"prompt_tokens": 100, "completion_tokens": 20},
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        latency_ms=120.0,
    )
    result = extract_entities("T-Shirt $19.99", router)
    assert result == [Entity(entity_id="prod-1", name="T-Shirt", value="19.99", unit="USD")]


def test_extract_entities_returns_empty_on_llm_failure():
    router = MagicMock()
    router.chat.side_effect = RuntimeError("LLM failed")
    result = extract_entities("T-Shirt $19.99", router)
    assert result == []


def test_extract_entities_normalizes_missing_id():
    router = MagicMock()
    router.chat.return_value = LLMResponse(
        content='[{"name": "T-Shirt", "value": "19.99", "context": "Men"}]',
        model="mixtral",
        usage={"prompt_tokens": 100, "completion_tokens": 20},
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        latency_ms=120.0,
    )
    result = extract_entities("T-Shirt $19.99", router)
    assert result[0].entity_id == "men-t-shirt"


def test_extract_entities_returns_empty_when_router_is_none():
    result = extract_entities("T-Shirt $19.99", None)
    assert result == []


def test_extract_entities_returns_empty_on_invalid_json():
    router = MagicMock()
    router.chat.return_value = LLMResponse(
        content="not valid json",
        model="mixtral",
        usage={"prompt_tokens": 100, "completion_tokens": 20},
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        latency_ms=120.0,
    )
    result = extract_entities("T-Shirt $19.99", router)
    assert result == []


def test_extract_entities_returns_empty_on_non_list_json():
    router = MagicMock()
    router.chat.return_value = LLMResponse(
        content='{"entities": []}',
        model="mixtral",
        usage={"prompt_tokens": 100, "completion_tokens": 20},
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        latency_ms=120.0,
    )
    result = extract_entities("T-Shirt $19.99", router)
    assert result == []


def test_extract_entities_skips_entries_missing_name_or_value():
    router = MagicMock()
    router.chat.return_value = LLMResponse(
        content='[{"name": "T-Shirt", "value": "19.99"}, {"name": "OnlyName"}, {"value": "OnlyValue"}]',
        model="mixtral",
        usage={"prompt_tokens": 100, "completion_tokens": 20},
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        latency_ms=120.0,
    )
    result = extract_entities("T-Shirt $19.99", router)
    assert result == [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit=None, context=None)]


def test_extract_entities_skips_non_dict_entries():
    router = MagicMock()
    router.chat.return_value = LLMResponse(
        content='["string", {"name": "x", "value": "y"}]',
        model="mixtral",
        usage={"prompt_tokens": 100, "completion_tokens": 20},
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        latency_ms=120.0,
    )
    result = extract_entities("some markdown", router)
    assert result == [Entity(entity_id="x", name="x", value="y", unit=None, context=None)]


def test_extract_entities_handles_numeric_value():
    router = MagicMock()
    router.chat.return_value = LLMResponse(
        content='[{"name": "T-Shirt", "value": 19.99, "unit": "USD"}]',
        model="mixtral",
        usage={"prompt_tokens": 100, "completion_tokens": 20},
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        latency_ms=120.0,
    )
    result = extract_entities("T-Shirt $19.99", router)
    assert result == [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")]


def test_extract_entities_strips_markdown_code_fences():
    router = MagicMock()
    router.chat.return_value = LLMResponse(
        content='```json\n[{"name": "T-Shirt", "value": "19.99", "unit": "USD"}]\n```',
        model="mixtral",
        usage={"prompt_tokens": 100, "completion_tokens": 20},
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        latency_ms=120.0,
    )
    result = extract_entities("T-Shirt $19.99", router)
    assert result == [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")]
