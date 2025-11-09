#!/usr/bin/env python3
"""
Scheduler for Monitor Agent
Runs monitoring tasks based on cron schedules defined in sites.yaml
"""

import logging
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from main import MonitorAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('Scheduler')


def parse_schedule(schedule_str: str) -> dict:
    """
    Parse schedule string from sites.yaml into cron parameters.
    
    Examples:
        "daily 10:00" -> {'hour': 10, 'minute': 0}
        "twice-daily" -> Run at 09:00 and 18:00
        "hourly" -> {'minute': 0}
        "every 6 hours" -> {'hour': '*/6'}
        "monday 14:30" -> {'day_of_week': 'mon', 'hour': 14, 'minute': 30}
    
    Args:
        schedule_str: Schedule string from configuration
        
    Returns:
        dict: Cron parameters for APScheduler
    """
    schedule_str = schedule_str.lower().strip()
    
    # Daily at specific time
    if schedule_str.startswith('daily'):
        if ' ' in schedule_str:
            time_part = schedule_str.split(' ')[1]
            hour, minute = time_part.split(':')
            return {'hour': int(hour), 'minute': int(minute)}
        return {'hour': 10, 'minute': 0}  # Default: 10:00
    
    # Twice daily (morning and evening)
    elif schedule_str == 'twice-daily':
        # This will create two separate jobs
        return [
            {'hour': 9, 'minute': 0},
            {'hour': 18, 'minute': 0}
        ]
    
    # Hourly
    elif schedule_str == 'hourly':
        return {'minute': 0}
    
    # Every X hours
    elif 'every' in schedule_str and 'hour' in schedule_str:
        hours = schedule_str.split()[1]
        return {'hour': f'*/{hours}'}
    
    # Specific day of week with time
    elif any(day in schedule_str for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
        parts = schedule_str.split()
        day_map = {
            'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed',
            'thursday': 'thu', 'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
        }
        day = day_map.get(parts[0])
        if len(parts) > 1:
            hour, minute = parts[1].split(':')
            return {'day_of_week': day, 'hour': int(hour), 'minute': int(minute)}
        return {'day_of_week': day, 'hour': 10, 'minute': 0}
    
    # Default: daily at 10:00
    logger.warning(f"Unknown schedule format '{schedule_str}', using default: daily 10:00")
    return {'hour': 10, 'minute': 0}


def run_monitoring_for_site(site_config: dict):
    """
    Run monitoring for a specific site.
    
    Args:
        site_config: Site configuration dict from sites.yaml
    """
    logger.info(f"=== Starting scheduled monitoring ===")
    logger.info(f"Site: {site_config.get('instruction', 'Unknown')}")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        agent = MonitorAgent()
        agent.monitor_site(site_config)
        logger.info(f"Monitoring completed successfully")
    except Exception as e:
        logger.error(f"Monitoring failed: {e}", exc_info=True)
    
    logger.info(f"=== Monitoring finished ===\n")


def setup_scheduler():
    """
    Setup APScheduler with jobs from sites.yaml.
    
    Returns:
        BlockingScheduler: Configured scheduler instance
    """
    scheduler = BlockingScheduler()
    agent = MonitorAgent()
    sites = agent.load_sites_config('config/sites.yaml')
    
    logger.info(f"Loading {len(sites)} site(s) from configuration...")
    
    job_count = 0
    for idx, site in enumerate(sites):
        if not site.get('active', True):
            logger.info(f"Skipping inactive site: {site.get('instruction', 'Unknown')}")
            continue
        
        schedule_str = site.get('schedule', 'daily 10:00')
        instruction = site.get('instruction', 'Unknown')
        
        # Parse schedule
        cron_params = parse_schedule(schedule_str)
        
        # Handle twice-daily (creates 2 jobs)
        if isinstance(cron_params, list):
            for i, params in enumerate(cron_params):
                job_id = f"site_{idx}_job_{i}"
                scheduler.add_job(
                    run_monitoring_for_site,
                    trigger=CronTrigger(**params),
                    args=[site],
                    id=job_id,
                    name=f"{instruction} (job {i+1})"
                )
                job_count += 1
                logger.info(f"Scheduled: '{instruction}' at {params}")
        else:
            job_id = f"site_{idx}"
            scheduler.add_job(
                run_monitoring_for_site,
                trigger=CronTrigger(**cron_params),
                args=[site],
                id=job_id,
                name=instruction
            )
            job_count += 1
            logger.info(f"Scheduled: '{instruction}' with {cron_params}")
    
    if job_count == 0:
        logger.warning("No active jobs scheduled! Check your sites.yaml configuration.")
    else:
        logger.info(f"\nTotal jobs scheduled: {job_count}")
    
    return scheduler


def main():
    """
    Main entry point for the scheduler.
    """
    logger.info("=" * 60)
    logger.info("Monitor Agent Scheduler Starting")
    logger.info("=" * 60)
    
    try:
        scheduler = setup_scheduler()
        
        logger.info("\nScheduler running... Press Ctrl+C to stop.")
        logger.info("=" * 60 + "\n")
        
        # Start the scheduler (blocking)
        scheduler.start()
        
        # After starting, print next run times
        logger.info("\nNext scheduled runs:")
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            if next_run:
                logger.info(f"  - {job.name}: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        
    except KeyboardInterrupt:
        logger.info("\nScheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
