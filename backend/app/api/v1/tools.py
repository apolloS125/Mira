"""Introspection for tools — lets clients discover what Mira can do."""
from fastapi import APIRouter, Depends

from app.api.auth import require_api_key
from app.tools import registry as tool_registry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", dependencies=[Depends(require_api_key)])
async def list_tools():
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "source": t.source,
            }
            for t in tool_registry.list_tools()
        ]
    }
