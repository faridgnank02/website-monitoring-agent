import json
import logging
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


def _strip_code_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content[3:]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    if content.endswith("```"):
        content = content[:-3].strip()
    return content


def _derive_entity_id(entity: dict) -> str:
    context = str(entity.get("context") or "").strip()
    name = str(entity.get("name") or "").strip()
    if context and name:
        return _slugify(f"{context}::{name}")
    return _slugify(name)


def _normalize_entity(raw: dict) -> Optional[Entity]:
    name = str(raw.get("name") or "").strip()
    value = str(raw.get("value") or "").strip()
    if not name or not value:
        return None
    unit = str(raw.get("unit") or "").strip() or None
    context = str(raw.get("context") or "").strip() or None
    entity_id = str(raw.get("entity_id") or "").strip() or _derive_entity_id(raw)
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
        logging.warning("Entity extraction failed: %s", exc)
        return []
