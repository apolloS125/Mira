"""Tool protocol + dataclass.

A Tool has:
  - name (snake_case, unique)
  - description (1-2 lines, shown to LLM)
  - parameters (JSON Schema for arguments)
  - run (async function: dict -> Any)
"""
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON schema (OpenAI function format)
    run: Callable[[dict], Awaitable[Any]]
    source: str = "builtin"  # "builtin" | "skill" | "connector"
