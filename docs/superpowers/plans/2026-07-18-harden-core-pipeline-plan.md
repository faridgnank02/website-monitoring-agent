# Phase 0: Harden the Core Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real entity correlation between snapshots so `AnalystAgent` can accurately classify price drops, price rises, and new-product changes, and add comprehensive edge-case tests for the monitoring pipeline.

**Architecture:** Add a `core/entities/` subsystem with extraction and correlation modules. `ScoutAgent` extracts entities from the current snapshot and stores them raw. `AnalystAgent` loads the previous snapshot's entities and correlates them with the current ones, producing `{entity_id, old_value, new_value, changed}` pairs. The orchestrator passes this through to reporter and action agents. All new code is unit tested with mocked LLM and scraper calls.

**Tech Stack:** Python 3.9+, Pydantic, SQLAlchemy, pytest, difflib, existing `core/llm/router.py` and `src/modules/`.

---

## File Structure

| File | Responsibility |
|---|---|
| `core/entities/models.py` | Pydantic models: `Entity`, `CorrelatedEntity` |
| `core/entities/extractor.py` | `extract_entities()` — LLM-based entity extraction with normalization |
| `core/entities/correlator.py` | `correlate_entities()` — matches old/new entities by `entity_id` |
| `core/entities/__init__.py` | Public exports |
| `core/agents/events.py` | Add `entities` to `ScoutEvent`, `correlated_entities` to `AnalysisEvent` |
| `core/agents/scout.py` | Use `extract_entities`, store entities in snapshot |
| `core/agents/analyst.py` | Use `correlate_entities`, improve classification |
| `core/orchestrator.py` | Ensure `AnalysisEvent` payload is logged |
| `tests/core/test_entities_models.py` | Model validation tests |
| `tests/core/test_entities_extractor.py` | Extraction + normalization tests |
| `tests/core/test_entities_correlator.py` | Correlation tests (unchanged, changed, added, removed, renamed) |
| `tests/core/test_scout_agent.py` | Add entity persistence test |
| `tests/core/test_analyst_agent.py` | Add classification tests |
| `tests/core/test_orchestrator.py` | Add edge-case tests |

---

## Task 1: Define entity models

**Files:**
- Create: `core/entities/models.py`
- Create: `core/entities/__init__.py`
- Test: `tests/core/test_entities_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_entities_models.py
from core.entities.models import Entity, CorrelatedEntity


def test_entity_requires_id_and_name():
    e = Entity(entity_id="prod-1", name="T-Shirt", value="19.99")
    assert e.entity_id == "prod-1"
    assert e.name == "T-Shirt"
    assert e.value == "19.99"


def test_correlated_entity_tracks_change():
    c = CorrelatedEntity(
        entity_id="prod-1",
        name="T-Shirt",
        old_value="19.99",
        new_value="17.99",
        changed=True,
        status="changed",
    )
    assert c.old_value == "19.99"
    assert c.new_value == "17.99"
    assert c.changed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/core/test_entities_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.entities.models'`

- [ ] **Step 3: Write the models**

```python
# core/entities/models.py
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: str
    name: str
    value: str
    unit: Optional[str] = None
    context: Optional[str] = None


class CorrelatedEntity(BaseModel):
    entity_id: str
    name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    unit: Optional[str] = None
    changed: bool = False
    status: str = "unchanged"  # unchanged | changed | added | removed
```

```python
# core/entities/__init__.py
from core.entities.models import Entity, CorrelatedEntity

__all__ = ["Entity", "CorrelatedEntity"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/core/test_entities_models.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add core/entities/models.py core/entities/__init__.py tests/core/test_entities_models.py
git commit -m "feat(entities): add Entity and CorrelatedEntity models"
```

---

## Task 2: Implement entity extraction

**Files:**
- Create: `core/entities/extractor.py`
- Modify: `core/llm/config.py` (add `TaskProfile` if missing — check first)
- Test: `tests/core/test_entities_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_entities_extractor.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/core/test_entities_extractor.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.entities.extractor'`

- [ ] **Step 3: Implement the extractor**

```python
# core/entities/extractor.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/core/test_entities_extractor.py -v
```
Expected: 3 passed

- [ ] **Step 5: Update `core/entities/__init__.py` to export extractor**

```python
# core/entities/__init__.py
from core.entities.models import Entity, CorrelatedEntity
from core.entities.extractor import extract_entities

__all__ = ["Entity", "CorrelatedEntity", "extract_entities"]
```

- [ ] **Step 6: Commit**

```bash
git add core/entities/extractor.py core/entities/__init__.py tests/core/test_entities_extractor.py
git commit -m "feat(entities): add LLM entity extraction with normalization"
```

---

## Task 3: Implement entity correlation

**Files:**
- Create: `core/entities/correlator.py`
- Test: `tests/core/test_entities_correlator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_entities_correlator.py
from core.entities.models import Entity
from core.entities.correlator import correlate_entities


def test_unchanged_entity():
    old = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    new = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    result = correlate_entities(old, new)
    assert len(result) == 1
    assert result[0].changed is False
    assert result[0].status == "unchanged"


def test_changed_entity():
    old = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    new = [Entity(entity_id="prod-1", name="T-Shirt", value="17.99")]
    result = correlate_entities(old, new)
    assert len(result) == 1
    assert result[0].changed is True
    assert result[0].old_value == "19.99"
    assert result[0].new_value == "17.99"


def test_added_and_removed_entities():
    old = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    new = [
        Entity(entity_id="prod-1", name="T-Shirt", value="19.99"),
        Entity(entity_id="prod-2", name="Jeans", value="49.99"),
    ]
    result = correlate_entities(old, new)
    assert len(result) == 2
    statuses = {r.entity_id: r.status for r in result}
    assert statuses["prod-1"] == "unchanged"
    assert statuses["prod-2"] == "added"


def test_removed_entity():
    old = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    new = []
    result = correlate_entities(old, new)
    assert len(result) == 1
    assert result[0].status == "removed"
    assert result[0].old_value == "19.99"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/core/test_entities_correlator.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.entities.correlator'`

- [ ] **Step 3: Implement the correlator**

```python
# core/entities/correlator.py
from typing import Optional
from core.entities.models import Entity, CorrelatedEntity


def correlate_entities(old: list[Entity], new: list[Entity]) -> list[CorrelatedEntity]:
    old_by_id = {e.entity_id: e for e in old}
    new_by_id = {e.entity_id: e for e in new}

    results: list[CorrelatedEntity] = []
    seen_ids = set()

    for entity_id in new_by_id:
        new_entity = new_by_id[entity_id]
        old_entity = old_by_id.get(entity_id)
        if old_entity is None:
            results.append(CorrelatedEntity(
                entity_id=entity_id,
                name=new_entity.name,
                new_value=new_entity.value,
                unit=new_entity.unit,
                changed=True,
                status="added",
            ))
        else:
            changed = old_entity.value != new_entity.value
            results.append(CorrelatedEntity(
                entity_id=entity_id,
                name=new_entity.name,
                old_value=old_entity.value,
                new_value=new_entity.value,
                unit=new_entity.unit,
                changed=changed,
                status="changed" if changed else "unchanged",
            ))
        seen_ids.add(entity_id)

    for entity_id in old_by_id:
        if entity_id in seen_ids:
            continue
        old_entity = old_by_id[entity_id]
        results.append(CorrelatedEntity(
            entity_id=entity_id,
            name=old_entity.name,
            old_value=old_entity.value,
            unit=old_entity.unit,
            changed=True,
            status="removed",
        ))

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/core/test_entities_correlator.py -v
```
Expected: 4 passed

- [ ] **Step 5: Update `core/entities/__init__.py` to export correlator**

```python
# core/entities/__init__.py
from core.entities.models import Entity, CorrelatedEntity
from core.entities.extractor import extract_entities
from core.entities.correlator import correlate_entities

__all__ = ["Entity", "CorrelatedEntity", "extract_entities", "correlate_entities"]
```

- [ ] **Step 6: Commit**

```bash
git add core/entities/correlator.py core/entities/__init__.py tests/core/test_entities_correlator.py
git commit -m "feat(entities): add entity correlation between snapshots"
```

---

## Task 4: Update event models

**Files:**
- Modify: `core/agents/events.py`
- Test: `tests/core/test_agent_events.py`

- [ ] **Step 1: Write the failing test**

Add to existing `tests/core/test_agent_events.py` (or create if missing):

```python
# tests/core/test_agent_events.py
from core.agents.events import ScoutEvent, AnalysisEvent
from core.entities.models import Entity, CorrelatedEntity


def test_scout_event_carries_entities():
    event = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        url="https://example.com",
        entities=[Entity(entity_id="p1", name="Shirt", value="10")],
    )
    assert event.entities[0].name == "Shirt"


def test_analysis_event_carries_correlated_entities():
    event = AnalysisEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        correlated_entities=[
            CorrelatedEntity(entity_id="p1", name="Shirt", old_value="10", new_value="12", changed=True)
        ],
    )
    assert event.correlated_entities[0].changed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/core/test_agent_events.py -v
```
Expected: `AttributeError` or `ValidationError` for `entities` / `correlated_entities`

- [ ] **Step 3: Update event models**

```python
# core/agents/events.py
from core.entities.models import Entity, CorrelatedEntity


class ScoutEvent(AgentEvent):
    stage: str = "scout"
    has_change: bool
    snapshot_id: Optional[int] = None
    url: str
    content_markdown: Optional[str] = None
    content_html: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    entities: list[Entity] = Field(default_factory=list)
    error: Optional[str] = None


class AnalysisEvent(AgentEvent):
    stage: str = "analyst"
    has_change: bool
    change_type: str = "content_update"
    severity: str = "low"
    change_score: float = 0.0
    added_lines: int = 0
    removed_lines: int = 0
    modified_lines: int = 0
    visual_diff_path: Optional[str] = None
    vision_description: Optional[str] = None
    semantic_diff_summary: Optional[str] = None
    correlated_entities: list[CorrelatedEntity] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/core/test_agent_events.py -v
```
Expected: all existing tests + 2 new tests pass

- [ ] **Step 5: Commit**

```bash
git add core/agents/events.py tests/core/test_agent_events.py
git commit -m "feat(events): add entity and correlated_entity fields to agent events"
```

---

## Task 5: Update ScoutAgent to use entity extraction

**Files:**
- Modify: `core/agents/scout.py`
- Test: `tests/core/test_scout_agent.py`

- [ ] **Step 1: Write the failing test**

Add to existing `tests/core/test_scout_agent.py`:

```python
from unittest.mock import MagicMock, patch
from core.entities.models import Entity


def test_scout_extracts_and_returns_entities():
    site = MagicMock()
    site.id = 1
    site.instruction = "Monitor price of T-Shirt"
    site.url = "https://example.com"

    parsed = MagicMock(success=True, url="https://example.com", error=None)
    scraped = MagicMock(success=True, markdown="T-Shirt $19.99", html="", metadata={}, error=None)
    entity = Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")

    with patch("core.agents.scout.parse_instruction", return_value=parsed), \
         patch("core.agents.scout.scrape_url", return_value=scraped), \
         patch("core.entities.extractor.extract_entities", return_value=[entity]):
        agent = ScoutAgent(llm_router=MagicMock(), db=MagicMock())
        event = agent.run(site, previous_snapshot=None)

    assert event.has_change is True
    assert event.entities == [entity]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/core/test_scout_agent.py::test_scout_extracts_and_returns_entities -v
```
Expected: `AttributeError` or assertion error because `entities` is not set

- [ ] **Step 3: Update ScoutAgent**

```python
# core/agents/scout.py
from core.entities.extractor import extract_entities
from core.entities.models import Entity


class ScoutAgent:
    def __init__(self, llm_router: Optional[LLMRouter] = None, db: Optional[Session] = None):
        self.llm_router = llm_router
        self.db = db

    def run(self, site: MonitorSite, previous_snapshot: Optional[MonitorSnapshot] = None) -> ScoutEvent:
        start = time.time()
        parsed = parse_instruction(site.instruction)
        if not parsed.success:
            return ScoutEvent(
                run_id="", site_id=site.id, has_change=False, url="", error=parsed.error
            )

        if not site.url:
            site.url = parsed.url
            if self.db:
                self.db.commit()

        scraped = scrape_url(parsed.url)
        if not scraped.success:
            return ScoutEvent(
                run_id="", site_id=site.id, has_change=False, url=parsed.url, error=scraped.error
            )

        content_hash = hashlib.md5(scraped.markdown.encode("utf-8")).hexdigest()
        has_change = previous_snapshot is None or previous_snapshot.content_hash != content_hash

        entities: list[Entity] = []
        if has_change:
            entities = extract_entities(scraped.markdown, self.llm_router)

        latency_ms = (time.time() - start) * 1000
        return ScoutEvent(
            run_id="",
            site_id=site.id,
            has_change=has_change,
            url=parsed.url,
            content_markdown=scraped.markdown,
            content_html=scraped.html,
            content_hash=content_hash,
            metadata=scraped.metadata if isinstance(scraped.metadata, dict) else {},
            entities=entities,
            latency_ms=latency_ms,
        )

    def _extract_entities(self, markdown: str) -> list[dict[str, Any]]:
        # Remove this method entirely; use extract_entities instead.
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/core/test_scout_agent.py -v
```
Expected: all existing tests + new test pass

- [ ] **Step 5: Commit**

```bash
git add core/agents/scout.py tests/core/test_scout_agent.py
git commit -m "feat(scout): use extract_entities and return typed entities"
```

---

## Task 6: Update AnalystAgent to use entity correlation

**Files:**
- Modify: `core/agents/analyst.py`
- Test: `tests/core/test_analyst_agent.py`

- [ ] **Step 1: Write the failing test**

Add to existing `tests/core/test_analyst_agent.py`:

```python
from unittest.mock import MagicMock
from core.entities.models import Entity
from core.agents.events import ScoutEvent


def test_analyst_classifies_price_drop():
    llm_router = MagicMock()
    agent = AnalystAgent(llm_router=llm_router)

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $17.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="17.99", unit="USD")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[Entity(entity_id="t-shirt", name="T-Shirt", value="17.99", unit="USD")]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        from src.modules.content_comparator import ComparisonResult
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=2.0,
            added_lines=[],
            removed_lines=[],
            modified_lines=[("T-Shirt $19.99", "T-Shirt $17.99")],
            diff_summary="Price changed",
            total_lines_old=1,
            total_lines_new=1,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "price_drop"
    assert result.severity == "high"
    assert result.correlated_entities[0].changed is True


def test_analyst_classifies_new_product():
    llm_router = MagicMock()
    agent = AnalystAgent(llm_router=llm_router)

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $19.99\\nJeans $49.99"
    new_snap.extracted_entities = [
        Entity(entity_id="t-shirt", name="T-Shirt", value="19.99"),
        Entity(entity_id="jeans", name="Jeans", value="49.99"),
    ]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[Entity(entity_id="jeans", name="Jeans", value="49.99")]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        from src.modules.content_comparator import ComparisonResult
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=0.5,
            added_lines=["Jeans $49.99"],
            removed_lines=[],
            modified_lines=[],
            diff_summary="Added Jeans",
            total_lines_old=1,
            total_lines_new=2,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "new_product"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/core/test_analyst_agent.py -v
```
Expected: `AssertionError` on change_type

- [ ] **Step 3: Update AnalystAgent**

```python
# core/agents/analyst.py
from core.entities.correlator import correlate_entities
from core.entities.models import CorrelatedEntity, Entity


def _normalize_snapshot_entities(raw_entities: list) -> list[Entity]:
    """Convert DB JSON list into typed Entity objects."""
    entities = []
    for raw in raw_entities:
        if isinstance(raw, Entity):
            entities.append(raw)
        elif isinstance(raw, dict):
            entities.append(Entity(**raw))
    return entities


class AnalystAgent:
    def __init__(self, llm_router: Optional[LLMRouter] = None):
        self.llm_router = llm_router

    def run(self, scout: ScoutEvent, old_snapshot: Optional[MonitorSnapshot], new_snapshot: Optional[MonitorSnapshot]) -> AnalysisEvent:
        start = time.time()
        if not scout.has_change or old_snapshot is None or new_snapshot is None:
            return AnalysisEvent(
                run_id=scout.run_id,
                site_id=scout.site_id,
                has_change=False,
                change_type="content_update",
                severity="low",
            )

        comparison = compare_content(
            old_snapshot.content_markdown or "",
            new_snapshot.content_markdown or "",
            threshold=0.0,
        )

        old_entities = _normalize_snapshot_entities(old_snapshot.extracted_entities or [])
        new_entities = _normalize_snapshot_entities(new_snapshot.extracted_entities or [])
        correlated = correlate_entities(old_entities, new_entities)

        change_type = self._classify_change(correlated, comparison)
        severity = self._severity(change_type, comparison.change_score, correlated)
        summary = comparison.diff_summary if comparison.has_changes else "No significant changes"

        latency_ms = (time.time() - start) * 1000
        return AnalysisEvent(
            run_id=scout.run_id,
            site_id=scout.site_id,
            has_change=comparison.has_changes,
            change_type=change_type,
            severity=severity,
            change_score=comparison.change_score,
            added_lines=len(comparison.added_lines),
            removed_lines=len(comparison.removed_lines),
            modified_lines=len(comparison.modified_lines),
            semantic_diff_summary=summary,
            latency_ms=latency_ms,
            correlated_entities=correlated,
        )

    def _classify_change(self, correlated: list[CorrelatedEntity], comparison) -> str:
        for entity in correlated:
            if entity.status != "changed":
                continue
            name = entity.name.lower()
            if "price" in name:
                try:
                    old_val = float((entity.old_value or "").replace("$", "").replace(",", ""))
                    new_val = float((entity.new_value or "").replace("$", "").replace(",", ""))
                    if new_val < old_val:
                        return "price_drop"
                    if new_val > old_val:
                        return "price_rise"
                except (ValueError, TypeError):
                    pass

        has_added = any(e.status == "added" for e in correlated)
        if has_added and not comparison.removed_lines:
            return "new_product"
        return "content_update"

    def _severity(self, change_type: str, change_score: float, correlated: list[CorrelatedEntity]) -> str:
        if change_type in ("price_drop", "price_rise"):
            return "high" if change_score > 1.0 else "medium"
        if change_score > 5.0:
            return "critical"
        if change_score > 1.0:
            return "medium"
        return "low"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/core/test_analyst_agent.py -v
```
Expected: all existing tests + new tests pass

- [ ] **Step 5: Commit**

```bash
git add core/agents/analyst.py tests/core/test_analyst_agent.py
git commit -m "feat(analyst): classify changes using correlated entities"
```

---

## Task 7: Ensure orchestrator logs AnalysisEvent payload

**Files:**
- Modify: `core/orchestrator.py`

- [ ] **Step 1: Inspect current `_log` method**

The current `_log` method reads:
```python
reasoning=str(event.payload) if hasattr(event, "payload") else "",
```

Pydantic models have a `.model_dump()` method, but `payload` is a dict. `AnalysisEvent` has no `payload` attribute, so reasoning will be empty.

- [ ] **Step 2: Update `_save_snapshot` to store entities as a list of dicts**

The current orchestrator stores `extracted_entities={"entities": event.entities}`. Change it to store a plain list so `AnalystAgent` can read it back:

```python
# core/orchestrator.py

def _save_snapshot(self, site: MonitorSite, run_id: str, event: ScoutEvent) -> MonitorSnapshot:
    content = event.content_markdown or ""
    snap = MonitorSnapshot(
        site_id=site.id,
        content_markdown=content,
        content_hash=event.content_hash or hashlib.md5(content.encode("utf-8")).hexdigest(),
        content_length=len(content),
        status="success",
        extracted_entities=[e.model_dump() for e in event.entities],
        model_calls={"run_id": run_id},
    )
    self.db.add(snap)
    self.db.flush()
    site.last_checked_at = datetime.utcnow()
    self.db.commit()
    return snap
```

- [ ] **Step 3: Update `_log` to serialize AnalysisEvent entities**

```python
# core/orchestrator.py

def _log(self, run_id: str, site: MonitorSite, actor: str, action: str, event):
    if hasattr(event, "model_dump"):
        reasoning_payload = event.model_dump()
    else:
        reasoning_payload = str(getattr(event, "payload", {}))
    log = AuditLog(
        run_id=run_id,
        site_id=site.id,
        actor=actor,
        action=action,
        reasoning=str(reasoning_payload),
        cost_usd=getattr(event, "cost_usd", 0.0),
        latency_ms=getattr(event, "latency_ms", 0.0),
    )
    self.db.add(log)
```

- [ ] **Step 4: Run orchestrator tests**

Run:
```bash
python -m pytest tests/core/test_orchestrator.py -v
```
Expected: existing tests pass

- [ ] **Step 5: Commit**

```bash
git add core/orchestrator.py
git commit -m "fix(orchestrator): log full event payload in audit log"
```

---

## Task 8: Add orchestrator edge-case tests

**Files:**
- Modify: `tests/core/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Add to existing `tests/core/test_orchestrator.py`:

```python
import hashlib
from unittest.mock import MagicMock, patch
from core.orchestrator import MonitoringOrchestrator


def test_orchestrator_first_run_no_change_detected():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    site = MagicMock()
    site.id = 1
    site.instruction = "Monitor https://example.com"
    site.url = None
    site.threshold = 1.0
    site.active = True
    site.user_id = 1

    with patch("core.orchestrator.parse_instruction") as mock_parse, \
         patch("core.orchestrator.scrape_url") as mock_scrape:
        mock_parse.return_value = MagicMock(success=True, url="https://example.com", error=None)
        mock_scrape.return_value = MagicMock(success=True, markdown="Hello", html="", metadata={}, error=None)
        orch = MonitoringOrchestrator(db)
        result = orch.run(site)

    assert result["success"] is True
    assert result["change_detected"] is False
    assert result["change_score"] == 0.0


def test_orchestrator_identical_content_no_change():
    db = MagicMock()
    previous = MagicMock()
    previous.content_hash = hashlib.md5(b"Hello").hexdigest()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

    site = MagicMock()
    site.id = 1
    site.instruction = "Monitor https://example.com"
    site.url = "https://example.com"
    site.threshold = 1.0
    site.active = True
    site.user_id = 1

    with patch("core.orchestrator.parse_instruction") as mock_parse, \
         patch("core.orchestrator.scrape_url") as mock_scrape:
        mock_parse.return_value = MagicMock(success=True, url="https://example.com", error=None)
        mock_scrape.return_value = MagicMock(success=True, markdown="Hello", html="", metadata={}, error=None)
        orch = MonitoringOrchestrator(db)
        result = orch.run(site)

    assert result["success"] is True
    assert result["change_detected"] is False


def test_orchestrator_scrape_failure_returns_error():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    site = MagicMock()
    site.id = 1
    site.instruction = "Monitor https://example.com"
    site.url = None
    site.threshold = 1.0
    site.active = True
    site.user_id = 1

    with patch("core.orchestrator.parse_instruction") as mock_parse, \
         patch("core.orchestrator.scrape_url") as mock_scrape:
        mock_parse.return_value = MagicMock(success=True, url="https://example.com", error=None)
        mock_scrape.return_value = MagicMock(success=False, markdown="", html="", metadata={}, error="Connection failed")
        orch = MonitoringOrchestrator(db)
        result = orch.run(site)

    assert result["success"] is False
    assert "Connection failed" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/core/test_orchestrator.py -v
```
Expected: some tests fail due to missing behavior

- [ ] **Step 3: Verify no code changes needed beyond earlier tasks**

If the orchestrator already handles these cases correctly after Task 7, the tests should pass. If not, fix the orchestrator minimally.

- [ ] **Step 4: Run full test suite**

Run:
```bash
python -m pytest tests/ -v
```
Expected: ≥55 passing, existing 46 still passing

- [ ] **Step 5: Commit**

```bash
git add tests/core/test_orchestrator.py
git commit -m "test(orchestrator): add first-run, no-change, and scrape-failure tests"
```

---

## Task 9: Final verification and cleanup

- [ ] **Step 1: Run the full test suite**

```bash
source venv/bin/activate
python -m pytest tests/ -v
```
Expected: ≥55 passed, 2 warnings

- [ ] **Step 2: Run the API health check**

```bash
source venv/bin/activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl http://localhost:8000/health
pkill -f "uvicorn api.main:app"
```
Expected: `{"status":"ok","service":"monitor-agent"}`

- [ ] **Step 3: Run the scheduler briefly**

```bash
source venv/bin/activate
timeout 30 python src/scheduler_db.py || true
```
Expected: starts without errors, logs "Scheduler running..."

- [ ] **Step 4: Final commit**

```bash
git status --short
# Confirm only intended files are staged
git log --oneline -5
```

---

## Self-Review

**1. Spec coverage:**
- Entity correlation: Tasks 1–6.
- Edge-case tests: Tasks 7–8.
- Event payload changes: Task 4.
- Orchestrator audit logging: Task 7.

**2. Placeholder scan:**
- No "TBD", "TODO", or "implement later".
- All code blocks contain concrete code.
- All test commands include expected output.

**3. Type consistency:**
- `Entity` and `CorrelatedEntity` used consistently across models, extractor, correlator, scout, analyst, and tests.
- `extract_entities` returns `list[Entity]`; `correlate_entities` returns `list[CorrelatedEntity]`.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-18-harden-core-pipeline-plan.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — I execute tasks in this session, batch by batch, with checkpoints for review.

Which approach do you want?
