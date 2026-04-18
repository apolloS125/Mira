"""User service - get or create users from Telegram."""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


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
