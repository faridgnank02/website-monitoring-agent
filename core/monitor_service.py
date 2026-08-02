"""
Monitor Service — legacy orchestration entry point.

Delegates to MonitoringOrchestrator, which coordinates the agentic pipeline
(scout → analyst → reporter → action) and persists snapshots, changes,
audit logs, and approval requests.
"""

from sqlalchemy.orm import Session

from db.models import MonitorSite
from core.orchestrator import MonitoringOrchestrator


def run_monitor_for_site(site: MonitorSite, db: Session) -> dict:
    """
    Run one full monitoring cycle for a site.

    Returns a dict with keys:
        success (bool), change_detected (bool), change_score (float),
        alert_sent (bool), error (str | None), run_id (str)
    """
    orchestrator = MonitoringOrchestrator(db)
    return orchestrator.run(site)
