"""Memory model for semantic/episodic/procedural memory."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, DateTime, Text, ForeignKey, Float, Integer, Boolean, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class Memory(Base):
    """Long-term memory - facts, events, preferences about the user."""

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )  # semantic, episodic, procedural
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(
        Float,
        default=0.5,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
    )
    source_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    memory_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<Memory(type={self.type}, content={self.content[:50]}...)>"
