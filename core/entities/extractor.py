import json
import logging
import re
from typing import Optional
from core.entities.models import Entity
from core.llm.router import LLMRouter
from core.llm.config import TaskProfile


_logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """
Extract structured entities from the markdown below. Return ONLY a JSON array of objects.
Each object must have: name, value. Optional fields: unit, context.
Examples of entities: products, prices, stock status, dates, headings, regulations.

Markdown:
{markdown}
"""


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "entity"


def _strip_code_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content[3:]
        if content.lower().startswith("json"):
            content = content[4:]
        content = content.strip()
    if content.endswith("```"):
        content = content[:-3].strip()
    return content


def _coerce_str(raw: dict, key: str) -> str:
    value = raw.get(key)
    return "" if value is None else str(value).strip()


def _derive_entity_id(entity: dict) -> str:
    context = _coerce_str(entity, "context")
    name = _coerce_str(entity, "name")
    if context and name:
        return _slugify(f"{context}::{name}")
    return _slugify(name)


def _normalize_entity(raw: dict) -> Optional[Entity]:
    name = _coerce_str(raw, "name")
    value = _coerce_str(raw, "value")
    if not name or not value:
        return None
    unit = _coerce_str(raw, "unit") or None
    context = _coerce_str(raw, "context") or None
    entity_id = _coerce_str(raw, "entity_id") or _derive_entity_id(raw)
    return Entity(
        entity_id=entity_id,
        name=name,
        value=value,
        unit=unit,
        context=context,
    )


def extract_entities(markdown: str, llm_router: Optional[LLMRouter] = None) -> list[Entity]:
    """Extract structured entities from markdown using an LLM router.

    Args:
        markdown: The markdown content to extract entities from.
        llm_router: Optional LLM router used to generate the JSON entity list.
            If None, an empty list is returned.

    Returns:
        A list of normalized Entity objects extracted from the LLM response.
    """
    if not llm_router:
        return []
    messages = [
        {"role": "system", "content": "Extract structured entities as JSON."},
        {"role": "user", "content": EXTRACTION_PROMPT.format(markdown=markdown[:4000])},
    ]
    try:
        response = llm_router.chat(messages, TaskProfile(name="parse"))
        raw_list = json.loads(_strip_code_fences(response.content or "[]"))
        if not isinstance(raw_list, list):
            return []
        entities = []
        for raw in raw_list:
            if not isinstance(raw, dict):
                continue
            entity = _normalize_entity(raw)
            if entity:
                entities.append(entity)
        return entities
    except Exception as exc:
        _logger.warning("Entity extraction failed: %s", exc)
        return []
