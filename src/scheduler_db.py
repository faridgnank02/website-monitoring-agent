#!/usr/bin/env python3
"""
DB-backed scheduler for Monitor Agent.
Reads active sites from the database (not sites.yaml) and schedules
them using their schedule_cron field.

Run standalone:
    python src/scheduler_db.py

Or alongside the API server (the API uses FastAPI background tasks for
manual triggers; this process handles the scheduled runs).
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from db.base import SessionLocal, init_db
from db.models import MonitorSite
from core.monitor_service import run_monitor_for_site

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SchedulerDB")


def check_site(site_id: int):
    """
    Job function called by APScheduler.
    Opens its own DB session, runs the monitor cycle, closes session.
    """
    db = SessionLocal()
    try:
        site = db.query(MonitorSite).filter(MonitorSite.id == site_id, MonitorSite.active == True).first()
        if not site:
            logger.warning(f"Site {site_id} not found or inactive — skipping.")
            return
        logger.info(f"[site {site_id}] Running scheduled check: {site.instruction[:60]}")
        result = run_monitor_for_site(site, db)
        if result.get("success"):
            logger.info(
                f"[site {site_id}] Orchestrated run {result.get('run_id')} | change_detected={result['change_detected']} | alert_sent={result['alert_sent']}"
            )
        else:
            logger.error(f"[site {site_id}] Check failed: {result['error']}")
    finally:
        db.close()


def check_all_sites():
    """
    Fallback job that checks all active sites whose last_checked_at is stale.
    Useful if a site's cron is not yet registered (e.g. added via API after scheduler start).
    Runs every 10 minutes.
    """
    db = SessionLocal()
    try:
        sites = db.query(MonitorSite).filter(MonitorSite.active == True).all()
        logger.info(f"Polling check: {len(sites)} active sites.")
        for site in sites:
            run_monitor_for_site(site, db)
    finally:
        db.close()


def load_jobs(scheduler: BlockingScheduler):
    """Register one APScheduler job per active site using its schedule_cron."""
    db = SessionLocal()
    try:
        sites = db.query(MonitorSite).filter(MonitorSite.active == True).all()
        for site in sites:
            cron = site.schedule_cron or "0 */6 * * *"
            job_id = f"site_{site.id}"
            # Remove existing job if re-loading
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass
            try:
                parts = cron.split()
                trigger = CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                )
                scheduler.add_job(
                    check_site,
                    trigger=trigger,
                    args=[site.id],
                    id=job_id,
                    name=site.instruction[:60],
                    replace_existing=True,
                )
                logger.info(f"Scheduled site {site.id} with cron '{cron}': {site.instruction[:60]}")
            except Exception as e:
                logger.error(f"Failed to schedule site {site.id}: {e}")
    finally:
        db.close()


def main():
    logger.info("=" * 60)
    logger.info("Monitor Agent DB Scheduler starting")
    logger.info("=" * 60)

    # Ensure tables exist
    init_db()

    scheduler = BlockingScheduler(timezone="UTC")

    # Load per-site jobs
    load_jobs(scheduler)

    # Safety net: re-sync jobs every 10 min (picks up new sites added via API)
    scheduler.add_job(
        load_jobs,
        "interval",
        minutes=10,
        args=[scheduler],
        id="reload_jobs",
        name="Reload site jobs",
    )

    logger.info("\nScheduler running... Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
