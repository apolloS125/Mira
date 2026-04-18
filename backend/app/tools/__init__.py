"""Tools that the agent can call.

A Tool is a named function with a JSON schema. Import this module to
auto-register the built-ins; skills can also register tools at runtime.
"""
from app.tools.registry import get_tool, list_tools, openai_schema, register  # noqa: F401

# Import built-ins to trigger @register side effects.
from app.tools import builtin_web  # noqa: F401
from app.tools import builtin_time  # noqa: F401
from app.tools import builtin_http  # noqa: F401
from app.tools import builtin_skills  # noqa: F401
from app.tools import builtin_connect  # noqa: F401
