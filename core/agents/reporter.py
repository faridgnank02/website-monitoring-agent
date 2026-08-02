import time
from typing import Optional
from core.agents.events import AnalysisEvent, ReportEvent
from core.llm.router import LLMRouter
from core.llm.config import TaskProfile


class ReporterAgent:
    def __init__(self, llm_router: Optional[LLMRouter] = None):
        self.llm_router = llm_router

    def run(self, analysis: AnalysisEvent) -> ReportEvent:
        start = time.time()
        title = self._title(analysis.change_type)
        summary = analysis.semantic_diff_summary or f"{analysis.change_type} detected with severity {analysis.severity}"
        recommended = [
            {"type": "email", "reason": "default alert"},
            {"type": "slack", "reason": "high visibility"},
        ] if analysis.severity in ("high", "critical") else [
            {"type": "email", "reason": "default alert"},
        ]

        if self.llm_router:
            summary = self._generate_summary(analysis)

        latency_ms = (time.time() - start) * 1000
        return ReportEvent(
            run_id=analysis.run_id,
            site_id=analysis.site_id,
            title=title,
            summary=summary,
            recommended_actions=recommended,
            latency_ms=latency_ms,
        )

    def _title(self, change_type: str) -> str:
        return {
            "price_drop": "Price drop detected",
            "price_rise": "Price rise detected",
            "new_product": "New product detected",
            "layout_change": "Layout change detected",
            "seo_change": "SEO metadata changed",
            "content_update": "Content updated",
        }.get(change_type, "Change detected")

    def _generate_summary(self, analysis: AnalysisEvent) -> str:
        messages = [
            {"role": "system", "content": "Write a concise, human-readable summary of a website change."},
            {"role": "user", "content": f"change_type={analysis.change_type}, severity={analysis.severity}, summary={analysis.semantic_diff_summary}"},
        ]
        try:
            response = self.llm_router.chat(messages, TaskProfile(name="report"))
            return response.content
        except Exception:
            return analysis.semantic_diff_summary or "Change detected"
