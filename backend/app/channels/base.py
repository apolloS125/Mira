from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class InboundMessage:
    """Normalized inbound message from any channel."""
    channel: str                       # e.g. "telegram", "discord", "web"
    external_user_id: str              # stable per-channel user id
    text: str
    display_name: Optional[str] = None
    language_code: str = "th"


class ChannelAdapter(Protocol):
    """What every channel adapter implements.

    Typical lifecycle:
      - `start()` on app startup (connect websocket, set webhook, etc.)
      - `stop()` on shutdown
      - `send_reply(external_user_id, text)` when Mira produces a reply

    The inbound path is channel-specific — Telegram posts to a FastAPI webhook,
    Discord runs a gateway loop — so it's not part of this Protocol. What
    matters is that the inbound handler ends up calling `core_chat(...)`.
    """

    channel: str  # "telegram", "discord", ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send_reply(self, external_user_id: str, text: str) -> None: ...
