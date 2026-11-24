"""Webhook receivers — WhatsApp (Chatea Pro) · Twilio · ElevenLabs.

FALLAN CERRADO. Hay dos formas de entrar y ninguna acepta eventos sin verificar:

  1. POR CLIENTE (la normal):  POST /api/webhooks/{provider}/{org_token}
     El cliente (org) sale del token aleatorio de la URL (webhook_tokens.py;
     el cliente copia sus URLs de GET /api/org/webhook-urls). Token desconocido
     → 401. Twilio además valida X-Twilio-Signature con el Auth Token de ESE
     cliente (esquema real: HMAC-SHA1 de URL + parámetros ordenados, base64).

  2. ANTIGUAS (sin token):     POST /api/webhooks/{provider}
     Solo operan sobre la org "default" y EXIGEN firma. Sin secreto configurado
     en el servidor → 503; firma ausente o incorrecta → 401.

AISLAMIENTO: el org nunca se toma del cuerpo ni se deduce de datos de otros
clientes; TODA lectura/escritura de un evento filtra por el org resuelto.
GET /webhooks/events exige autenticación y muestra solo los eventos del org.
"""
from __future__ import annotations
import base64
import hmac
import hashlib
import json
import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from typing import Any

from db import get_db
from deps import get_org, require_api_key
import webhook_tokens

log = logging.getLogger("webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DEFAULT_ORG = "default"


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _log_event(provider: str, event_type: str, raw: Any,
                    processed: bool, notes: str = "", org: str | None = None) -> None:
    await get_db().webhook_events.insert_one({
        "id": str(uuid.uuid4()),
        "org_id": org,
        "provider": provider,
        "type": event_type,
        "raw": raw if isinstance(raw, (dict, list)) else str(raw)[:5000],
        "processed": processed,
        "notes": notes,
        "created_at": _now(),
    })


# ------------------------------------------------------------ verificación
def hmac_valid(secret: str, body_bytes: bytes, provided: str | None) -> bool:
    """HMAC-SHA256 del cuerpo. SIN secreto o SIN firma → False (nunca válido)."""
    secret = (secret or "").strip()
    if not secret or not provided:
        return False
    mac = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, provided.strip().replace("sha256=", ""))


async def _require_hmac(provider: str, secret_env: str, body_bytes: bytes,
                        provided: str | None) -> None:
    """Rutas antiguas: sin secreto en el servidor → 503; firma mala → 401."""
    secret = os.environ.get(secret_env, "").strip()
    if not secret:
        raise HTTPException(503, f"Webhook sin configurar: falta {secret_env} en el servidor. "
                                 "Usa la URL con token de tu cuenta (GET /api/org/webhook-urls).")
    if not hmac_valid(secret, body_bytes, provided):
        await _log_event(provider, "signature_invalid", "(cuerpo omitido)", False, "bad signature")
        raise HTTPException(401, "Firma de webhook inválida.")


def twilio_signature(auth_token: str, url: str, params: dict[str, Any]) -> str:
    """Firma real de Twilio: base64(HMAC-SHA1(auth_token, URL + k1v1k2v2…))
    con los parámetros POST ordenados por nombre."""
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(
        hmac.new(auth_token.encode(), data.encode("utf-8"), hashlib.sha1).digest()).decode()


def twilio_signature_valid(auth_token: str, url: str, params: dict[str, Any],
                           provided: str | None) -> bool:
    if not (auth_token or "").strip() or not provided:
        return False
    return hmac.compare_digest(twilio_signature(auth_token.strip(), url, params), provided.strip())


def _public_url(request: Request) -> str:
    """URL exacta que el proveedor firmó (la pública, no la interna del proxy)."""
    url = webhook_tokens.public_base(request) + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    return url


async def _org_of_token(org_token: str) -> str:
    org = await webhook_tokens.org_for_token(org_token)
    if not org:
        raise HTTPException(401, "Token de webhook inválido.")
    return org


async def _require_twilio(org: str, request: Request, form: dict, provided: str | None) -> None:
    """Valida X-Twilio-Signature con el Auth Token de ESTE cliente."""
    from org_credentials import get_credentials
    try:
        token = ((await get_credentials("twilio", org)).get("auth_token") or "").strip()
    except Exception:  # noqa: BLE001
        token = ""
    if not token:
        raise HTTPException(503, "Twilio no está conectado para esta cuenta: no se puede "
                                 "verificar la firma.")
    if not twilio_signature_valid(token, _public_url(request), form, provided):
        await _log_event("twilio", "signature_invalid", "(cuerpo omitido)", False,
                         "bad signature", org)
        raise HTTPException(401, "Firma de Twilio inválida.")


def _json(body_bytes: bytes) -> dict:
    try:
        body = json.loads(body_bytes or b"{}")
    except Exception:  # noqa: BLE001
        body = {}
    return body if isinstance(body, dict) else {}


# =========================================================================
# CHATEA PRO (WhatsApp)
# =========================================================================
@router.post("/chatea/{org_token}",
             summary="WhatsApp (Chatea Pro) del cliente dueño del token: entregas, respuestas, opt-out.")
async def chatea_webhook_org(org_token: str, request: Request):
    org = await _org_of_token(org_token)
    return await _handle_chatea(org, _json(await request.body()))


@router.post("/chatea",
             summary="(Antigua) Solo org «default» y con firma X-Signature obligatoria.")
async def chatea_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    body_bytes = await request.body()
    await _require_hmac("chatea_pro", "CHATEA_WEBHOOK_SECRET", body_bytes, x_signature)
    return await _handle_chatea(DEFAULT_ORG, _json(body_bytes))


async def _handle_chatea(org: str, body: dict) -> dict:
    """Procesa un evento de WhatsApp tocando SOLO datos de `org`."""
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
            r = await db.message_log.update_one(
                {"provider_message_id": pmid, "org_id": org}, {"$set": upd})
            processed_notes.append(f"status={upd['status']} matched={r.modified_count}")

    # --- Inbound customer reply ---
    if event_type in ("message", "message_received", "inbound") or (text and not event_type):
        if phone and text:
            await db.message_log.insert_one({
                "id": str(uuid.uuid4()), "org_id": org,
                "direction": "inbound", "channel": "whatsapp",
                "phone": phone, "body": text,
                "provider": "chatea_pro", "provider_message_id": pmid,
                "status": "received", "created_at": _now(),
            })
            processed_notes.append("inbound_logged")

            # Update the WhatsApp 24h window for this contact — every inbound
            # message reopens the free-form window (Meta rule).
            await db.whatsapp_contacts.update_one(
                {"org_id": org, "phone": phone},
                {"$set": {"org_id": org, "phone": phone, "last_inbound_at": _now(),
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
                await db.orders.update_many({"org_id": org, "customer_phone": phone},
                                            {"$set": {"opt_out": True}})
                # Cancel scheduled attempts for this phone's queue items
                orders = await db.orders.find({"org_id": org, "customer_phone": phone},
                                              {"_id": 0, "id": 1}).to_list(50)
                order_ids = [o["id"] for o in orders]
                queues = await db.call_queue.find({"org_id": org, "order_id": {"$in": order_ids}},
                                                   {"_id": 0, "id": 1}).to_list(50)
                for q in queues:
                    sched = await db.call_schedules.find_one({"queue_id": q["id"], "org_id": org},
                                                             {"_id": 0})
                    if not sched:
                        continue
                    for a in sched["attempts"]:
                        if a["status"] == "pending":
                            a["status"] = "skipped"
                    await db.call_schedules.update_one({"queue_id": q["id"], "org_id": org},
                                                      {"$set": {"attempts": sched["attempts"]}})
                    await db.call_queue.update_one({"id": q["id"], "org_id": org},
                                                  {"$set": {"status": "detenido",
                                                            "opt_out": True,
                                                            "updated_at": _now()}})
                processed_notes.append("opt_out_applied")

            if action:
                orders = await db.orders.find({"org_id": org, "customer_phone": phone},
                                              {"_id": 0, "id": 1},
                                              sort=[("created_at", -1)]).to_list(5)
                if orders:
                    q = await db.call_queue.find_one({"org_id": org, "order_id": orders[0]["id"]},
                                                     {"_id": 0, "id": 1},
                                                     sort=[("created_at", -1)])
                    if q:
                        await _stop_cadence(q["id"], action, org)
                        processed_notes.append(f"queue {q['id']} → {action}")

            # Automatizaciones del cliente ("cuando llega un mensaje…"). El texto
            # entrante es un DATO: solo rellena variables de la acción configurada.
            # Se ejecutan en segundo plano: el webhook responde sin esperarlas.
            from automation_engine import emit, inbound_depth
            await emit(org, "mensaje_entrante",
                       {"phone": phone, "text": text, "channel": "whatsapp",
                        "_depth": await inbound_depth(org, phone),
                        **({"_dedupe": f"wa:{pmid}"} if pmid else {})})

    await _log_event("chatea_pro", event_type or "unknown", body, True,
                     "; ".join(processed_notes), org)
    return {"ok": True, "processed": processed_notes}


# =========================================================================
# TWILIO — call status + recordings + verificación de caller ID
# =========================================================================
@router.post("/twilio/{org_token}",
             summary="Twilio del cliente dueño del token. Exige X-Twilio-Signature válida "
                     "con el Auth Token de ese cliente.")
async def twilio_webhook_org(org_token: str, request: Request,
                             x_twilio_signature: str | None = Header(
                                 default=None, alias="X-Twilio-Signature")):
    org = await _org_of_token(org_token)
    form = {k: str(v) for k, v in (await request.form()).items()}
    await _require_twilio(org, request, form, x_twilio_signature)
    return await _handle_twilio(org, form)


@router.post("/twilio",
             summary="(Antigua) Solo org «default»; exige X-Twilio-Signature válida.")
async def twilio_webhook(request: Request,
                        x_twilio_signature: str | None = Header(default=None,
                                                                alias="X-Twilio-Signature")):
    form = {k: str(v) for k, v in (await request.form()).items()}
    await _require_twilio(DEFAULT_ORG, request, form, x_twilio_signature)
    return await _handle_twilio(DEFAULT_ORG, form)


async def _handle_twilio(org: str, form: dict) -> dict:
    """Procesa un callback de Twilio tocando SOLO datos de `org`."""
    db = get_db()
    call_sid = form.get("CallSid")
    status = (form.get("CallStatus") or "").lower()  # initiated,ringing,answered,completed,no-answer,busy,failed
    recording_url = form.get("RecordingUrl")
    duration = form.get("CallDuration")
    to_number = form.get("To") or form.get("Called")
    queue_id = form.get("QueueId")  # optional: our own passthrough via `StatusCallbackParameter`
    attempt_number = form.get("AttemptNumber")

    processed_notes = []
    # Verificación de caller ID: SIEMPRE dentro de este cliente. Con CallSid se
    # casa con la validación que él inició; sin CallSid, con SU número pendiente.
    verification_status = form.get("VerificationStatus")
    if verification_status:
        num_status = "verified" if verification_status == "success" else "failed"
        num_q = {"org_id": org, "phone_number": to_number}
        if call_sid:
            num_q["call_sid"] = call_sid
        else:
            num_q["status"] = "pending"
        r = await db.connected_numbers.update_one(
            num_q,
            {"$set": {"status": num_status, "twilio_sid": form.get("OutgoingCallerIdSid"),
                      "updated_at": _now()}})
        processed_notes.append(f"caller_id={num_status} matched={r.matched_count}")

    # Update call attempt if we can match it (solo planes de este cliente)
    if queue_id and attempt_number:
        try:
            an = int(attempt_number)
            sched = await db.call_schedules.find_one({"queue_id": queue_id, "org_id": org},
                                                     {"_id": 0})
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
                await db.call_schedules.update_one({"queue_id": queue_id, "org_id": org},
                                                   {"$set": {"attempts": sched["attempts"]}})
                processed_notes.append(f"attempt#{an}={status}")
            else:
                processed_notes.append("queue_no_encontrada")
        except Exception as e:  # noqa: BLE001
            processed_notes.append(f"error: {type(e).__name__}")

    await _log_event("twilio", f"call_{status or 'unknown'}", form, True,
                     "; ".join(processed_notes), org)
    return {"ok": True, "processed": processed_notes}


# =========================================================================
# ELEVENLABS — post-call transcript + result
# =========================================================================
@router.post("/elevenlabs/{org_token}",
             summary="ElevenLabs (post-llamada) del cliente dueño del token.")
async def elevenlabs_webhook_org(org_token: str, request: Request):
    org = await _org_of_token(org_token)
    return await _handle_elevenlabs(org, _json(await request.body()))


@router.post("/elevenlabs",
             summary="(Antigua) Solo org «default» y con firma X-Elevenlabs-Signature obligatoria.")
async def elevenlabs_webhook(request: Request,
                            x_elevenlabs_signature: str | None = Header(
                                default=None, alias="X-Elevenlabs-Signature")):
    body_bytes = await request.body()
    await _require_hmac("elevenlabs", "ELEVENLABS_WEBHOOK_SECRET", body_bytes,
                        x_elevenlabs_signature)
    return await _handle_elevenlabs(DEFAULT_ORG, _json(body_bytes))


async def _handle_elevenlabs(org: str, body: dict) -> dict:
    """Procesa el resultado de una llamada tocando SOLO datos de `org`."""
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
    processed = False
    if queue_id and attempt_number and result:
        db = get_db()
        # El plan debe ser de ESTE cliente; el de otro "no existe".
        sched = await db.call_schedules.find_one({"queue_id": queue_id, "org_id": org}, {"_id": 0})
        if not sched:
            processed_notes.append("queue_no_encontrada")
        else:
            for a in sched["attempts"]:
                if a["attempt_number"] == int(attempt_number):
                    a["recording_url"] = recording_url
                    a["transcript"] = str(transcript)[:5000]
                    a["summary"] = str(summary)[:1000]
                    break
            await db.call_schedules.update_one({"queue_id": queue_id, "org_id": org},
                                               {"$set": {"attempts": sched["attempts"]}})
            # Delegate to the same handler used by /api/calls/attempt-result
            from routes.cadence import attempt_result
            from models import AttemptResult as AR
            try:
                r = await attempt_result(AR(queue_id=queue_id, attempt_number=int(attempt_number),
                                            result=result,
                                            notes=str(summary)[:2000] or str(transcript)[:2000]),
                                         org)
                processed_notes.append(f"advanced: {r}")
                processed = True
            except Exception as e:  # noqa: BLE001
                processed_notes.append(f"advance error: {type(e).__name__}")

    from automation_engine import emit
    cid = body.get("conversation_id") or body.get("call_id")
    await emit(org, "llamada_terminada", {
        "call_id": cid, "telefono": body.get("phone") or body.get("to_number") or "",
        "resultado": result or detected or "sin_clasificar", "duracion": body.get("duration"),
        "direction": "outbound", "agent_id": body.get("agent_id") or "",
        **({"_dedupe": f"el:{cid}"} if cid else {})})

    await _log_event("elevenlabs", f"call_ended:{detected or 'unknown'}",
                    body, processed, "; ".join(processed_notes), org)
    return {"ok": True, "result": result, "processed": processed_notes}


# =========================================================================
# helper — stop cadence and set ops status (used by Chatea auto-classify)
# =========================================================================
async def _stop_cadence(queue_id: str, action: str, org: str) -> None:
    db = get_db()
    await db.call_queue.update_one({"id": queue_id, "org_id": org},
                                   {"$set": {"status": action, "updated_at": _now()}})
    sched = await db.call_schedules.find_one({"queue_id": queue_id, "org_id": org}, {"_id": 0})
    if sched:
        for a in sched["attempts"]:
            if a["status"] == "pending":
                a["status"] = "skipped"
        await db.call_schedules.update_one({"queue_id": queue_id, "org_id": org},
                                          {"$set": {"attempts": sched["attempts"]}})
    from automation_engine import emit_queue_status
    await emit_queue_status(org, queue_id, action)


# =========================================================================
# INSPECTION — recent events (dev/debug)
# =========================================================================
@router.get("/events", summary="Recent webhook events of this org (debug). Requires auth.",
            dependencies=[Depends(require_api_key)])
async def list_events(provider: str | None = None, limit: int = 50,
                      org: str = Depends(get_org)):
    q = {"org_id": org}
    if provider:
        q["provider"] = provider
    docs = await get_db().webhook_events.find(q, {"_id": 0}).sort("created_at", -1) \
        .limit(min(limit, 200)).to_list(200)
    return docs
