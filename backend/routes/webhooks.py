"""Robust webhook receivers — Chatea Pro · Twilio · ElevenLabs.

All events are logged into `webhook_events` for debugging (raw payload + parse
status). Where the provider supports signature verification, we validate it
using an env-configured secret (kept in backend/.env only).

URL layout (each ready to paste into the provider's dashboard):
  POST /api/webhooks/chatea
  POST /api/webhooks/twilio
  POST /api/webhooks/elevenlabs
"""
from __future__ import annotations
import hmac
import hashlib
import json
import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Header, Request
from typing import Any

from db import get_db

log = logging.getLogger("webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _log_event(provider: str, event_type: str, raw: Any,
                    processed: bool, notes: str = "") -> None:
    await get_db().webhook_events.insert_one({
        "id": str(uuid.uuid4()),
        "provider": provider,
        "type": event_type,
        "raw": raw if isinstance(raw, (dict, list)) else str(raw)[:5000],
        "processed": processed,
        "notes": notes,
        "created_at": _now(),
    })


def _verify_hmac(secret_env: str, body_bytes: bytes, provided: str | None) -> bool:
    secret = os.environ.get(secret_env, "").strip()
    if not secret:
        return True  # verification disabled
    if not provided:
        return False
    mac = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, provided.replace("sha256=", ""))


# =========================================================================
# CHATEA PRO
# =========================================================================
@router.post("/chatea",
             summary="Chatea Pro events: delivered/read/failed + inbound replies + opt-out.")
async def chatea_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    body_bytes = await request.body()
    if not _verify_hmac("CHATEA_WEBHOOK_SECRET", body_bytes, x_signature):
        await _log_event("chatea_pro", "signature_invalid", body_bytes.decode(errors="ignore"),
                        False, "bad signature")
        return {"ok": False, "error": "invalid signature"}
    try:
        body = json.loads(body_bytes or b"{}")
    except Exception:
        body = {}

    db = get_db()
    event_type = (body.get("event") or body.get("type") or "").lower()
    phone = str(body.get("phone") or body.get("from") or body.get("wa_id")
                or (body.get("contact") or {}).get("phone", "") or "").strip()
    msg = body.get("message") or {}
    if isinstance(msg, list) and msg:
        msg = msg[0]
    text = (msg.get("text", {}) or {}).get("body") if isinstance(msg, dict) else ""
    text = text or body.get("text") or body.get("body") or ""
    pmid = body.get("id") or (msg.get("id") if isinstance(msg, dict) else None)

    processed_notes = []

    # --- Delivery / read receipts ---
    if event_type in ("delivered", "read", "failed", "sent"):
        upd = {"status": "delivered" if event_type in ("delivered", "read")
               else "failed" if event_type == "failed" else "sent"}
        if pmid:
            r = await db.message_log.update_one({"provider_message_id": pmid}, {"$set": upd})
            processed_notes.append(f"status={upd['status']} matched={r.modified_count}")

    # --- Inbound customer reply ---
    if event_type in ("message", "message_received", "inbound") or (text and not event_type):
        if phone and text:
            await db.message_log.insert_one({
                "id": str(uuid.uuid4()),
                "direction": "inbound", "channel": "whatsapp",
                "phone": phone, "body": text,
                "provider": "chatea_pro", "provider_message_id": pmid,
                "status": "received", "created_at": _now(),
            })
            processed_notes.append("inbound_logged")

            # Update the WhatsApp 24h window for this contact — every inbound
            # message reopens the free-form window (Meta rule).
            await db.whatsapp_contacts.update_one(
                {"phone": phone},
                {"$set": {"phone": phone, "last_inbound_at": _now(),
                          "last_inbound_body": text[:400]}},
                upsert=True)
            processed_notes.append("wa_window_opened")

            # Auto-classify
            low = text.lower()
            action = None
            if any(k in low for k in ("recogí", "recogi", "ya recog", "listo", "pasé")):
                action = "ya_recogio"
            elif any(k in low for k in ("confirmo", "sí voy", "si voy", "confirmar", "confirmado")):
                action = "confirmado"
            elif any(k in low for k in ("no quiero", "cancelar", "rechazo", "no me interesa")):
                action = "rechazado"
            # Opt-out
            if low.strip() in ("no", "stop", "baja", "salir") or "opt-out" in low:
                await db.orders.update_many({"customer_phone": phone},
                                            {"$set": {"opt_out": True}})
                # Cancel scheduled attempts for this phone's queue items
                orders = await db.orders.find({"customer_phone": phone},
                                              {"_id": 0, "id": 1}).to_list(50)
                order_ids = [o["id"] for o in orders]
                queues = await db.call_queue.find({"order_id": {"$in": order_ids}},
                                                   {"_id": 0, "id": 1}).to_list(50)
                for q in queues:
                    sched = await db.call_schedules.find_one({"queue_id": q["id"]},
                                                             {"_id": 0})
                    if not sched:
                        continue
                    for a in sched["attempts"]:
                        if a["status"] == "pending":
                            a["status"] = "skipped"
                    await db.call_schedules.update_one({"queue_id": q["id"]},
                                                      {"$set": {"attempts": sched["attempts"]}})
                    await db.call_queue.update_one({"id": q["id"]},
                                                  {"$set": {"status": "detenido",
                                                            "opt_out": True,
                                                            "updated_at": _now()}})
                processed_notes.append("opt_out_applied")

            if action:
                orders = await db.orders.find({"customer_phone": phone},
                                              {"_id": 0, "id": 1},
                                              sort=[("created_at", -1)]).to_list(5)
                if orders:
                    q = await db.call_queue.find_one({"order_id": orders[0]["id"]},
                                                     {"_id": 0, "id": 1},
                                                     sort=[("created_at", -1)])
                    if q:
                        await _stop_cadence(q["id"], action)
                        processed_notes.append(f"queue {q['id']} → {action}")

    await _log_event("chatea_pro", event_type or "unknown", body, True, "; ".join(processed_notes))
    return {"ok": True, "processed": processed_notes}


# =========================================================================
# TWILIO — call status + recordings
# =========================================================================
@router.post("/twilio",
             summary="Twilio call status callbacks + recording callbacks.")
async def twilio_webhook(request: Request,
                        x_twilio_signature: str | None = Header(default=None,
                                                                alias="X-Twilio-Signature")):
    form = dict((await request.form()).items())
    body_bytes = json.dumps(form, sort_keys=True).encode()
    if not _verify_hmac("TWILIO_WEBHOOK_SECRET", body_bytes, x_twilio_signature):
        await _log_event("twilio", "signature_invalid", form, False, "bad signature")
        return {"ok": False, "error": "invalid signature"}

    db = get_db()
    call_sid = form.get("CallSid")
    status = (form.get("CallStatus") or "").lower()  # initiated,ringing,answered,completed,no-answer,busy,failed
    recording_url = form.get("RecordingUrl")
    duration = form.get("CallDuration")
    to_number = form.get("To") or form.get("Called")
    queue_id = form.get("QueueId")  # optional: our own passthrough via `StatusCallbackParameter`
    attempt_number = form.get("AttemptNumber")

    processed_notes = []
    # Verification callback (verified caller ID)
    verification_status = form.get("VerificationStatus")
    if verification_status:
        num_status = "verified" if verification_status == "success" else "failed"
        await db.connected_numbers.update_one(
            {"phone_number": to_number},
            {"$set": {"status": num_status, "twilio_sid": form.get("OutgoingCallerIdSid"),
                      "updated_at": _now()}})
        processed_notes.append(f"caller_id={num_status}")

    # Update call attempt if we can match it
    if queue_id and attempt_number:
        try:
            an = int(attempt_number)
            sched = await db.call_schedules.find_one({"queue_id": queue_id}, {"_id": 0})
            if sched:
                for a in sched["attempts"]:
                    if a["attempt_number"] == an:
                        a["call_sid"] = call_sid
                        a["duration_seconds"] = int(duration) if duration else None
                        if recording_url:
                            a["recording_url"] = recording_url
                        if status in ("no-answer", "busy", "failed"):
                            a["result"] = "no_contesta"
                            a["status"] = "done"
                            a["executed_at"] = _now()
                        elif status == "completed":
                            a.setdefault("status", "done")
                            a.setdefault("executed_at", _now())
                        break
                await db.call_schedules.update_one({"queue_id": queue_id},
                                                   {"$set": {"attempts": sched["attempts"]}})
                processed_notes.append(f"attempt#{an}={status}")
        except Exception as e:  # noqa: BLE001
            processed_notes.append(f"error: {e}")

    await _log_event("twilio", f"call_{status or 'unknown'}", form, True, "; ".join(processed_notes))
    return {"ok": True, "processed": processed_notes}


# =========================================================================
# ELEVENLABS — post-call transcript + result
# =========================================================================
@router.post("/elevenlabs",
             summary="ElevenLabs Conversational AI post-call payload.")
async def elevenlabs_webhook(request: Request,
                            x_elevenlabs_signature: str | None = Header(
                                default=None, alias="X-Elevenlabs-Signature")):
    body_bytes = await request.body()
    if not _verify_hmac("ELEVENLABS_WEBHOOK_SECRET", body_bytes, x_elevenlabs_signature):
        await _log_event("elevenlabs", "signature_invalid",
                        body_bytes.decode(errors="ignore"), False, "bad signature")
        return {"ok": False, "error": "invalid signature"}
    try:
        body = json.loads(body_bytes or b"{}")
    except Exception:
        body = {}

    queue_id = body.get("queue_id") or (body.get("metadata") or {}).get("queue_id")
    attempt_number = body.get("attempt_number") or (body.get("metadata") or {}).get("attempt_number")
    transcript = body.get("transcript") or ""
    summary = body.get("summary") or ""
    recording_url = body.get("recording_url") or body.get("audio_url")
    detected = (body.get("detected_result") or body.get("outcome") or "").lower()

    # Normalise outcome
    result_map = {
        "confirmed": "confirmado", "confirmado": "confirmado",
        "extension": "extension", "postpone": "extension",
        "refused": "rechaza", "rechaza": "rechaza", "rejected": "rechaza",
        "picked_up": "ya_recogio", "ya_recogio": "ya_recogio",
        "no_answer": "no_contesta", "no_contesta": "no_contesta",
        "wrong_number": "numero_incorrecto", "numero_incorrecto": "numero_incorrecto",
    }
    result = result_map.get(detected)

    processed_notes = []
    if queue_id and attempt_number and result:
        # Attach recording + transcript to the attempt
        db = get_db()
        sched = await db.call_schedules.find_one({"queue_id": queue_id}, {"_id": 0})
        if sched:
            for a in sched["attempts"]:
                if a["attempt_number"] == int(attempt_number):
                    a["recording_url"] = recording_url
                    a["transcript"] = transcript[:5000]
                    a["summary"] = summary[:1000]
                    break
            await db.call_schedules.update_one({"queue_id": queue_id},
                                               {"$set": {"attempts": sched["attempts"]}})
        # Delegate to the same handler used by /api/calls/attempt-result
        from routes.cadence import attempt_result
        from models import AttemptResult as AR
        try:
            r = await attempt_result(AR(queue_id=queue_id, attempt_number=int(attempt_number),
                                        result=result, notes=summary[:2000] or transcript[:2000]))
            processed_notes.append(f"advanced: {r}")
        except Exception as e:  # noqa: BLE001
            processed_notes.append(f"advance error: {e}")

    await _log_event("elevenlabs", f"call_ended:{detected or 'unknown'}",
                    body, bool(result), "; ".join(processed_notes))
    return {"ok": True, "result": result, "processed": processed_notes}


# =========================================================================
# helper — stop cadence and set ops status (used by Chatea auto-classify)
# =========================================================================
async def _stop_cadence(queue_id: str, action: str) -> None:
    db = get_db()
    await db.call_queue.update_one({"id": queue_id},
                                   {"$set": {"status": action, "updated_at": _now()}})
    sched = await db.call_schedules.find_one({"queue_id": queue_id}, {"_id": 0})
    if sched:
        for a in sched["attempts"]:
            if a["status"] == "pending":
                a["status"] = "skipped"
        await db.call_schedules.update_one({"queue_id": queue_id},
                                          {"$set": {"attempts": sched["attempts"]}})


# =========================================================================
# INSPECTION — recent events (dev/debug)
# =========================================================================
@router.get("/events", summary="Recent webhook events (debug).")
async def list_events(provider: str | None = None, limit: int = 50):
    q = {"provider": provider} if provider else {}
    docs = await get_db().webhook_events.find(q, {"_id": 0}).sort("created_at", -1) \
        .limit(min(limit, 200)).to_list(200)
    return docs
