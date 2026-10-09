"""
APScheduler integration for automatic pipeline polling.

Runs the pipeline on a configurable interval without external
cron jobs or task queues — everything stays in-process.
"""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from api.database import SessionLocal
from api.pipeline_service import run_pipeline

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _scheduled_run() -> None:
    """Callback executed by APScheduler on each interval."""
    logger.info("Scheduled pipeline run triggered.")
    db = SessionLocal()
    try:
        run_pipeline(db, trigger="scheduled")
    except Exception:
        logger.exception("Scheduled pipeline run failed.")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler.

    Reads SNOW_POLL_INTERVAL_SECONDS from environment (default: 300).
    """
    global _scheduler

    interval = int(os.getenv("SNOW_POLL_INTERVAL_SECONDS", "300"))

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _scheduled_run,
        trigger=IntervalTrigger(seconds=interval),
        id="pipeline_poll",
        name="ServiceNow Pipeline Poll",
        replace_existing=True,
    )
    _scheduler.start()

    logger.info("Scheduler started — polling every %d seconds.", interval)
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
        _scheduler = None


def get_schedule_info() -> dict:
    """Return current scheduler status and configuration."""
    interval = int(os.getenv("SNOW_POLL_INTERVAL_SECONDS", "300"))

    if _scheduler and _scheduler.running:
        job = _scheduler.get_job("pipeline_poll")
        next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
        return {
            "active": True,
            "interval_seconds": interval,
            "next_run_at": next_run,
        }

    return {
        "active": False,
        "interval_seconds": interval,
        "next_run_at": None,
    }
