"""In-memory tool registry.

Skills / built-ins register here. The agent loop reads `list_tools()` and
`openai_schema()` to advertise callable tools to the LLM.
"""
import logging
from typing import Awaitable, Callable, List, Optional

from app.tools.base import Tool

logger = logging.getLogger(__name__)

_tools: dict[str, Tool] = {}


def register(
    name: str,
    description: str,
    parameters: dict,
    source: str = "builtin",
) -> Callable[[Callable[[dict], Awaitable]], Callable]:
    """Decorator to register an async tool function."""

    def decorator(fn: Callable[[dict], Awaitable]) -> Callable:
        _tools[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            run=fn,
            source=source,
        )
        logger.info(f"Registered tool: {name} ({source})")
        return fn

    return decorator


def register_tool(tool: Tool) -> None:
    """Register a Tool instance directly (used by skill loader)."""
    _tools[tool.name] = tool
    logger.info(f"Registered tool: {tool.name} ({tool.source})")


def unregister(name: str) -> bool:
    return _tools.pop(name, None) is not None


def get_tool(name: str) -> Optional[Tool]:
    return _tools.get(name)


def list_tools() -> List[Tool]:
    return list(_tools.values())


def openai_schema() -> list[dict]:
    """Return OpenAI/LiteLLM-compatible tools array."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in _tools.values()
    ]
