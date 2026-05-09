"""Skill loader — compiles DB-persisted Python code into callable Tools.

Security note: this executes arbitrary Python from the DB. We apply two layers:
  1. AST validation rejects dunder attribute access (`__class__`, `__subclasses__`,
     `__globals__`, etc.) which would otherwise let a skill walk to `os`/`subprocess`.
  2. Limited builtins + import allow-list at exec time.

This is still not a strong sandbox. Production should run skills in a separate
process/container with seccomp or use RestrictedPython.
"""
import ast
import asyncio
import json
import logging
from typing import Any, Callable, List

from sqlalchemy import select

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.skill import Skill
from app.services.secrets import ambient_secrets
from app.tools.base import Tool
from app.tools.registry import register_tool, unregister

logger = logging.getLogger(__name__)

# Modules a skill may import. Extend carefully.
ALLOWED_IMPORTS = {
    "asyncio",
    "datetime",
    "json",
    "math",
    "re",
    "statistics",
    "textwrap",
    "typing",
    "urllib.parse",
    "zoneinfo",
    "httpx",
}

# Dunder attributes/names that enable sandbox escape. Any reference rejected.
_FORBIDDEN_DUNDERS = {
    "__class__", "__bases__", "__base__", "__mro__", "__subclasses__",
    "__globals__", "__builtins__", "__import__", "__loader__", "__spec__",
    "__dict__", "__getattribute__", "__getattr__", "__setattr__", "__delattr__",
    "__code__", "__closure__", "__func__", "__self__", "__module__",
    "__init_subclass__", "__class_getitem__", "__reduce__", "__reduce_ex__",
    "__subclasshook__", "__init__", "__new__", "__call__",
}


class _SkillASTValidator(ast.NodeVisitor):
    """Reject any AST node that references a forbidden dunder name."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def _check(self, name: str, node: ast.AST) -> None:
        if name in _FORBIDDEN_DUNDERS or (
            name.startswith("__") and name.endswith("__") and len(name) > 4
        ):
            self.errors.append(
                f"forbidden dunder reference '{name}' at line {getattr(node, 'lineno', '?')}"
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._check(node.attr, node)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self._check(node.id, node)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # Block string-form access via getattr(obj, "__class__"). Conservative:
        # any string constant matching a forbidden dunder fails.
        if isinstance(node.value, str):
            self._check(node.value, node)
        self.generic_visit(node)


def _validate_skill_ast(code: str, name: str) -> ast.Module:
    tree = ast.parse(code, filename=f"<skill:{name}>")
    v = _SkillASTValidator()
    v.visit(tree)
    if v.errors:
        raise ValueError(f"Skill '{name}' rejected: {'; '.join(v.errors)}")
    return tree


def _make_safe_import():
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".")[0]
        if root not in {n.split(".")[0] for n in ALLOWED_IMPORTS}:
            raise ImportError(f"Skill import '{name}' not allowed")
        return real_import(name, globals, locals, fromlist, level)

    return safe_import


def compile_skill(skill: Skill) -> Tool:
    """Compile a Skill row into a Tool. Expects code to define `async def run(args): ...`"""
    tree = _validate_skill_ast(skill.code, skill.name)
    namespace: dict = {
        "__builtins__": {
            "__import__": _make_safe_import(),
            "len": len, "range": range, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict, "set": set, "tuple": tuple,
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "sorted": sorted, "enumerate": enumerate, "zip": zip,
            "print": print, "isinstance": isinstance, "any": any, "all": all,
            "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
        },
        # Per-user encrypted secrets, scoped via ContextVar at invoke time.
        "secrets": ambient_secrets,
    }
    exec(compile(tree, f"<skill:{skill.name}>", "exec"), namespace)  # noqa: S102
    run = namespace.get("run")
    if run is None or not callable(run):
        raise ValueError(f"Skill '{skill.name}' must define async def run(args)")

    guarded = _guard_run(run, skill.name)

    return Tool(
        name=skill.name,
        description=skill.description,
        parameters=skill.parameters or {"type": "object", "properties": {}},
        run=guarded,
        source="skill",
    )


def _guard_run(run: Callable, skill_name: str) -> Callable:
    """Wrap a skill's run() with timeout, output cap, and error containment.

    Returns a structured {ok, result|error} dict so a broken skill never crashes
    the agent loop. Note: asyncio.wait_for cannot kill pure-CPU loops — this is
    a soft guard. Hard isolation would require a subprocess.
    """
    timeout = settings.skill_run_timeout_sec
    max_bytes = settings.skill_max_output_bytes

    async def guarded(args: Any) -> Any:
        try:
            coro = run(args)
            if not asyncio.iscoroutine(coro):
                return {"ok": False, "error": f"skill '{skill_name}' run() must be async"}
            result = await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return {"ok": False, "error": f"skill '{skill_name}' timed out after {timeout}s"}
        except Exception as e:
            logger.warning(f"Skill '{skill_name}' raised: {e}")
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

        try:
            payload = json.dumps(result, default=str)
        except Exception:
            payload = str(result)
        if len(payload.encode("utf-8")) > max_bytes:
            return {
                "ok": True,
                "truncated": True,
                "result": payload[:max_bytes] + "…[truncated]",
            }
        return result

    return guarded


async def load_all_skills() -> int:
    """Load all active skills from DB and register them. Drafts are skipped."""
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Skill).where(Skill.enabled == True, Skill.status == "active")  # noqa: E712
        )).scalars().all()

    loaded = 0
    for s in rows:
        try:
            register_tool(compile_skill(s))
            loaded += 1
        except Exception as e:
            logger.warning(f"Skipping skill '{s.name}': {e}")
    logger.info(f"Loaded {loaded}/{len(rows)} skills from DB")
    return loaded


async def upsert_skill(
    name: str,
    description: str,
    parameters: dict,
    code: str,
    author: str = "agent",
) -> Skill:
    """Create or update a skill and hot-reload it into the tool registry."""
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(
            select(Skill).where(Skill.name == name)
        )).scalar_one_or_none()

        if existing is None:
            skill = Skill(
                name=name,
                description=description,
                parameters=parameters,
                code=code,
                author=author,
            )
            session.add(skill)
        else:
            existing.description = description
            existing.parameters = parameters
            existing.code = code
            existing.version = (existing.version or 1) + 1
            existing.enabled = True
            skill = existing
        await session.commit()
        await session.refresh(skill)

    # Compile + hot-register.
    unregister(name)
    register_tool(compile_skill(skill))
    return skill


async def list_skills() -> List[dict]:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Skill))).scalars().all()
    return [
        {
            "name": s.name,
            "description": s.description,
            "enabled": s.enabled,
            "author": s.author,
            "version": s.version,
        }
        for s in rows
    ]


async def disable_skill(name: str) -> bool:
    async with AsyncSessionLocal() as session:
        skill = (await session.execute(
            select(Skill).where(Skill.name == name)
        )).scalar_one_or_none()
        if skill is None:
            return False
        skill.enabled = False
        skill.status = "disabled"
        await session.commit()
    unregister(name)
    return True


async def save_draft(
    name: str,
    description: str,
    parameters: dict,
    code: str,
    author: str = "agent",
    confirmation_required: bool = False,
) -> Skill:
    """Persist a skill as a draft (not registered as a tool)."""
    # Validate AST early so we don't store a broken draft.
    _validate_skill_ast(code, name)

    async with AsyncSessionLocal() as session:
        existing = (await session.execute(
            select(Skill).where(Skill.name == name)
        )).scalar_one_or_none()

        if existing is None:
            skill = Skill(
                name=name,
                description=description,
                parameters=parameters,
                code=code,
                author=author,
                enabled=False,
                status="draft",
                confirmation_required=confirmation_required,
            )
            session.add(skill)
        else:
            existing.description = description
            existing.parameters = parameters
            existing.code = code
            existing.status = "draft"
            existing.enabled = False
            existing.confirmation_required = confirmation_required
            skill = existing
        await session.commit()
        await session.refresh(skill)
    return skill


async def confirm_draft(name: str) -> Skill | None:
    """Promote a draft to active and hot-register it."""
    async with AsyncSessionLocal() as session:
        skill = (await session.execute(
            select(Skill).where(Skill.name == name)
        )).scalar_one_or_none()
        if skill is None or skill.status != "draft":
            return None
        skill.status = "active"
        skill.enabled = True
        skill.version = (skill.version or 1) + 1
        await session.commit()
        await session.refresh(skill)

    unregister(name)
    register_tool(compile_skill(skill))
    return skill


async def list_drafts() -> List[dict]:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Skill).where(Skill.status == "draft")
        )).scalars().all()
    return [
        {
            "name": s.name,
            "description": s.description,
            "confirmation_required": s.confirmation_required,
            "version": s.version,
        }
        for s in rows
    ]


async def discard_draft(name: str) -> bool:
    async with AsyncSessionLocal() as session:
        skill = (await session.execute(
            select(Skill).where(Skill.name == name, Skill.status == "draft")
        )).scalar_one_or_none()
        if skill is None:
            return False
        await session.delete(skill)
        await session.commit()
    return True


async def get_skill(name: str) -> Skill | None:
    async with AsyncSessionLocal() as session:
        return (await session.execute(
            select(Skill).where(Skill.name == name)
        )).scalar_one_or_none()


def compile_isolated(skill: Skill) -> Callable:
    """Compile a skill but do not register. Returns guarded run() for dry-run testing."""
    return compile_skill(skill).run
