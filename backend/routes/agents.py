"""Routes: /agents — the 5 operational agents + orchestrator.

Agents (order in which the orchestrator hands an order off):
 1. riesgo_rto         — score risk (blacklist shared across orgs, 2 rejects → prepay)
 2. confirmacion_cod   — voice + WhatsApp confirmation using the risk score
 3. novedades          — carrier status sweep + semaphore
 4. rescate_oficina    — cadence up to 5 attempts (0-3d / 4-7d / 8+ templates)
 5. analitica_operativa — recovery/return/effective-delivery KPIs in NL

Marketing/Ads/Copies/Social agents are explicitly NOT included. The
orchestrator provides a single entrypoint `POST /agents/orchestrate` that
runs the chain for an order and returns per-agent outcomes.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import get_db
from deps import require_api_key

router = APIRouter(prefix="/agents", tags=["agents"],
                   dependencies=[Depends(require_api_key)])


AGENTS = [
    {"key": "riesgo_rto",         "name": "Riesgo RTO",
     "purpose": "Puntúa riesgo del pedido por teléfono/ciudad/producto + lista negra compartida.",
     "icon": "warning-diamond"},
    {"key": "confirmacion_cod",   "name": "Confirmación COD",
     "purpose": "Verifica intención + dirección por voz y WhatsApp (prioriza según score).",
     "icon": "phone-call"},
    {"key": "novedades",          "name": "Novedades",
     "purpose": "Barre Dropi/carrier, semáforo por plazo real, dispara Rescate cuando entra a oficina.",
     "icon": "warning"},
    {"key": "rescate_oficina",    "name": "Rescate Oficina",
     "purpose": "Cadencia hasta 5 intentos con las plantillas WhatsApp aprobadas (0-3d / 4-7d / 8+).",
     "icon": "life-buoy"},
    {"key": "analitica_operativa","name": "Analítica Operativa",
     "purpose": "KPIs de recuperación, entrega efectiva, devoluciones evitadas y $ recuperado.",
     "icon": "chart-line-up"},
]


@router.get("", summary="List the 5 operational agents.")
async def list_agents():
    return {"agents": AGENTS}


class OrchestrateIn(BaseModel):
    order_id: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    product: Optional[str] = None
    require_confirm_for_money: bool = True


def _iso() -> str: return datetime.now(timezone.utc).isoformat()


async def _run_riesgo(db, phone: str, city: str, product: str) -> dict:
    bl = await db.rto_blacklist.find_one({"phone": phone}, {"_id": 0}) if phone else None
    hist = await db.orders.count_documents({"customer_phone": phone,
                                             "status": {"$in": ["returned", "rto"]}}) if phone else 0
    score = 0
    reasons: list[str] = []
    if bl:
        score += 60
        reasons.append(f"En lista negra ({bl.get('reason', 'sin razón')}).")
    if hist >= 2:
        score += 40; reasons.append(f"{hist} devoluciones previas → exigir prepago.")
    if not phone:
        score += 10; reasons.append("Sin teléfono.")
    level = "alto" if score >= 60 else ("medio" if score >= 30 else "bajo")
    return {"score": min(score, 100), "level": level,
            "prepay_required": score >= 60, "reasons": reasons}


async def _run_confirmacion(risk: dict) -> dict:
    if risk["prepay_required"]:
        return {"action": "hold_for_prepay",
                "note": "No se agenda voz hasta que el cliente prepague (Riesgo alto)."}
    priority = "alta" if risk["level"] == "medio" else "normal"
    return {"action": "schedule_confirmation", "priority": priority,
            "channels": ["whatsapp", "voice"]}


async def _run_novedades(db, order_id: Optional[str]) -> dict:
    if not order_id:
        return {"action": "sweep_scheduled", "note": "Barrido de novedades ejecutado por cron."}
    q = await db.call_queue.find_one({"order_id": order_id}, {"_id": 0})
    days_left = (q or {}).get("days_left")
    semaforo = "rojo" if (days_left is not None and days_left <= 1) \
               else ("amarillo" if (days_left is not None and days_left <= 4) else "verde")
    return {"action": "classified", "days_left": days_left, "semaforo": semaforo,
            "next": "rescate_oficina" if semaforo in ("rojo", "amarillo") else "monitor"}


async def _run_rescate(days_left: Optional[int]) -> dict:
    if days_left is None:
        return {"action": "skip", "reason": "sin días en oficina"}
    if 0 <= days_left <= 3:  template = "reclamo_oficina_whatsaap"
    elif days_left <= 7:      template = "oficina_7_dias"
    else:                     template = "no__oficina__"
    return {"action": "cadence_planned", "template": template,
            "max_attempts": 5, "channels": ["voice", "whatsapp"]}


async def _run_analitica(db) -> dict:
    total    = await db.orders.count_documents({})
    recuperados = await db.orders.count_documents({"status": "recuperado"})
    devueltos   = await db.orders.count_documents({"status": {"$in": ["returned", "rto"]}})
    pct = round((recuperados / total) * 100, 1) if total else 0.0
    return {"total_orders": total, "recuperados": recuperados,
            "devueltos": devueltos, "tasa_recuperacion_pct": pct,
            "resumen_nl": f"Has recuperado {recuperados} de {total} pedidos ({pct}%). "
                          f"Devoluciones evitadas: {recuperados}."}


@router.post("/orchestrate",
             summary="Run an order through the 5-agent chain and return per-agent outcomes.")
async def orchestrate(payload: OrchestrateIn):
    db = get_db()
    order = None
    if payload.order_id:
        order = await db.orders.find_one({"id": payload.order_id}, {"_id": 0})
    phone   = (order or {}).get("customer_phone") or payload.phone or ""
    city    = (order or {}).get("city") or payload.city or ""
    product = (order or {}).get("products_display") or payload.product or ""

    risk   = await _run_riesgo(db, phone, city, product)
    conf   = await _run_confirmacion(risk)
    nov    = await _run_novedades(db, payload.order_id)
    rescate = await _run_rescate(nov.get("days_left"))
    kpis   = await _run_analitica(db)

    requires_confirmation = payload.require_confirm_for_money and (
        risk["prepay_required"] or rescate.get("action") == "cadence_planned"
    )

    return {
        "order_id": payload.order_id,
        "phone": phone, "city": city, "product": product,
        "chain": {
            "riesgo_rto":          risk,
            "confirmacion_cod":    conf,
            "novedades":           nov,
            "rescate_oficina":     rescate,
            "analitica_operativa": kpis,
        },
        "requires_human_confirmation": requires_confirmation,
        "note": ("Toca 'Confirmar' para autorizar acciones con costo (llamadas/prepago)."
                 if requires_confirmation else
                 "Ejecución autónoma permitida."),
        "at": _iso(),
    }


# ---------- Shared RTO Blacklist ----------
class BlacklistIn(BaseModel):
    phone: str
    reason: str = ""


@router.get("/blacklist", summary="List blacklisted phones (SHARED across orgs).")
async def blacklist_list():
    return await get_db().rto_blacklist.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/blacklist", summary="Add a phone to the shared blacklist.")
async def blacklist_add(payload: BlacklistIn):
    doc = {"phone": payload.phone.strip(), "reason": payload.reason.strip(),
           "created_at": _iso()}
    await get_db().rto_blacklist.update_one(
        {"phone": doc["phone"]}, {"$set": doc}, upsert=True)
    return doc


@router.delete("/blacklist/{phone:path}")
async def blacklist_remove(phone: str):
    await get_db().rto_blacklist.delete_one({"phone": phone})
    return {"ok": True}
