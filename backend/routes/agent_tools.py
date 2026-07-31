"""The 7 tools Retell calls back into during a live conversation.

BETA policy:
  · Non-money tools just log the action and return `{ok:true}` — the real
    wiring to Dropi / Chatea Pro / etc. will land later.
  · Money tools (`registrar_promesa_pago`, `enviar_link_pago`) require
    explicit `human_confirmed: true` in the body OR they respond
    `{ok:false, requires_human_confirmation:true}` — the UI/HITL layer
    turns that into a Sí/No prompt.

Date/time NEVER happens on the LLM side — see `consultar_disponibilidad`
and `proximo_horario_disponible` which return already-formatted ISO
strings in `America/Bogota` (UTC-5).
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from db import get_db

router = APIRouter(prefix="/agent-tools", tags=["agent-tools"])

# Colombia doesn't observe DST — fixed offset is safe.
BOGOTA = timezone(timedelta(hours=-5))


def _iso() -> str: return datetime.now(timezone.utc).isoformat()


async def _log(action: str, payload: dict, request: Request) -> str:
    """Every tool call gets persisted to `agent_tool_calls` for audit."""
    from uuid import uuid4
    rec = {
        "id":         uuid4().hex[:12],
        "action":     action,
        "payload":    payload,
        "org_id":     request.headers.get("X-Org-Id"),
        "created_at": _iso(),
    }
    await get_db().agent_tool_calls.insert_one(rec)
    return rec["id"]


# --------- Date helpers (backend-only, LLM never computes dates) ---------
def _bogota_now() -> datetime: return datetime.now(BOGOTA)


def _next_business_hour(base: datetime, hour_start: int = 8, hour_end: int = 18) -> datetime:
    """Round `base` up to the next slot within business hours (Mon-Sat)."""
    d = base.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while True:
        if d.weekday() == 6:                           # Sunday → Monday
            d = d.replace(hour=hour_start) + timedelta(days=1); continue
        if d.hour < hour_start: d = d.replace(hour=hour_start); continue
        if d.hour >= hour_end:                         # roll to next day
            d = d.replace(hour=hour_start) + timedelta(days=1); continue
        return d


class DispIn(BaseModel):
    duracion_min: int = 30
    n:            int = 3   # number of slots to propose


@router.post("/consultar_disponibilidad",
             summary="Devuelve N horarios disponibles (America/Bogota) — el LLM SOLO lee.")
async def consultar_disponibilidad(payload: DispIn, request: Request):
    now = _bogota_now()
    slots = []
    cursor = _next_business_hour(now)
    for _ in range(max(1, min(payload.n, 10))):
        slots.append({
            "iso":     cursor.isoformat(),                    # e.g. 2026-08-03T10:00:00-05:00
            "humano":  cursor.strftime("%A %d/%m %H:%M"),
            "zona":    "America/Bogota",
        })
        cursor = _next_business_hour(cursor + timedelta(minutes=payload.duracion_min))
    await _log("consultar_disponibilidad", payload.model_dump(), request)
    return {"ok": True, "slots": slots}


@router.post("/proximo_horario_disponible",
             summary="Devuelve UN solo horario disponible (para reagendar rápido).")
async def proximo_horario_disponible(request: Request):
    slot = _next_business_hour(_bogota_now())
    await _log("proximo_horario_disponible", {}, request)
    return {"ok": True, "slot": {
        "iso":    slot.isoformat(),
        "humano": slot.strftime("%A %d/%m %H:%M"),
        "zona":   "America/Bogota",
    }}


# --------- Non-money actions (BETA-safe: log + ok) ---------
class ReagendarIn(BaseModel):
    pedido_id:      str
    nueva_fecha_iso: str
    telefono:       Optional[str] = None


@router.post("/reagendar_entrega")
async def reagendar_entrega(p: ReagendarIn, request: Request):
    tid = await _log("reagendar_entrega", p.model_dump(), request)
    return {"ok": True, "tool_call_id": tid,
            "detail": f"Reprogramada {p.pedido_id} para {p.nueva_fecha_iso} (BETA)."}


class ConfirmarPedidoIn(BaseModel):
    pedido_id: str
    direccion: Optional[str] = None
    franja:    Optional[str] = None


@router.post("/confirmar_pedido")
async def confirmar_pedido(p: ConfirmarPedidoIn, request: Request):
    tid = await _log("confirmar_pedido", p.model_dump(), request)
    return {"ok": True, "tool_call_id": tid,
            "detail": f"Pedido {p.pedido_id} confirmado (BETA)."}


class WhatsAppIn(BaseModel):
    telefono: str
    plantilla: Optional[str] = None
    mensaje:  Optional[str] = None


@router.post("/enviar_whatsapp")
async def enviar_whatsapp(p: WhatsAppIn, request: Request):
    tid = await _log("enviar_whatsapp", p.model_dump(), request)
    return {"ok": True, "tool_call_id": tid,
            "detail": f"WhatsApp encolado hacia {p.telefono} (BETA)."}


class TransferIn(BaseModel):
    telefono: str
    razon:    Optional[str] = None


@router.post("/transferir_a_humano")
async def transferir_a_humano(p: TransferIn, request: Request):
    tid = await _log("transferir_a_humano", p.model_dump(), request)
    return {"ok": True, "tool_call_id": tid,
            "detail": "Transferencia solicitada — un humano tomará la llamada (BETA)."}


# --------- Money actions (require explicit human confirmation) ---------
class PromesaPagoIn(BaseModel):
    pedido_id: str
    fecha_iso: str
    monto:     Optional[float] = None
    human_confirmed: bool = False


@router.post("/registrar_promesa_pago")
async def registrar_promesa_pago(p: PromesaPagoIn, request: Request):
    if not p.human_confirmed:
        return {"ok": False, "requires_human_confirmation": True,
                "detail": "Acción con dinero — el operador humano debe confirmar."}
    tid = await _log("registrar_promesa_pago", p.model_dump(), request)
    return {"ok": True, "tool_call_id": tid,
            "detail": f"Promesa de pago {p.pedido_id} el {p.fecha_iso} guardada."}


class LinkPagoIn(BaseModel):
    telefono:  str
    pedido_id: str
    monto:     float
    link_pago: Optional[str] = None
    human_confirmed: bool = False


@router.post("/enviar_link_pago")
async def enviar_link_pago(p: LinkPagoIn, request: Request):
    if not p.human_confirmed:
        return {"ok": False, "requires_human_confirmation": True,
                "detail": "Envío de link de pago — el operador humano debe confirmar."}
    tid = await _log("enviar_link_pago", p.model_dump(), request)
    return {"ok": True, "tool_call_id": tid,
            "detail": f"Link de pago enviado a {p.telefono} (BETA)."}
