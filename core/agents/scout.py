import hashlib
import time
from typing import Optional, Any
from sqlalchemy.orm import Session

from core.agents.events import ScoutEvent
from core.llm.router import LLMRouter
from core.llm.config import TaskProfile
from db.models import MonitorSite, MonitorSnapshot
from src.modules import parse_instruction, scrape_url


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

        entities = []
        if self.llm_router and has_change:
            entities = self._extract_entities(scraped.markdown)

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
        if not self.llm_router:
            return []
        messages = [
            {"role": "system", "content": "Extract structured entities (prices, products, stock status, etc.) as JSON."},
            {"role": "user", "content": markdown[:4000]},
        ]
        try:
            response = self.llm_router.chat(messages, TaskProfile(name="parse"))
            import json
            return json.loads(response.content) if response.content else []
        except Exception:
            return []
