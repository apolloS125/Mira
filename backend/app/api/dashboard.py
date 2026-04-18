"""Dashboard REST API — read-only views over users, messages, memories."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.message import Message
from app.models.user import User
from app.services import memory as memory_svc

router = APIRouter(prefix="/api", tags=["dashboard"])


class UserOut(BaseModel):
    id: uuid.UUID
    telegram_id: int
    telegram_username: Optional[str] = None
    first_name: Optional[str] = None
    language_code: str
    created_at: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: str


class MemoryOut(BaseModel):
    id: str
    type: str
    content: str


@router.get("/users", response_model=List[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(desc(User.created_at)))
    return [
        UserOut(
            id=u.id,
            telegram_id=u.telegram_id,
            telegram_username=u.telegram_username,
            first_name=u.first_name,
            language_code=u.language_code,
            created_at=u.created_at.isoformat(),
        )
        for u in result.scalars().all()
    ]


@router.get("/users/{user_id}/messages", response_model=List[MessageOut])
async def list_messages(
    user_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Message)
        .where(Message.user_id == user_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in rows
    ]


@router.get("/users/{user_id}/memories", response_model=List[MemoryOut])
async def list_user_memories(user_id: uuid.UUID, limit: int = 50):
    memories = await memory_svc.list_memories(user_id, limit=limit)
    return [
        MemoryOut(
            id=m["id"],
            type=m.get("type", "semantic"),
            content=m.get("content", ""),
        )
        for m in memories
    ]


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    try:
        await memory_svc.delete_memory(memory_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}

@router.get("/test")
async def test_endpoint():
    return {"message": "Hello from the dashboard API!"}