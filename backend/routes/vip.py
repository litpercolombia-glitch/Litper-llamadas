"""Routes: /vip-leads — funnel capture (public POST) + admin CRUD + xlsx export.

Public endpoint (`POST /vip-leads`) does NOT require an API key so the landing
page can capture leads without exposing the operator key to the browser.
"""
from __future__ import annotations
import io
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from db import get_db
from deps import require_api_key
from models import VipLead, VipLeadIn
from chatea import get_client as get_chatea

# NOTE: two routers — public capture + admin CRUD. Both mounted under /api.
public_router = APIRouter(prefix="/vip-leads", tags=["funnel-public"])
admin_router  = APIRouter(prefix="/vip-leads", tags=["funnel-admin"],
                          dependencies=[Depends(require_api_key)])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@public_router.post("", response_model=VipLead,
                    summary="Capture a VIP lead from the public funnel. "
                            "Optionally send a WhatsApp welcome via Chatea Pro.")
async def capture(payload: VipLeadIn):
    db = get_db()
    doc = VipLead(**payload.model_dump())
    await db.vip_leads.insert_one(doc.model_dump())

    # Fire welcome WA (best-effort)
    group_url = os.environ.get("VIP_GROUP_URL", "").strip()
    chatea = get_chatea()
    if chatea.configured and payload.whatsapp:
        text = (
            f"Hola {payload.nombre.split(' ')[0]}, ¡bienvenido al Grupo VIP de "
            f"Litper Connect! 🎉\n\n"
            f"Acá te vamos a compartir el sistema que recupera pedidos represados "
            f"en oficina y baja las devoluciones. \n\n"
        )
        if group_url:
            text += f"Únete al grupo VIP: {group_url}"
        try:
            res = await chatea.send_message(payload.whatsapp, text)
            await db.vip_leads.update_one(
                {"id": doc.id},
                {"$set": {"welcome_sent": bool(res.get("ok")),
                          "welcome_error": None if res.get("ok") else res.get("error")}})
            doc.welcome_sent = bool(res.get("ok"))
            doc.welcome_error = None if res.get("ok") else res.get("error")
        except Exception as e:  # noqa: BLE001
            await db.vip_leads.update_one(
                {"id": doc.id}, {"$set": {"welcome_error": str(e)}})
            doc.welcome_error = str(e)

    return doc


@public_router.get("/config",
                   summary="Public read: whether WA welcome is configured and the VIP group URL.")
async def public_config():
    return {
        "vip_group_url": os.environ.get("VIP_GROUP_URL", ""),
        "chatea_configured": get_chatea().configured,
    }


@admin_router.get("", response_model=list[VipLead],
                  summary="List captured VIP leads (admin).")
async def list_leads(limit: int = 500):
    return await get_db().vip_leads.find({}, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)


@admin_router.patch("/{lead_id}", response_model=VipLead,
                    summary="Update a lead status (admin).")
async def update_lead(lead_id: str, patch: dict):
    db = get_db()
    allowed = {k: v for k, v in patch.items() if k in ("status", "welcome_sent")}
    if not allowed:
        raise HTTPException(400, "Nada que actualizar.")
    await db.vip_leads.update_one({"id": lead_id}, {"$set": allowed})
    doc = await db.vip_leads.find_one({"id": lead_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Lead not found")
    return doc


@admin_router.delete("/{lead_id}")
async def delete_lead(lead_id: str):
    r = await get_db().vip_leads.delete_one({"id": lead_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Lead not found")
    return {"ok": True}


@admin_router.get("/export.xlsx",
                  summary="Export all leads as XLSX (admin).")
async def export_leads():
    import pandas as pd
    docs = await get_db().vip_leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
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
        headers={"Content-Disposition": 'attachment; filename="litper_vip_leads.xlsx"'},
    )
