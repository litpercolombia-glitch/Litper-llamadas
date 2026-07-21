"""Routes: /webhooks — inbound events from Chatea Pro (WhatsApp) and VAPI (calls).

Note: Webhooks intentionally do NOT require X-API-Key (external providers cannot
easily inject custom headers). Signature verification could be added later.
"""
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Request

from db import get_db
from models import VapiWebhook, ChateaWebhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _now():
    return datetime.now(timezone.utc).isoformat()


@router.post("/chatea", summary="Inbound WhatsApp events (customer replies, delivery receipts).")
async def chatea_webhook(request: Request):
    body = await request.json()
    payload = _parse_chatea(body)

    db = get_db()

    # Log inbound message
    if payload.text or payload.template_name:
        await db.message_log.insert_one({
            "id": str(uuid.uuid4()),
            "direction": "inbound",
            "channel": "whatsapp",
            "phone": payload.phone,
            "template_name": payload.template_name,
            "body": payload.text or "",
            "provider": "chatea_pro",
            "provider_message_id": payload.provider_message_id,
            "status": "received",
            "created_at": _now(),
            "raw": payload.raw,
        })

    # Simple auto-classification: keywords → confirm/stop cadence
    txt = (payload.text or "").lower()
    if not payload.phone or not txt:
        return {"ok": True, "matched_queue": None}

    # Find latest queue item for this phone
    order = await db.orders.find_one({"customer_phone": payload.phone}, {"_id": 0},
                                     sort=[("created_at", -1)])
    if not order:
        return {"ok": True, "matched_queue": None, "note": "phone not found"}

    q = await db.call_queue.find_one({"order_id": order["id"]}, {"_id": 0},
                                     sort=[("created_at", -1)])
    if not q:
        return {"ok": True, "matched_queue": None}

    if any(k in txt for k in ("recogí", "recogi", "ya recog", "listo", "pasé")):
        await _mark_queue(q["id"], "ya_recogio")
        return {"ok": True, "matched_queue": q["id"], "action": "ya_recogio"}
    if any(k in txt for k in ("confirmo", "sí voy", "si voy", "confirmar", "confirmado")):
        await _mark_queue(q["id"], "confirmado")
        return {"ok": True, "matched_queue": q["id"], "action": "confirmado"}
    if any(k in txt for k in ("no quiero", "cancelar", "rechazo", "no me interesa")):
        await _mark_queue(q["id"], "rechazado")
        return {"ok": True, "matched_queue": q["id"], "action": "rechazado"}

    return {"ok": True, "matched_queue": q["id"], "action": None}


async def _mark_queue(queue_id: str, status: str):
    db = get_db()
    await db.call_queue.update_one({"id": queue_id},
                                   {"$set": {"status": status, "updated_at": _now()}})
    # skip remaining attempts
    sched = await db.call_schedules.find_one({"queue_id": queue_id}, {"_id": 0})
    if sched:
        for a in sched["attempts"]:
            if a["status"] == "pending":
                a["status"] = "skipped"
        await db.call_schedules.update_one({"queue_id": queue_id},
                                           {"$set": {"attempts": sched["attempts"]}})


def _parse_chatea(body: dict) -> ChateaWebhook:
    """Flexibly extract phone/text/template from Chatea Pro payloads."""
    phone = (body.get("from") or body.get("phone") or body.get("wa_id")
             or (body.get("contact") or {}).get("phone", ""))
    text = ""
    msg = body.get("message") or body.get("messages") or {}
    if isinstance(msg, list) and msg:
        msg = msg[0]
    if isinstance(msg, dict):
        text = (msg.get("text", {}) or {}).get("body", "") or msg.get("body", "") or msg.get("text", "")
    if not text:
        text = body.get("text", "") or body.get("body", "")
    tpl = body.get("template_name") or (msg.get("template", {}) or {}).get("name") if isinstance(msg, dict) else None
    pmid = body.get("id") or (msg.get("id") if isinstance(msg, dict) else None)
    return ChateaWebhook(phone=str(phone or ""), text=text or "",
                        template_name=tpl, provider_message_id=pmid, raw=body)


@router.post("/vapi", summary="VAPI (or any AI phone) call-ended webhook.")
async def vapi_webhook(payload: VapiWebhook):
    """Register the outcome of a phone call as an attempt result."""
    from routes.cadence import attempt_result  # local import to avoid cycles
    from models import AttemptResult as AR
    return await attempt_result(AR(queue_id=payload.queue_id,
                                   attempt_number=payload.attempt_number,
                                   result=payload.result,
                                   notes=(payload.transcript or "")[:2000]))
