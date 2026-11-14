"""Routes: /vip-leads — captura pública de interesados + CRUD admin + export xlsx.

El formulario público (`POST /vip-leads`) NO pide llave ni sesión, así que:
  · está APAGADO por defecto: responde 404 salvo VIP_LEADS_PUBLIC=1;
  · tiene un límite de frecuencia por IP (5 por hora, en memoria);
  · SOLO guarda el lead. No envía WhatsApp automático: el número lo escribió
    un desconocido y no está verificado; escribirle es decisión de una persona
    del equipo desde la lista de interesados.
"""
from __future__ import annotations
import io
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from db import get_db
from deps import get_org, require_api_key
from models import VipLead, VipLeadIn
import ratelimit

# NOTE: two routers — public capture + admin CRUD. Both mounted under /api.
public_router = APIRouter(prefix="/vip-leads", tags=["funnel-public"])
admin_router  = APIRouter(prefix="/vip-leads", tags=["funnel-admin"],
                          dependencies=[Depends(require_api_key)])

# Límite del formulario público. EN MEMORIA (ratelimit.py): con varias réplicas
# debe ir a Mongo/Redis.
PUBLIC_MAX_PER_HOUR = 5
PUBLIC_WINDOW_S = 3600


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_enabled() -> bool:
    return os.environ.get("VIP_LEADS_PUBLIC", "").strip().lower() in ("1", "true", "yes")


def _require_public() -> None:
    if not public_enabled():
        raise HTTPException(404, "Not Found")


def _leads_org() -> str:
    """El formulario público no trae sesión: los leads se asignan al cliente
    dueño del embudo (VIP_LEADS_ORG; por defecto "default"). Nunca se mezclan
    con los de otro cliente: el admin solo ve los de su org."""
    return os.environ.get("VIP_LEADS_ORG", "").strip() or "default"


@public_router.post("", response_model=VipLead,
                    summary="Guarda un interesado del formulario público "
                            "(404 salvo VIP_LEADS_PUBLIC=1; máx. 5 por hora por IP; no envía mensajes).")
async def capture(payload: VipLeadIn, request: Request):
    _require_public()
    key = "vip:" + ratelimit.client_ip(request)
    if ratelimit.count(key, PUBLIC_WINDOW_S) >= PUBLIC_MAX_PER_HOUR:
        raise HTTPException(429, "Demasiados envíos desde esta conexión. Inténtalo más tarde.",
                            headers={"Retry-After": str(PUBLIC_WINDOW_S)})
    ratelimit.hit(key, PUBLIC_WINDOW_S)
    doc = VipLead(**payload.model_dump())
    # Solo se guarda. welcome_sent queda en False: nadie le ha escrito.
    await get_db().vip_leads.insert_one({**doc.model_dump(), "org_id": _leads_org()})
    return doc


@public_router.get("/config",
                   summary="Lectura pública: enlace del grupo, si está definido (404 si el formulario está apagado).")
async def public_config():
    _require_public()
    return {
        "vip_group_url": os.environ.get("VIP_GROUP_URL", ""),
        # Ya no hay bienvenida automática por WhatsApp (se conserva la clave por compatibilidad).
        "chatea_configured": False,
        "welcome_auto": False,
    }


@admin_router.get("", response_model=list[VipLead],
                  summary="List captured VIP leads (admin).")
async def list_leads(limit: int = 500, org: str = Depends(get_org)):
    return await get_db().vip_leads.find({"org_id": org}, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)


@admin_router.patch("/{lead_id}", response_model=VipLead,
                    summary="Update a lead status (admin).")
async def update_lead(lead_id: str, patch: dict, org: str = Depends(get_org)):
    db = get_db()
    allowed = {k: v for k, v in patch.items() if k in ("status", "welcome_sent")}
    if not allowed:
        raise HTTPException(400, "Nada que actualizar.")
    await db.vip_leads.update_one({"id": lead_id, "org_id": org}, {"$set": allowed})
    doc = await db.vip_leads.find_one({"id": lead_id, "org_id": org}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Lead not found")
    return doc


@admin_router.delete("/{lead_id}")
async def delete_lead(lead_id: str, org: str = Depends(get_org)):
    r = await get_db().vip_leads.delete_one({"id": lead_id, "org_id": org})
    if r.deleted_count == 0:
        raise HTTPException(404, "Lead not found")
    return {"ok": True}


@admin_router.get("/export.xlsx",
                  summary="Export all leads as XLSX (admin).")
async def export_leads(org: str = Depends(get_org)):
    import pandas as pd
    docs = await get_db().vip_leads.find({"org_id": org}, {"_id": 0}) \
        .sort("created_at", -1).to_list(5000)
    if not docs:
        docs = [{"nombre": "", "whatsapp": "", "pais": "", "pedidos_semana": "",
                 "email": "", "status": "", "created_at": ""}]
    df = pd.DataFrame(docs)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="VIP Leads")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="vip_leads.xlsx"'},
    )
