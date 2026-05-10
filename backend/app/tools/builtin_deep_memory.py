"""Tools for the agent to self-edit its persistent identity files.

Read-only files (SOUL.md, IDENTITY.md) cannot be modified through these tools —
the human owner edits them via Telegram commands. The agent can read all six.
"""
from __future__ import annotations

from app.services import deep_memory as dm
from app.tools.registry import register


@register(
    name="memory_read",
    description=(
        "Read one of your persistent identity files. "
        f"Files: {', '.join(dm.FILES)}."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file": {"type": "string", "enum": list(dm.FILES)},
        },
        "required": ["file"],
    },
)
async def _memory_read(args: dict):
    name = args["file"]
    try:
        return {"ok": True, "file": name, "content": dm.read(name)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@register(
    name="memory_append",
    description=(
        "Append a short line/section to a writable identity file. "
        "Writable: HEARTBEAT.md, USER.md, TOOLS.md, AGENT.md. "
        "SOUL.md and IDENTITY.md are protected — use memory_propose_edit instead."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file": {"type": "string", "enum": list(dm.AGENT_WRITABLE)},
            "text": {"type": "string", "description": "Plain markdown to append"},
        },
        "required": ["file", "text"],
    },
)
async def _memory_append(args: dict):
    try:
        await dm.append(args["file"], args["text"])
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@register(
    name="memory_replace",
    description=(
        "Replace an exact substring inside a writable identity file. "
        "Use to update HEARTBEAT after each turn or correct USER profile. "
        "SOUL/IDENTITY are protected — use memory_propose_edit."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file": {"type": "string", "enum": list(dm.AGENT_WRITABLE)},
            "old": {"type": "string"},
            "new": {"type": "string"},
        },
        "required": ["file", "old", "new"],
    },
)
async def _memory_replace(args: dict):
    try:
        n = await dm.replace(args["file"], args["old"], args["new"])
        return {"ok": n > 0, "replacements": n}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@register(
    name="memory_overwrite",
    description=(
        "Fully overwrite a writable identity file. Use sparingly — prefer "
        "memory_replace for surgical edits. Max 2KB per file. "
        "SOUL/IDENTITY are protected — use memory_propose_edit."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file": {"type": "string", "enum": list(dm.AGENT_WRITABLE)},
            "content": {"type": "string"},
        },
        "required": ["file", "content"],
    },
)
async def _memory_overwrite(args: dict):
    try:
        await dm.write(args["file"], args["content"])
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@register(
    name="memory_propose_edit",
    description=(
        "Propose a change to a protected identity file (SOUL.md or IDENTITY.md). "
        "The proposal is queued and the OWNER must approve via Telegram inline "
        "button before it takes effect. Use this when the user explicitly asks "
        "you to change your values, name, persona, or origin. After calling, "
        "tell the user to run /mem_drafts to review and approve."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file": {"type": "string", "enum": list(dm.READ_ONLY)},
            "new_body": {
                "type": "string",
                "description": "Full new body of the file (max 2KB)",
            },
        },
        "required": ["file", "new_body"],
    },
)
async def _memory_propose_edit(args: dict):
    try:
        dm.propose_edit(args["file"], args["new_body"])
        return {
            "ok": True,
            "file": args["file"],
            "message": (
                f"Edit to {args['file']} queued. Tell the user to run "
                "/mem_drafts in Telegram to approve."
            ),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
