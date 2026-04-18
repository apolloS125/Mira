"""Public chat endpoint — any client can POST a message.

POST /v1/chat
  body: { channel, external_user_id, message, display_name?, language_code? }
  returns: { user_id, reply }
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.auth import require_api_key
from app.services.chat import chat as core_chat

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    channel: str = Field(..., description="Channel id: 'web', 'cli', 'discord', ...")
    external_user_id: str = Field(..., description="Stable per-channel user id")
    message: str
    display_name: Optional[str] = None
    language_code: str = "th"


class ChatResponse(BaseModel):
    user_id: str
    reply: str


@router.post("", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def post_chat(body: ChatRequest) -> ChatResponse:
    result = await core_chat(
        channel=body.channel,
        external_user_id=body.external_user_id,
        message=body.message,
        display_name=body.display_name,
        language_code=body.language_code,
    )
    return ChatResponse(user_id=str(result.user_id), reply=result.reply)
