import time
from typing import Optional
from core.agents.events import ScoutEvent, AnalysisEvent
from core.llm.router import LLMRouter
from core.llm.config import TaskProfile
from db.models import MonitorSnapshot
from src.modules import compare_content


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

        change_type = self._classify_change(scout.entities, comparison)
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
        )

    def _classify_change(self, entities: list, comparison) -> str:
        for entity in entities:
            name = entity.get("name", "").lower()
            old = str(entity.get("old_value", ""))
            new = str(entity.get("value", ""))
            if "price" in name:
                try:
                    old_val = float(old.replace("$", "").replace(",", ""))
                    new_val = float(new.replace("$", "").replace(",", ""))
                    if new_val < old_val:
                        return "price_drop"
                    if new_val > old_val:
                        return "price_rise"
                except ValueError:
                    pass
        if comparison.added_lines and not comparison.removed_lines:
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
