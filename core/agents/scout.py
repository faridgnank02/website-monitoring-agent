import hashlib
import time
from typing import Optional
from sqlalchemy.orm import Session

from core.agents.events import ScoutEvent
from core.entities.extractor import extract_entities
from core.entities.models import Entity
from core.llm.router import LLMRouter
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

