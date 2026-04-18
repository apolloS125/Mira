"""Core chat service — channel-agnostic entry point.

Any adapter (Telegram, web, CLI, Discord, ...) calls this.
"""
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from app.agents.graph import run_agent
from app.core.database import AsyncSessionLocal
from app.models.message import Message
from app.services.user import get_or_create_user_by_identity

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    user_id: uuid.UUID
    reply: str


async def chat(
    channel: str,
    external_user_id: str,
    message: str,
    display_name: Optional[str] = None,
    language_code: str = "th",
) -> ChatResult:
    """Run one chat turn.

    Steps:
      1. Resolve / create user via (channel, external_user_id) identity
      2. Persist user message
      3. Run agent graph
      4. Persist assistant reply
    """
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user_by_identity(
            session,
            channel=channel,
            external_id=str(external_user_id),
            display_name=display_name,
            language_code=language_code,
        )
        user_id = user.id
        session.add(Message(
            user_id=user_id,
            role="user",
            content=message,
            message_metadata={"channel": channel},
        ))
        await session.commit()

    reply = await run_agent(user_id=user_id, user_message=message)

    async with AsyncSessionLocal() as session:
        session.add(Message(
            user_id=user_id,
            role="assistant",
            content=reply,
            message_metadata={"channel": channel},
        ))
        await session.commit()

    return ChatResult(user_id=user_id, reply=reply)
