"""User service — channel-agnostic get-or-create via Identity."""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Identity
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_or_create_user_by_identity(
    session: AsyncSession,
    channel: str,
    external_id: str,
    display_name: Optional[str] = None,
    language_code: str = "th",
    profile: Optional[dict] = None,
) -> User:
    """Look up a user by (channel, external_id). Create user + identity if missing."""
    stmt = select(Identity).where(
        Identity.channel == channel,
        Identity.external_id == str(external_id),
    )
    identity = (await session.execute(stmt)).scalar_one_or_none()

    if identity is not None:
        user = (
            await session.execute(select(User).where(User.id == identity.user_id))
        ).scalar_one()
        if display_name and identity.display_name != display_name:
            identity.display_name = display_name
        return user

    # Legacy fallback: Telegram users were stored with User.telegram_id.
    if channel == "telegram":
        legacy = (
            await session.execute(
                select(User).where(User.telegram_id == int(external_id))
            )
        ).scalar_one_or_none()
        if legacy is not None:
            session.add(Identity(
                user_id=legacy.id,
                channel=channel,
                external_id=str(external_id),
                display_name=display_name or legacy.first_name,
                profile=profile or {},
            ))
            await session.flush()
            return legacy

    user = User(
        telegram_id=int(external_id) if channel == "telegram" else 0,
        telegram_username=None,
        first_name=display_name,
        language_code=language_code,
    )
    session.add(user)
    await session.flush()
    session.add(Identity(
        user_id=user.id,
        channel=channel,
        external_id=str(external_id),
        display_name=display_name,
        profile=profile or {},
    ))
    await session.flush()
    logger.info(f"✨ Created user {user.id} via {channel}:{external_id}")
    return user


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    telegram_username: Optional[str] = None,
    first_name: Optional[str] = None,
    language_code: str = "th",
) -> User:
    """Get existing user or create new one from Telegram data."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            first_name=first_name,
            language_code=language_code,
        )
        session.add(user)
        await session.flush()
        logger.info(f"✨ Created new user: {telegram_id} ({first_name})")
    else:
        # Update username/name if changed
        updated = False
        if telegram_username and user.telegram_username != telegram_username:
            user.telegram_username = telegram_username
            updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if updated:
            logger.info(f"🔄 Updated user: {telegram_id}")

    return user


async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> Optional[User]:
    """Find user by Telegram ID."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
