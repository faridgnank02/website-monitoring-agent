from unittest.mock import MagicMock
from core.entities.extractor import extract_entities
from core.entities.models import Entity
from core.llm.config import LLMResponse, TaskProfile


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
