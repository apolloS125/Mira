"""Clock / timezone helper."""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.tools.registry import register


@register(
    name="time_now",
    description="Get the current date and time in a given IANA timezone (default Asia/Bangkok).",
    parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone, e.g. 'Asia/Bangkok', 'UTC', 'America/New_York'",
                "default": "Asia/Bangkok",
            }
        },
    },
)
async def _run(args: dict):
    tz = args.get("timezone") or "Asia/Bangkok"
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:
        now = datetime.now(ZoneInfo("Asia/Bangkok"))
        tz = "Asia/Bangkok"
    return {
        "timezone": tz,
        "iso": now.isoformat(),
        "human": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }
