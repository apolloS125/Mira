"""Meta-tools: let the agent author, test, and list skills from chat.

Drafts are persisted in the DB so they survive restart. Confirmation is gated
in two layers: `confirm_skill` is restricted to the Telegram callback layer to
prevent prompt-injection (a malicious web result cannot trick the agent into
auto-promoting drafts that touch user data).
"""
import asyncio
import time
from typing import Any

import jsonschema

from app.skills import registry as skill_registry
from app.tools.registry import register


@register(
    name="create_skill",
    description=(
        "Author a trivial skill the agent can call in future turns. "
        "ONLY use this for skills that do NOT touch user data, accounts, or external APIs. "
        "For anything that does, use `propose_skill` so the user can review the code first. "
        "Code MUST define `async def run(args: dict)`. Allowed imports: "
        "asyncio, datetime, json, math, re, statistics, textwrap, typing, "
        "urllib.parse, zoneinfo, httpx. Skills can also call `secrets.get('NAME')` "
        "to read encrypted user secrets (set via Telegram /secret_add)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "snake_case, unique, max 64 chars"},
            "description": {"type": "string", "description": "1-2 sentences for future tool-calling LLM"},
            "parameters": {"type": "object", "description": "JSON schema for args"},
            "code": {"type": "string", "description": "Python source defining `async def run(args): ...`"},
        },
        "required": ["name", "description", "parameters", "code"],
    },
)
async def _create_skill(args: dict):
    skill = await skill_registry.upsert_skill(
        name=args["name"],
        description=args["description"],
        parameters=args.get("parameters") or {"type": "object", "properties": {}},
        code=args["code"],
        author="agent",
    )
    return {
        "ok": True,
        "name": skill.name,
        "version": skill.version,
        "message": f"Skill '{skill.name}' v{skill.version} saved and active.",
    }


@register(
    name="propose_skill",
    description=(
        "Save a skill as a DRAFT (not yet callable) so the user can review the code. "
        "ALWAYS use this instead of create_skill when the skill touches user data, "
        "accounts, or external APIs. After proposing, summarize what the skill does "
        "for the user and tell them to approve via the /drafts command in Telegram."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "parameters": {"type": "object"},
            "code": {"type": "string"},
        },
        "required": ["name", "description", "parameters", "code"],
    },
)
async def _propose_skill(args: dict):
    try:
        skill = await skill_registry.save_draft(
            name=args["name"],
            description=args["description"],
            parameters=args.get("parameters") or {"type": "object", "properties": {}},
            code=args["code"],
            author="agent",
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {
        "ok": True,
        "name": skill.name,
        "message": (
            f"Draft '{skill.name}' saved (NOT active yet). "
            "Tell the user to run /drafts in Telegram to review and approve it."
        ),
    }


@register(
    name="list_skills",
    description="List all skills (active + drafts + disabled) currently in the DB.",
    parameters={"type": "object", "properties": {}},
)
async def _list_skills(args: dict):
    return {"skills": await skill_registry.list_skills()}


@register(
    name="list_drafts",
    description="List skill drafts pending user approval.",
    parameters={"type": "object", "properties": {}},
)
async def _list_drafts(args: dict):
    return {"drafts": await skill_registry.list_drafts()}


@register(
    name="disable_skill",
    description="Disable a skill by name so the agent stops using it.",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
async def _disable(args: dict):
    ok = await skill_registry.disable_skill(args["name"])
    return {"ok": ok}


@register(
    name="show_skill_code",
    description="Return the Python source of a skill so the agent can explain or debug it.",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
async def _show_skill_code(args: dict):
    skill = await skill_registry.get_skill(args["name"])
    if skill is None:
        return {"ok": False, "error": f"no skill '{args['name']}'"}
    return {
        "ok": True,
        "name": skill.name,
        "status": skill.status,
        "version": skill.version,
        "description": skill.description,
        "parameters": skill.parameters,
        "code": skill.code,
    }


@register(
    name="test_skill",
    description=(
        "Dry-run a skill (active OR draft) once with the given args, without "
        "registering it or persisting any state. Returns timing, output, and "
        "any error. Use this before `propose_skill` confirmation to verify a "
        "draft actually works."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "args": {
                "type": "object",
                "description": "Arguments dict passed to the skill's run(args)",
            },
        },
        "required": ["name", "args"],
    },
)
async def _test_skill(args: dict):
    name = args["name"]
    sample_args = args.get("args") or {}

    skill = await skill_registry.get_skill(name)
    if skill is None:
        return {"ok": False, "error": f"no skill '{name}'"}

    # Validate args against the skill's parameter schema if one exists.
    schema = skill.parameters or {}
    try:
        if schema.get("properties") is not None:
            jsonschema.validate(instance=sample_args, schema=schema)
    except jsonschema.ValidationError as e:
        return {"ok": False, "error": f"args validation failed: {e.message}"}

    try:
        run = skill_registry.compile_isolated(skill)
    except Exception as e:
        return {"ok": False, "error": f"compile failed: {e}"}

    started = time.monotonic()
    try:
        result = await run(sample_args)
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    return {
        "ok": True,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "result": result,
    }
