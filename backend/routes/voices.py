"""Routes: /voices — CRUD for AI phone-call voice profiles (ElevenLabs)."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from db import get_db
from deps import require_api_key
from models import VoiceProfile, VoiceProfileIn, VoiceProfileUpdate
from elevenlabs_client import get_client as get_eleven

router = APIRouter(prefix="/voices", tags=["voices"],
                   dependencies=[Depends(require_api_key)])

MAX_VOICES = 6


def _now():
    return datetime.now(timezone.utc).isoformat()


@router.get("", response_model=List[VoiceProfile],
            summary="List registered voice profiles (max 6).")
async def list_voices():
    docs = await get_db().voice_profiles.find({}, {"_id": 0}) \
        .sort("created_at", 1).to_list(50)
    return docs


@router.post("", response_model=VoiceProfile, status_code=201,
             summary="Register a new voice profile. Max 6 per org.")
async def create_voice(payload: VoiceProfileIn):
    db = get_db()
    count = await db.voice_profiles.count_documents({})
    if count >= MAX_VOICES:
        raise HTTPException(400, f"Máximo {MAX_VOICES} voces permitidas.")
    voice = VoiceProfile(**payload.model_dump())
    if voice.is_default:
        await db.voice_profiles.update_many(
            {"country": voice.country},
            {"$set": {"is_default": False, "updated_at": _now()}},
        )
    await db.voice_profiles.insert_one(voice.model_dump())
    return voice


@router.put("/{voice_id}", response_model=VoiceProfile,
            summary="Update a voice profile.")
async def update_voice(voice_id: str, payload: VoiceProfileUpdate):
    db = get_db()
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    upd["updated_at"] = _now()
    if upd.get("is_default") is True:
        cur = await db.voice_profiles.find_one({"id": voice_id}, {"_id": 0, "country": 1})
        if cur:
            country = upd.get("country") or cur.get("country")
            await db.voice_profiles.update_many(
                {"country": country, "id": {"$ne": voice_id}},
                {"$set": {"is_default": False, "updated_at": _now()}})
    r = await db.voice_profiles.find_one_and_update(
        {"id": voice_id}, {"$set": upd}, return_document=True, projection={"_id": 0})
    if not r:
        raise HTTPException(404, "Voz no encontrada")
    return r


@router.delete("/{voice_id}",
               summary="Delete a voice profile.")
async def delete_voice(voice_id: str):
    r = await get_db().voice_profiles.delete_one({"id": voice_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Voz no encontrada")
    return {"ok": True, "id": voice_id}


@router.get("/default/{country}",
            summary="Return the default voice for a country (or first available).")
async def default_for_country(country: str):
    db = get_db()
    doc = await db.voice_profiles.find_one({"country": country, "is_default": True},
                                           {"_id": 0})
    if not doc:
        doc = await db.voice_profiles.find_one({"country": country}, {"_id": 0})
    if not doc:
        doc = await db.voice_profiles.find_one({}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "No hay voces registradas")
    return doc


@router.get("/elevenlabs/available",
            summary="List voices available in the connected ElevenLabs account.")
async def elevenlabs_available():
    return await get_eleven().list_voices()
