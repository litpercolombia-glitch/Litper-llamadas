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


# ---------- CEO Reports (populated by the daily cron) ----------
@router.get("/ceo-report",
            summary="Latest daily CEO report snapshot (or the one for a specific date).")
async def ceo_report(date: Optional[str] = None):
    db = get_db()
    q = {"id": date} if date else {}
    cursor = db.ceo_reports.find(q, {"_id": 0}).sort("date", -1).limit(1)
    docs = await cursor.to_list(1)
    if not docs:
        return {"available": False, "note": "Aún no hay reporte CEO. El cron corre 08:00 America/Bogotá."}
    return {"available": True, "report": docs[0]}


@router.post("/ceo-report/run-now",
             summary="Manually generate the CEO snapshot for today (debug/preview).")
async def ceo_report_now():
    from scheduler import daily_ceo_report
    await daily_ceo_report()
    return {"ok": True}


@router.get("/novedades-ticks",
            summary="Recent semaphore snapshots from the 15-min sweep.")
async def novedades_ticks(limit: int = 20):
    docs = await get_db().novedades_ticks.find({}, {"_id": 0}).sort("ts", -1).limit(limit).to_list(limit)
    return docs


# ---------- CEO Report → WhatsApp (Chatea Pro) ----------
_CEO_WA_KEY = "ceo_report_wa_target"


async def _get_ceo_wa_target() -> str:
    """DB setting overrides the env fallback. Returns "" if nothing is configured."""
    import os as _os
    doc = await get_db().settings.find_one({"key": _CEO_WA_KEY}, {"_id": 0, "value": 1})
    if doc and doc.get("value"):
        return str(doc["value"]).strip()
    return (_os.environ.get("CEO_REPORT_WA_TARGET") or "").strip()


def _fmt_cop(v) -> str:
    try: return "$" + f"{int(round(float(v))):,}".replace(",", ".")
    except Exception: return "$0"


def _format_ceo_message(report: dict) -> str:
    n = report.get("norte") or {}
    rr  = (n.get("recovery_rate") or {}).get("value", 0)
    rto = (n.get("rto_reduction") or {}).get("value", 0)
    cpr = (n.get("cpr_cop") or {}).get("value", 0)
    roi = n.get("roi_cop") or {}
    recovered = roi.get("recovered_value_cop", 0)
    margin    = roi.get("margin_recovered_cop", 0)
    cost      = roi.get("total_cost_cop", 0)
    net       = roi.get("value", 0)
    return (
        f"📊 *Reporte CEO — {report.get('date','hoy')}*\n"
        f"\n"
        f"• Recuperación: *{rr}%*  ·  RTO evitado: *{rto}%*\n"
        f"• Recuperado: *{_fmt_cop(recovered)}*  (margen {_fmt_cop(margin)})\n"
        f"• Costo del día: {_fmt_cop(cost)}  ·  CPR: {_fmt_cop(cpr)}\n"
        f"• *ROI neto: {_fmt_cop(net)}*\n"
        f"\n"
        f"Pedidos totales: {report.get('orders_total',0)}  ·  En cola: {report.get('queue_total',0)}\n"
        f"— Zynex OS · autogenerado"
    )


class CeoTargetIn(BaseModel):
    target: str  # phone (E.164) OR chatea subscriber id


@router.get("/ceo-report/target",
            summary="Get the WhatsApp destination for the daily CEO report.")
async def ceo_target_get():
    return {"target": await _get_ceo_wa_target()}


@router.put("/ceo-report/target",
            summary="Set the WhatsApp destination (phone in E.164). Overrides the env default.")
async def ceo_target_set(payload: CeoTargetIn):
    val = (payload.target or "").strip()
    await get_db().settings.update_one(
        {"key": _CEO_WA_KEY},
        {"$set": {"key": _CEO_WA_KEY, "value": val, "updated_at": _iso()}},
        upsert=True,
    )
    return {"ok": True, "target": val}


@router.post("/ceo-report/send-wa",
             summary="Send today's CEO report to WhatsApp NOW (uses configured target).")
async def ceo_report_send_wa():
    db = get_db()
    target = await _get_ceo_wa_target()
    if not target:
        raise HTTPException(400, "No hay destinatario configurado. Usa PUT /agents/ceo-report/target.")
    docs = await db.ceo_reports.find({}, {"_id": 0}).sort("date", -1).limit(1).to_list(1)
    if not docs:
        # Generate on the fly if there's nothing yet
        from scheduler import daily_ceo_report
        await daily_ceo_report()
        docs = await db.ceo_reports.find({}, {"_id": 0}).sort("date", -1).limit(1).to_list(1)
    if not docs:
        raise HTTPException(500, "No se pudo generar el reporte.")
    from chatea import get_client as _get_chatea
    chatea = _get_chatea()
    if not chatea.configured:
        raise HTTPException(400, "Chatea Pro no está configurado en el servidor.")
    text = _format_ceo_message(docs[0])
    res = await chatea.send_message(target, text, name="CEO Report")
    await db.message_log.insert_one({
        "id": _iso() + "-ceo",
        "direction": "outbound",
        "channel": "whatsapp",
        "phone": target,
        "body": text[:300],
        "template_name": None,
        "provider": "chatea_pro",
        "provider_message_id": res.get("provider_message_id"),
        "status": "sent" if res.get("ok") else "failed",
        "error": res.get("error"),
        "created_at": _iso(),
        "kind": "ceo_report",
    })
    return {"ok": bool(res.get("ok")), "target": target,
            "provider_message_id": res.get("provider_message_id"),
            "error": res.get("error")}


# ---------- Cascade (run 5-agent chain across a segment) ----------
class CascadeIn(BaseModel):
    segment: str = "red_this_week"  # red_this_week | new_today | office_all | custom
    limit: int = 25                  # cap to keep response snappy
    require_confirm_for_money: bool = True


async def _pick_segment(db, segment: str, limit: int) -> list[dict]:
    """Return a list of {order_id, phone, city, product} dicts for the segment."""
    q: dict = {}
    if segment == "red_this_week":
        # rojo semaphore in queue → days_left <= 3
        rows = await db.call_queue.find(
            {"status": {"$in": ["pending", "in_progress"]}},
            {"_id": 0, "order_id": 1, "days_left": 1}).to_list(500)
        picked = [r["order_id"] for r in rows if (r.get("days_left") is not None
                                                   and r["days_left"] <= 3)][:limit]
        q = {"id": {"$in": picked}}
    elif segment == "new_today":
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        q = {"created_at": {"$gte": cutoff}}
    elif segment == "office_all":
        q = {"status": {"$in": ["office_arrived", "pending", "in_progress"]}}
    else:
        q = {}
    orders = await db.orders.find(q, {"_id": 0}).limit(limit).to_list(limit)
    return orders


@router.post("/cascade",
             summary="Run the 5-agent chain across a segment (up to `limit` orders).")
async def cascade(payload: CascadeIn):
    db = get_db()
    orders = await _pick_segment(db, payload.segment, payload.limit)
    if not orders:
        return {"segment": payload.segment, "processed": 0, "results": [],
                "hitl_required": [], "summary": {"total_orders": 0},
                "note": "Sin pedidos en ese segmento."}

    results: list[dict] = []
    hitl_required: list[dict] = []
    high_risk_ct = 0
    rescate_ct = 0
    for o in orders:
        phone = o.get("customer_phone") or ""
        city  = o.get("city") or ""
        product = (o.get("products_display")
                   or (o.get("items") or [{}])[0].get("product", "")
                   or "")
        risk    = await _run_riesgo(db, phone, city, product)
        conf    = await _run_confirmacion(risk)
        nov     = await _run_novedades(db, o.get("id"))
        rescate = await _run_rescate(nov.get("days_left"))
        needs_conf = payload.require_confirm_for_money and (
            risk["prepay_required"] or rescate.get("action") == "cadence_planned"
        )
        if risk["level"] == "alto":
            high_risk_ct += 1
        if rescate.get("action") == "cadence_planned":
            rescate_ct += 1
        item = {
            "order_id": o.get("id"),
            "tracking": o.get("tracking_number"),
            "customer": o.get("customer_name"),
            "phone": phone, "city": city,
            "chain": {"riesgo_rto": risk, "confirmacion_cod": conf,
                      "novedades": nov, "rescate_oficina": rescate},
            "requires_human_confirmation": needs_conf,
        }
        if needs_conf:
            hitl_required.append({
                "order_id": o.get("id"),
                "customer": o.get("customer_name"),
                "reason": ("Riesgo alto — exigir prepago." if risk["prepay_required"]
                            else "Rescate con costo (llamada + WhatsApp)."),
            })
        results.append(item)

    kpis = await _run_analitica(db)
    summary = {
        "processed":    len(results),
        "high_risk":    high_risk_ct,
        "rescate_planned": rescate_ct,
        "hitl_pending": len(hitl_required),
        "kpis":         kpis,
    }
    return {
        "segment": payload.segment,
        "processed": len(results),
        "results": results,
        "hitl_required": hitl_required,
        "summary": summary,
        "at": _iso(),
    }
