"""Built-in cron tools — let the agent schedule, list, and delete cron jobs."""
import uuid

from app.tools.registry import register_tool
from app.tools.base import Tool


async def _schedule_job(args: dict) -> dict:
    from app.models.cronjob import CronJob
    from app.services.scheduler import add_job

    name = args.get("name", "").strip()
    prompt = args.get("prompt", "").strip()
    cron_expr = args.get("cron_expr", "").strip()
    user_id_str = args.get("user_id", "")

    if not all([name, prompt, cron_expr, user_id_str]):
        return {"error": "name, prompt, cron_expr, and user_id are required"}

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return {"error": f"invalid user_id: {user_id_str!r}"}

    job = CronJob(user_id=user_id, name=name, prompt=prompt, cron_expr=cron_expr)
    await add_job(job)
    return {"ok": True, "job_id": str(job.id), "name": name, "cron_expr": cron_expr}


async def _list_jobs(args: dict) -> dict:
    from app.services.scheduler import list_jobs

    user_id_str = args.get("user_id", "")
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return {"error": f"invalid user_id: {user_id_str!r}"}

    jobs = await list_jobs(user_id)
    return {
        "jobs": [
            {
                "id": str(j.id),
                "name": j.name,
                "cron_expr": j.cron_expr,
                "prompt": j.prompt,
                "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
            }
            for j in jobs
        ]
    }


async def _delete_job(args: dict) -> dict:
    from app.services.scheduler import remove_job

    job_id_str = args.get("job_id", "")
    try:
        job_id = uuid.UUID(job_id_str)
    except ValueError:
        return {"error": f"invalid job_id: {job_id_str!r}"}

    ok = await remove_job(job_id)
    return {"ok": ok}


register_tool(Tool(
    name="schedule_job",
    description=(
        "Schedule a recurring cron job. Mira will run the given prompt on the cron schedule "
        "and send the result back to you via Telegram. "
        "cron_expr format: 'minute hour day month day_of_week' (standard 5-field cron). "
        "Examples: '0 9 * * *' = every day 9am, '0 9 * * 1' = every Monday 9am."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Short label for this job"},
            "prompt": {"type": "string", "description": "What to ask Mira when the job fires"},
            "cron_expr": {"type": "string", "description": "5-field cron expression"},
            "user_id": {"type": "string", "description": "UUID of the owner user"},
        },
        "required": ["name", "prompt", "cron_expr", "user_id"],
    },
    run=_schedule_job,
))

register_tool(Tool(
    name="list_cron_jobs",
    description="List all active cron jobs for a user.",
    parameters={
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "UUID of the owner user"},
        },
        "required": ["user_id"],
    },
    run=_list_jobs,
))

register_tool(Tool(
    name="delete_cron_job",
    description="Delete (disable) a cron job by its ID.",
    parameters={
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "UUID of the cron job to delete"},
        },
        "required": ["job_id"],
    },
    run=_delete_job,
))
