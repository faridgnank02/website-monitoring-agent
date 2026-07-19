import re
import time
from typing import Optional, Union

from core.agents.events import ScoutEvent, AnalysisEvent
from core.llm.router import LLMRouter
from db.models import MonitorSnapshot
from src.modules import compare_content
from core.entities.correlator import correlate_entities
from core.entities.models import CorrelatedEntity, Entity


def _normalize_snapshot_entities(raw_entities: Optional[Union[list, dict]]) -> list[Entity]:
    """Convert DB JSON list/dict into typed Entity objects."""
    if raw_entities is None:
        return []
    if isinstance(raw_entities, dict):
        raw_entities = raw_entities.get("entities", [])
    entities = []
    for raw in raw_entities:
        if isinstance(raw, Entity):
            entities.append(raw)
        elif isinstance(raw, dict):
            entities.append(Entity(**raw))
    return entities


def _parse_price(value: str) -> Optional[float]:
    """Parse a price string. Returns None if unparseable.

    NOTE: This is a simple parser. It strips non-numeric characters and treats
    commas as thousand separators, so European-style decimals like "19,99" will
    be parsed as 1999.0. A locale-aware parser can be added later.
    """
    if not value:
        return None
    cleaned = re.sub(r"[^\d.,]", "", value)
    # Treat comma as thousand separator for simplicity
    cleaned = cleaned.replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


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
        severity = self._severity(change_type, comparison.change_score)
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
            unit = (entity.unit or "").upper()
            is_price = "price" in name or unit in ("USD", "EUR", "GBP", "$")
            if is_price:
                old_val = _parse_price(entity.old_value)
                new_val = _parse_price(entity.new_value)
                if old_val is None or new_val is None:
                    continue
                if new_val < old_val:
                    return "price_drop"
                if new_val > old_val:
                    return "price_rise"

        has_added = any(e.status == "added" for e in correlated)
        has_removed = any(e.status == "removed" for e in correlated)
        if has_added and not has_removed:
            return "new_product"
        return "content_update"

    def _severity(self, change_type: str, change_score: float) -> str:
        if change_type in ("price_drop", "price_rise"):
            return "high" if change_score > 1.0 else "medium"
        if change_score > 5.0:
            return "critical"
        if change_score > 1.0:
            return "medium"
        return "low"
