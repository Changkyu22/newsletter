"""매일 08:00 자동 뉴스 수집·발송 백그라운드 스케줄러."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import SCHEDULE_HOUR, SCHEDULE_MINUTE, SCHEDULE_TIMEZONE
from utils import logger

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=SCHEDULE_TIMEZONE)
    return _scheduler


def start_daily_scheduler(job_func: Callable[[], None]) -> BackgroundScheduler:
    """매일 지정 시각에 job_func 실행. 이미 등록된 경우 재등록하지 않음."""
    scheduler = get_scheduler()

    if scheduler.get_job("daily_newsletter"):
        if not scheduler.running:
            scheduler.start()
        return scheduler

    scheduler.add_job(
        job_func,
        trigger=CronTrigger(
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE,
            timezone=SCHEDULE_TIMEZONE,
        ),
        id="daily_newsletter",
        name="Daily Newsletter Send",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info(
            "Scheduler started — daily at %02d:%02d (%s)",
            SCHEDULE_HOUR,
            SCHEDULE_MINUTE,
            SCHEDULE_TIMEZONE,
        )

    return scheduler


def get_next_run_time() -> datetime | None:
    scheduler = get_scheduler()
    job = scheduler.get_job("daily_newsletter")
    if job and job.next_run_time:
        return job.next_run_time
    return None


def is_scheduler_running() -> bool:
    scheduler = get_scheduler()
    return scheduler.running and scheduler.get_job("daily_newsletter") is not None
