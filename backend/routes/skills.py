"""Routes: /skills — reusable prompts / agent workflows."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from db import get_db
from deps import require_api_key
from models import Skill, SkillIn

router = APIRouter(prefix="/skills", tags=["copilot"],
                   dependencies=[Depends(require_api_key)])


def _now():
    return datetime.now(timezone.utc).isoformat()


@router.get("", response_model=List[Skill],
            summary="List available skills.")
async def list_skills():
    docs = await get_db().copilot_skills.find({}, {"_id": 0}) \
        .sort("name", 1).to_list(100)
    return docs


@router.post("", response_model=Skill, status_code=201,
             summary="Create a skill.")
async def create_skill(payload: SkillIn):
    s = Skill(**payload.model_dump())
    await get_db().copilot_skills.insert_one(s.model_dump())
    return s


@router.put("/{skill_id}", response_model=Skill,
            summary="Update a skill.")
async def update_skill(skill_id: str, payload: SkillIn):
    upd = payload.model_dump()
    upd["updated_at"] = _now()
    doc = await get_db().copilot_skills.find_one_and_update(
        {"id": skill_id}, {"$set": upd}, return_document=True, projection={"_id": 0})
    if not doc:
        raise HTTPException(404, "Skill not found")
    return doc


@router.delete("/{skill_id}", summary="Delete a skill.")
async def delete_skill(skill_id: str):
    r = await get_db().copilot_skills.delete_one({"id": skill_id, "is_seed": {"$ne": True}})
    if r.deleted_count == 0:
        raise HTTPException(404, "Skill not found or is seed (protected)")
    return {"ok": True}
