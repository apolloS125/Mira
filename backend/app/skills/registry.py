"""Skill loader — compiles DB-persisted Python code into callable Tools.

Security note: this executes arbitrary Python from the DB. We apply two layers:
  1. AST validation rejects dunder attribute access (`__class__`, `__subclasses__`,
     `__globals__`, etc.) which would otherwise let a skill walk to `os`/`subprocess`.
  2. Limited builtins + import allow-list at exec time.

This is still not a strong sandbox. Production should run skills in a separate
process/container with seccomp or use RestrictedPython.
"""
import ast
import logging
from typing import List

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.skill import Skill
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
        }
    }
    exec(compile(tree, f"<skill:{skill.name}>", "exec"), namespace)  # noqa: S102
    run = namespace.get("run")
    if run is None or not callable(run):
        raise ValueError(f"Skill '{skill.name}' must define async def run(args)")

    return Tool(
        name=skill.name,
        description=skill.description,
        parameters=skill.parameters or {"type": "object", "properties": {}},
        run=run,
        source="skill",
    )


async def load_all_skills() -> int:
    """Load all enabled skills from DB and register them. Returns count loaded."""
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Skill).where(Skill.enabled == True)  # noqa: E712
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
        await session.commit()
    unregister(name)
    return True
