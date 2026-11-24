"""Routes: /org/profile — perfil de negocio por cliente (org).

Colección `org_profiles {org_id, empresa, sector, pais, moneda, zona_horaria,
idioma, nombre_asistente, descripcion}`. El agente (agent/loop.py) arma su
prompt de sistema con este perfil, así sirve para cualquier negocio.
Valores por defecto neutros: no asumen país, sector ni marca.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from db import get_db
from deps import get_org, require_api_key

router = APIRouter(prefix="/org", tags=["org"],
                   dependencies=[Depends(require_api_key)])

DEFAULT_PROFILE = {
    "empresa": "",
    "sector": "",
    "pais": "",
    "moneda": "USD",
    "zona_horaria": "America/Bogota",
    "idioma": "es",
    "nombre_asistente": "Lyan",
    "descripcion": "",
}


class OrgProfileIn(BaseModel):
    empresa:          Optional[str] = Field(None, max_length=120)
    sector:           Optional[str] = Field(None, max_length=120)
    pais:             Optional[str] = Field(None, max_length=8, description="Código ISO (CO, MX, ES…).")
    moneda:           Optional[str] = Field(None, max_length=8, description="Código ISO 4217 (USD, COP…).")
    zona_horaria:     Optional[str] = Field(None, max_length=64, description="Zona IANA, ej. America/Bogota.")
    idioma:           Optional[str] = Field(None, max_length=16)
    nombre_asistente: Optional[str] = Field(None, max_length=60)
    descripcion:      Optional[str] = Field(None, max_length=2000)


async def get_profile(org_id: str) -> dict:
    """Perfil del org con los valores por defecto rellenados (nunca None)."""
    doc = await get_db().org_profiles.find_one({"org_id": org_id}, {"_id": 0}) or {}
    return {**DEFAULT_PROFILE, **{k: v for k, v in doc.items() if v is not None},
            "org_id": org_id}


def tz_of(profile: dict | None) -> ZoneInfo:
    """Zona horaria del perfil; si falta o es inválida, America/Bogota."""
    try:
        return ZoneInfo((profile or {}).get("zona_horaria") or DEFAULT_PROFILE["zona_horaria"])
    except Exception:  # noqa: BLE001
        return ZoneInfo(DEFAULT_PROFILE["zona_horaria"])


@router.get("/profile", summary="Perfil de negocio del cliente actual.")
async def read_profile(org: str = Depends(get_org)):
    return await get_profile(org)


async def save_profile(org: str, payload: OrgProfileIn) -> dict:
    """Guarda (parcial) el perfil del cliente `org`. Lo usan la ruta y la
    herramienta `update_business_profile` del asistente."""
    upd = {k: v.strip() for k, v in payload.model_dump().items() if v is not None}
    if "pais" in upd:
        upd["pais"] = upd["pais"].upper()
    if "moneda" in upd:
        upd["moneda"] = upd["moneda"].upper()
    if upd.get("zona_horaria"):
        try:
            ZoneInfo(upd["zona_horaria"])
        except Exception:  # noqa: BLE001
            raise HTTPException(400, f"Zona horaria inválida: {upd['zona_horaria']}")
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await get_db().org_profiles.update_one(
        {"org_id": org}, {"$set": {**upd, "org_id": org}}, upsert=True)
    return await get_profile(org)


@router.put("/profile", summary="Crea/actualiza el perfil de negocio del cliente actual.")
async def write_profile(payload: OrgProfileIn, org: str = Depends(get_org)):
    return await save_profile(org, payload)


WEBHOOK_NOTAS = {
    "chatea": "Pégala en Chatea Pro como dirección de eventos de WhatsApp.",
    "twilio": "Además se valida la firma X-Twilio-Signature con tu Auth Token.",
    "elevenlabs": "Pégala en ElevenLabs como webhook de fin de conversación.",
    "retell": "Pega esta URL como webhook del agente en Retell.",
}


@router.get("/webhook-urls",
            summary="URLs de webhooks de ESTE cliente (con su token) para pegar en cada proveedor.")
async def webhook_urls(request: Request, org: str = Depends(get_org)):
    """El token identifica al cliente: quien tenga la URL puede enviar eventos
    a su cuenta, así que se muestra solo con sesión. `rotate` lo cambia."""
    import webhook_tokens
    token = await webhook_tokens.token_for(org)
    return {"org_id": org, "token": token,
            "urls": webhook_tokens.urls_for(webhook_tokens.public_base(request), token),
            "notas": WEBHOOK_NOTAS}


@router.post("/webhook-urls/rotate",
             summary="Genera un token nuevo: las URLs anteriores dejan de funcionar.")
async def rotate_webhook_urls(request: Request, org: str = Depends(get_org)):
    import webhook_tokens
    token = await webhook_tokens.rotate(org)
    return {"org_id": org, "token": token, "rotated": True,
            "urls": webhook_tokens.urls_for(webhook_tokens.public_base(request), token),
            "notas": WEBHOOK_NOTAS}
