"""Meta-tools: let the agent author and list skills from chat.

The propose → confirm flow exists so Mira asks the user before saving
anything that touches their accounts. Always prefer it over `create_skill`
for anything non-trivial.
"""
from app.skills import registry as skill_registry
from app.tools.registry import register

# In-memory drafts keyed by name. Cleared on process restart — deliberate:
# drafts are meant to be confirmed in the same conversation.
_drafts: dict[str, dict] = {}


@register(
    name="create_skill",
    description=(
        "Author a new skill (Python tool) that the agent can call in future turns. "
        "The code MUST define `async def run(args: dict)` and may import from: "
        "asyncio, datetime, json, math, re, statistics, textwrap, typing, "
        "urllib.parse, zoneinfo, httpx. Use this when the user asks Mira to 'learn' "
        "a new capability or when a pattern will repeat."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "snake_case, unique, max 64 chars",
            },
            "description": {
                "type": "string",
                "description": "1-2 sentences, shown to future tool-calling LLM",
            },
            "parameters": {
                "type": "object",
                "description": "JSON schema for args (OpenAI function format)",
            },
            "code": {
                "type": "string",
                "description": "Python source defining `async def run(args): ...` returning JSON-serializable",
            },
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
        "message": f"Skill '{skill.name}' v{skill.version} saved and loaded.",
    }


@register(
    name="list_skills",
    description="List all skills currently installed (including enabled state).",
    parameters={"type": "object", "properties": {}},
)
async def _list_skills(args: dict):
    return {"skills": await skill_registry.list_skills()}


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
    name="propose_skill",
    description=(
        "Draft a skill without saving it, so the user can review the code first. "
        "Use this INSTEAD of create_skill whenever the skill touches user data, "
        "accounts, or external APIs. After proposing, show the user the code "
        "and ask for confirmation, then call `confirm_skill` with the same name."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "snake_case, unique, max 64 chars"},
            "description": {"type": "string"},
            "parameters": {"type": "object", "description": "JSON schema for args"},
            "code": {"type": "string", "description": "Python defining `async def run(args): ...`"},
        },
        "required": ["name", "description", "parameters", "code"],
    },
)
async def _propose_skill(args: dict):
    _drafts[args["name"]] = {
        "name": args["name"],
        "description": args["description"],
        "parameters": args.get("parameters") or {"type": "object", "properties": {}},
        "code": args["code"],
    }
    return {
        "ok": True,
        "name": args["name"],
        "message": (
            f"Draft '{args['name']}' prepared but NOT saved. "
            "Show the code to the user and call `confirm_skill` once they agree."
        ),
    }


@register(
    name="confirm_skill",
    description=(
        "Save a previously proposed skill after the user has approved it. "
        "Only call this after the user explicitly confirms."
    ),
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
async def _confirm_skill(args: dict):
    draft = _drafts.pop(args["name"], None)
    if draft is None:
        return {"ok": False, "error": f"no draft named '{args['name']}' — propose it first"}
    skill = await skill_registry.upsert_skill(
        name=draft["name"],
        description=draft["description"],
        parameters=draft["parameters"],
        code=draft["code"],
        author="agent",
    )
    return {
        "ok": True,
        "name": skill.name,
        "version": skill.version,
        "message": f"Skill '{skill.name}' v{skill.version} saved and loaded.",
    }


@register(
    name="list_drafts",
    description="List pending (unsaved) skill drafts proposed in this process.",
    parameters={"type": "object", "properties": {}},
)
async def _list_drafts(args: dict):
    return {"drafts": [{"name": n, "description": d["description"]} for n, d in _drafts.items()]}
