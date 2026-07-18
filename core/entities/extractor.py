import json
import re
from typing import Optional
from core.entities.models import Entity
from core.llm.router import LLMRouter
from core.llm.config import TaskProfile


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


def _derive_entity_id(entity: dict) -> str:
    context = (entity.get("context") or "").strip()
    name = (entity.get("name") or "").strip()
    if context and name:
        return _slugify(f"{context}::{name}")
    return _slugify(name)


def _normalize_entity(raw: dict) -> Optional[Entity]:
    name = (raw.get("name") or "").strip()
    value = (raw.get("value") or "").strip()
    if not name or not value:
        return None
    entity_id = (raw.get("entity_id") or "").strip() or _derive_entity_id(raw)
    if not entity_id:
        return None
    return Entity(
        entity_id=entity_id,
        name=name,
        value=value,
        unit=(raw.get("unit") or None),
        context=(raw.get("context") or None),
    )


def extract_entities(markdown: str, llm_router: Optional[LLMRouter] = None) -> list[Entity]:
    if not llm_router:
        return []
    messages = [
        {"role": "system", "content": "Extract structured entities as JSON."},
        {"role": "user", "content": EXTRACTION_PROMPT.format(markdown=markdown[:4000])},
    ]
    try:
        response = llm_router.chat(messages, TaskProfile(name="parse"))
        raw_list = json.loads(response.content or "[]")
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
    except Exception:
        return []
