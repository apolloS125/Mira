"""Skills management API."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import require_api_key
from app.skills import registry as skill_registry

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillUpsert(BaseModel):
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{0,63}$")
    description: str
    parameters: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})
    code: str
    author: str = "user"


@router.get("", dependencies=[Depends(require_api_key)])
async def list_skills():
    return {"skills": await skill_registry.list_skills()}


@router.post("", dependencies=[Depends(require_api_key)])
async def upsert_skill(body: SkillUpsert):
    try:
        skill = await skill_registry.upsert_skill(
            name=body.name,
            description=body.description,
            parameters=body.parameters,
            code=body.code,
            author=body.author,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Skill compile failed: {e}")
    return {
        "ok": True,
        "name": skill.name,
        "version": skill.version,
    }


@router.delete("/{name}", dependencies=[Depends(require_api_key)])
async def disable_skill(name: str):
    ok = await skill_registry.disable_skill(name)
    if not ok:
        raise HTTPException(status_code=404, detail="skill not found")
    return {"ok": True}
