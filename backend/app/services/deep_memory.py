"""Deep memory: file-based persistent identity loaded into every agent turn.

Inspired by OpenClew's SOUL.md/IDENTITY.md/HEARTBEAT.md/USER.md/TOOLS.md/AGENT.md.

These files live on disk under `data/memory/` and are injected into the system
prompt at the start of each agent turn. They give Mira a persistent personality
and operational notes that survive process restarts.

Tiers (controls who can write):
- read_only: SOUL, IDENTITY  → only the human owner edits via Telegram cmd
- agent_writable: HEARTBEAT, USER, TOOLS, AGENT → the agent can self-edit via tools

Each file is capped to MAX_BYTES_PER_FILE (2 KB default) to keep system prompts
small. A `.bak` is written before any overwrite.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable

from app.config import settings  # noqa: F401  (kept for future tuning)

# Layout
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = _BACKEND_ROOT / "data" / "memory"

FILES = ("SOUL.md", "IDENTITY.md", "HEARTBEAT.md", "USER.md", "TOOLS.md", "AGENT.md")
# Personal single-owner project: SOUL/IDENTITY are protected so prompt-injection
# from web/HTTP results cannot rewrite the agent's values silently. The agent
# CAN propose changes (memory_propose_edit) and the owner approves via inline
# button — same model as skill drafts.
READ_ONLY: set[str] = {"SOUL.md", "IDENTITY.md"}
AGENT_WRITABLE = set(FILES) - READ_ONLY

# In-memory pending proposed edits to read-only files: name -> new body.
# Owner promotes via Telegram callback `approve_mem:NAME`.
_PROPOSED_EDITS: dict[str, str] = {}

MAX_BYTES_PER_FILE = 2_048
MAX_TOTAL_PROMPT_BYTES = 12_288

_DEFAULTS: dict[str, str] = {
    "SOUL.md": """\
# SOUL — core values

I am Mira. I exist to help one person well.

- Warmth without flattery. Honesty without sharpness.
- Concise by default. Detailed when asked.
- Proactive, not pushy.
- I respect the user's time more than my own.
- I never pretend to know what I don't.
- When wrong, I name it and adjust.
""",
    "IDENTITY.md": """\
# IDENTITY

Name: Mira
Origin: built by Jetesada as a personal secretary agent
Purpose: secretary, memory, builder of own skills
Languages: Thai (default), English
Voice: warm, professional, concise; emojis sparingly
""",
    "HEARTBEAT.md": """\
# HEARTBEAT — recent state

(auto-updated each turn; agent may overwrite)

Last topic: —
Last user mood: —
Last action: —
Open loops: —
""",
    "USER.md": """\
# USER profile

(agent updates as it learns; human may correct)

Name: —
Timezone: Asia/Bangkok
Working hours: —
Communication style: —
Long-term goals: —
Pet peeves: —
""",
    "TOOLS.md": """\
# TOOLS — self-inventory

(agent updates when authoring/using skills)

Recently authored skills: —
Skills the user has approved: —
APIs connected: —
Known gaps (things I cannot do yet): —
""",
    "AGENT.md": """\
# AGENT — operational notes

(agent appends quirks it learns about its own behavior)

- I sometimes forget to call tools when I should — bias toward calling them.
- The user prefers short answers; expand only when asked.
""",
}

_lock = asyncio.Lock()


def ensure_seeded() -> None:
    """Create memory dir + seed defaults for any missing file."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        p = MEMORY_DIR / name
        if not p.exists():
            p.write_text(_DEFAULTS[name], encoding="utf-8")


def _path(name: str) -> Path:
    if name not in FILES:
        raise ValueError(f"unknown deep-memory file: {name}")
    return MEMORY_DIR / name


def read(name: str) -> str:
    return _path(name).read_text(encoding="utf-8")


def read_all() -> dict[str, str]:
    return {n: read(n) for n in FILES}


async def write(name: str, content: str, *, allow_read_only: bool = False) -> None:
    """Atomic write with .bak backup. Refuses agent writes to read-only files."""
    if name in READ_ONLY and not allow_read_only:
        raise PermissionError(f"{name} is read-only — only the human owner may edit")
    if len(content.encode("utf-8")) > MAX_BYTES_PER_FILE:
        raise ValueError(
            f"{name}: content > {MAX_BYTES_PER_FILE} bytes; trim before writing"
        )
    async with _lock:
        p = _path(name)
        if p.exists():
            (p.with_suffix(p.suffix + ".bak")).write_bytes(p.read_bytes())
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(p)


async def append(name: str, text: str, *, allow_read_only: bool = False) -> None:
    current = read(name)
    new = current.rstrip() + "\n" + text.rstrip() + "\n"
    await write(name, new, allow_read_only=allow_read_only)


async def replace(name: str, old: str, new: str, *, allow_read_only: bool = False) -> int:
    """Replace `old` with `new`. Returns number of replacements."""
    current = read(name)
    if old not in current:
        return 0
    updated = current.replace(old, new)
    await write(name, updated, allow_read_only=allow_read_only)
    return current.count(old)


def propose_edit(name: str, new_body: str) -> None:
    """Stash a proposed change to a read-only file. Owner approves via callback."""
    if name not in READ_ONLY:
        raise ValueError(f"{name} is not read-only; use write() directly")
    if len(new_body.encode("utf-8")) > MAX_BYTES_PER_FILE:
        raise ValueError(f"proposed body > {MAX_BYTES_PER_FILE} bytes")
    _PROPOSED_EDITS[name] = new_body


def list_proposed_edits() -> dict[str, str]:
    return dict(_PROPOSED_EDITS)


async def approve_proposed_edit(name: str) -> bool:
    body = _PROPOSED_EDITS.pop(name, None)
    if body is None:
        return False
    await write(name, body, allow_read_only=True)
    return True


def discard_proposed_edit(name: str) -> bool:
    return _PROPOSED_EDITS.pop(name, None) is not None


def render_for_prompt(files: Iterable[str] = FILES) -> str:
    """Render selected files joined for inclusion in the system prompt.

    Truncates to MAX_TOTAL_PROMPT_BYTES so the prompt cannot blow up if a file
    grows. Each file is wrapped in a ```md fence with its header.
    """
    parts: list[str] = []
    used = 0
    for name in files:
        try:
            body = read(name)
        except FileNotFoundError:
            continue
        block = f"\n--- {name} ---\n{body.strip()}\n"
        size = len(block.encode("utf-8"))
        if used + size > MAX_TOTAL_PROMPT_BYTES:
            break
        parts.append(block)
        used += size
    if not parts:
        return ""
    return "## Deep memory (your persistent identity)\n" + "".join(parts)
