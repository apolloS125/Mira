"""Secret model — encrypted per-user key/value vault for skills.

Values are encrypted at rest with Fernet using settings.mira_secret_key. Skills
reference secrets by name via `secrets.get("NAME")` — never see the raw value
unless they explicitly fetch it (and even then it's scoped to the invoking
user's row).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class Secret(Base):
    __tablename__ = "secrets"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_secret_user_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    value_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), default="skill")  # "skill" | "global"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
