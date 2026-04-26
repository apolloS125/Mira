import uuid
from typing import List, Optional
from pydantic import BaseModel

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