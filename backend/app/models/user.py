"""User model."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    """User model - one per Telegram user."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    telegram_username: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    language_code: Mapped[str] = mapped_column(
        String(10),
        default="th",
    )
    personality_profile: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id})>"
