"""Public v1 API — channel-agnostic chat and skills management."""
from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.skills import router as skills_router
from app.api.v1.tools import router as tools_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(chat_router)
v1_router.include_router(skills_router)
v1_router.include_router(tools_router)
