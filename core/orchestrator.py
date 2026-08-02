import hashlib
import logging
import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from core.agents.events import ScoutEvent, AnalysisEvent, ReportEvent, ActionEvent
from core.agents.scout import ScoutAgent
from core.agents.analyst import AnalystAgent
from core.agents.reporter import ReporterAgent
from core.agents.action import ActionAgent
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.actions.handlers.notion import NotionActionHandler
from core.actions.handlers.github import GitHubActionHandler
from core.actions.handlers.n8n import N8NActionHandler
from core.actions.handlers.webhook import WebhookActionHandler
from core.llm.router import LLMRouter
from core.visual.diff import VisualDiffEngine
from core.visual.screenshot import ScreenshotProvider
from core.visual.storage import FileSystemScreenshotStorage, ScreenshotStorage
from db.models import MonitorSite, MonitorSnapshot, MonitorChange, AuditLog, ApprovalRequest
from config.settings import load_llm_router_config
from src.modules import parse_instruction, scrape_url


class MonitoringOrchestrator:
    def __init__(
        self,
        db: Session,
        llm_router: Optional[LLMRouter] = None,
        screenshot_provider: Optional[ScreenshotProvider] = None,
        screenshot_storage: Optional[ScreenshotStorage] = None,
        visual_diff_engine: Optional[VisualDiffEngine] = None,
    ):
        self.db = db
        self.llm_router = llm_router or LLMRouter(load_llm_router_config())
        self.screenshot_provider = screenshot_provider
        self.screenshot_storage = screenshot_storage or FileSystemScreenshotStorage(".")
        self.visual_diff_engine = visual_diff_engine or VisualDiffEngine()
        self.scout = ScoutAgent(
            llm_router=self.llm_router,
            db=db,
            parse_instruction=parse_instruction,
            scrape_url=scrape_url,
            screenshot_provider=self.screenshot_provider,
        )
        self.analyst = AnalystAgent(
            llm_router=self.llm_router,
            visual_diff_engine=self.visual_diff_engine,
            screenshot_storage=self.screenshot_storage,
        )
        self.reporter = ReporterAgent(llm_router=self.llm_router)
        self.action_registry = ActionHandlerRegistry()
        self.action_registry.register(EmailActionHandler())
        self.action_registry.register(SlackActionHandler())
        self.action_registry.register(NotionActionHandler())
        self.action_registry.register(GitHubActionHandler())
        self.action_registry.register(N8NActionHandler())
        self.action_registry.register(WebhookActionHandler())
        self.action_agent = ActionAgent(self.action_registry)

    def run(self, site: MonitorSite) -> dict:
        run_id = str(uuid.uuid4())
        result = {
            "success": False,
            "change_detected": False,
            "change_score": 0.0,
            "alert_sent": False,
            "error": None,
            "run_id": run_id,
        }

        try:
            previous = self._latest_snapshot(site.id)
            scout_event = self.scout.run(site, previous)
            scout_event.run_id = run_id
            self._log(run_id, site, "scout", "scrape", scout_event)

            if scout_event.error:
                self._save_failed_snapshot(site, run_id, scout_event.error)
                result["error"] = scout_event.error
                return result

            new_snapshot = self._save_snapshot(site, run_id, scout_event)
            if previous is None:
                result["success"] = True
                return result

            if not scout_event.has_change:
                result["success"] = True
                return result

            analysis = self.analyst.run(scout_event, previous, new_snapshot)
            analysis.run_id = run_id
            self._log(run_id, site, "analyst", "classify", analysis)

            triggered_rules = self._evaluate_workflow_rules(site, analysis)
            if triggered_rules:
                self._log(run_id, site, "workflow", "rules_triggered", analysis)

            change_record = self._save_change(site, run_id, previous, new_snapshot, analysis)
            result["change_detected"] = analysis.has_change
            result["change_score"] = getattr(analysis, "change_score", 0.0)

            report = self.reporter.run(analysis)
            report.run_id = run_id
            self._log(run_id, site, "reporter", "summarize", report)

            action_event = self.action_agent.run(report, site, change_record)
            action_event.run_id = run_id
            self._log(run_id, site, "action", "act", action_event)
            self._save_approval_requests(run_id, site, change_record, action_event)

            if action_event.actions:
                result["alert_sent"] = any(a.get("type") == "email" and a.get("success") for a in action_event.actions)

            result["success"] = True
            return result

        except Exception as exc:
            self.db.rollback()
            result["error"] = str(exc)
            return result

    def _evaluate_workflow_rules(self, site: MonitorSite, analysis: AnalysisEvent) -> list[dict]:
        if not site.workflow_rules:
            return []
        from core.workflow.engine import WorkflowEngine
        engine = WorkflowEngine(site.workflow_rules)
        return engine.evaluate(analysis, change_score=analysis.change_score)

    def _latest_snapshot(self, site_id: int) -> Optional[MonitorSnapshot]:
        return (
            self.db.query(MonitorSnapshot)
            .filter(MonitorSnapshot.site_id == site_id, MonitorSnapshot.status == "success")
            .order_by(MonitorSnapshot.scraped_at.desc())
            .first()
        )

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
        self._persist_screenshot(snap, event)
        self.db.commit()
        return snap

    def _persist_screenshot(self, snap: MonitorSnapshot, event: ScoutEvent):
        if event.screenshot_bytes is None:
            return
        try:
            relative_path = self.screenshot_storage.save_snapshot(snap.site_id, snap.id, event.screenshot_bytes)
            snap.screenshot_path = relative_path
        except Exception:
            logger.warning("Failed to persist screenshot for snapshot %s", snap.id, exc_info=True)

    def _save_failed_snapshot(self, site: MonitorSite, run_id: str, error: str):
        snap = MonitorSnapshot(
            site_id=site.id,
            content_markdown=None,
            content_hash="",
            content_length=0,
            status="error",
            error_message=error,
        )
        self.db.add(snap)
        site.last_checked_at = datetime.utcnow()
        self.db.commit()

    def _save_change(self, site, run_id, old, new, analysis: AnalysisEvent) -> MonitorChange:
        change = MonitorChange(
            site_id=site.id,
            change_score=analysis.change_score,
            added_lines=analysis.added_lines,
            removed_lines=analysis.removed_lines,
            modified_lines=analysis.modified_lines,
            change_type=analysis.change_type,
            severity=analysis.severity,
            diff_summary=analysis.semantic_diff_summary,
            vision_description=analysis.vision_description,
            old_snapshot_id=old.id if old else None,
            new_snapshot_id=new.id if new else None,
            alert_sent=False,
            agent_reasoning={"run_id": run_id},
        )
        self.db.add(change)
        self.db.flush()
        self._persist_visual_diff(change, analysis)
        self.db.commit()
        return change

    def _persist_visual_diff(self, change: MonitorChange, analysis: AnalysisEvent):
        if analysis.visual_diff_bytes is None:
            return
        try:
            relative_path = self.screenshot_storage.save_diff(change.site_id, change.id, analysis.visual_diff_bytes)
            change.visual_diff_path = relative_path
        except Exception:
            logger.warning("Failed to persist visual diff for change %s", change.id, exc_info=True)

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

    def _save_approval_requests(self, run_id: str, site: MonitorSite, change: MonitorChange, event: ActionEvent):
        for req in event.approval_requests:
            ar = ApprovalRequest(
                run_id=run_id,
                site_id=site.id,
                change_id=change.id if change else None,
                action_type=req["type"],
                risk_score=req["risk_score"],
                payload=req["payload"],
                status="pending",
                user_id=site.user_id,
            )
            self.db.add(ar)
        self.db.commit()
