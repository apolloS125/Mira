"""Cron scheduler — loads CronJob rows from DB and runs them via APScheduler.

Each job fires `run_agent(user_id, prompt)` and sends the reply back via Telegram.
"""
import logging
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.cronjob import CronJob

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="Asia/Bangkok")


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler


async def _fire_job(job_id: str, user_id: str, prompt: str) -> None:
    """Execute one cron job: run agent, send reply via Telegram, update last_run_at."""
    from app.agents.graph import run_agent
    from app.channels.telegram.bot import telegram_app
    from app.config import settings

    uid = uuid.UUID(user_id)
    logger.info(f"Firing cron job {job_id}: {prompt[:60]}")
    try:
        reply = await run_agent(user_id=uid, user_message=prompt)
    except Exception as e:
        logger.exception(f"Cron job {job_id} agent error: {e}")
        reply = f"❌ Cron job error: {e}"

    # Send reply to owner via Telegram
    if settings.owner_telegram_id:
        try:
            await telegram_app.bot.send_message(
                chat_id=settings.owner_telegram_id,
                text=f"⏰ *{prompt[:40]}*\n\n{reply}",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"Failed to send cron reply via Telegram: {e}")

    # Update last_run_at
    async with AsyncSessionLocal() as session:
        job = await session.get(CronJob, uuid.UUID(job_id))
        if job:
            job.last_run_at = datetime.now(timezone.utc)
            await session.commit()


def _register_job(job: CronJob) -> None:
    parts = job.cron_expr.split()
    if len(parts) != 5:
        logger.warning(f"Invalid cron expr for job {job.id}: {job.cron_expr!r}")
        return
    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone="Asia/Bangkok",
    )
    _scheduler.add_job(
        _fire_job,
        trigger=trigger,
        id=str(job.id),
        args=[str(job.id), str(job.user_id), job.prompt],
        replace_existing=True,
    )
    logger.info(f"Scheduled job '{job.name}' ({job.cron_expr})")


async def load_all_jobs() -> int:
    """Load all enabled CronJobs from DB and register them. Called on startup."""
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(CronJob).where(CronJob.enabled == True)  # noqa: E712
            )
        ).scalars().all()
    for job in rows:
        _register_job(job)
    return len(rows)


async def add_job(job: CronJob) -> None:
    """Persist a new job to DB and register it in the scheduler."""
    async with AsyncSessionLocal() as session:
        session.add(job)
        await session.commit()
        await session.refresh(job)
    _register_job(job)


async def remove_job(job_id: uuid.UUID) -> bool:
    """Disable a job in DB and remove from scheduler. Returns False if not found."""
    async with AsyncSessionLocal() as session:
        job = await session.get(CronJob, job_id)
        if not job:
            return False
        job.enabled = False
        await session.commit()
    try:
        _scheduler.remove_job(str(job_id))
    except Exception:
        pass
    return True


async def list_jobs(user_id: uuid.UUID) -> list[CronJob]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(CronJob).where(
                    CronJob.user_id == user_id,
                    CronJob.enabled == True,  # noqa: E712
                )
            )
        ).scalars().all()
    return list(rows)
