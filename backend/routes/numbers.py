"""Routes: /numbers — Twilio Verified Caller IDs (self-service).

Flow:
  POST /numbers/verify/start   → creates a Twilio OutgoingCallerId validation
                                 request. Twilio calls the number and expects
                                 the user to enter the 6-digit code. Returns
                                 { validation_code, call_sid } to display.
  POST /numbers/verify/confirm → polls Twilio's OutgoingCallerIds list; if the
                                 phone appears there, marks the local record
                                 as `verified`.
  GET  /numbers                → local list of connected numbers + statuses.
  POST /numbers/import         → mark an existing (already-verified in Twilio)
                                 number as connected locally.
  DELETE /numbers/{id}         → remove local record (does NOT unverify in Twilio).
"""
from datetime import datetime, timezone
import os
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from db import get_db
from deps import require_api_key
from models import (ConnectedNumber, NumberVerifyStart, NumberVerifyConfirm,
                    NumberImport, SipConnectionIn, PlaceCallIn, TelnyxRegisterIn)
from twilio_client import get_client as get_twilio
from elevenlabs_client import get_client as get_eleven

router = APIRouter(prefix="/numbers", tags=["numbers"],
                   dependencies=[Depends(require_api_key)])


def _now():
    return datetime.now(timezone.utc).isoformat()


@router.get("", response_model=List[ConnectedNumber],
            summary="List locally-connected phone numbers.")
async def list_numbers():
    docs = await get_db().connected_numbers.find({}, {"_id": 0}) \
        .sort("created_at", -1).to_list(100)
    return docs


@router.post("/verify/start",
             summary="Start a Twilio caller-ID validation. Returns validation_code to show to the user.")
async def verify_start(payload: NumberVerifyStart):
    db = get_db()
    twilio = get_twilio()
    if not twilio.configured:
        return {"ok": False, "configured": False,
                "error": "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN no configurados. Añádelos en backend/.env."}
    res = await twilio.start_validation(payload.phone_number, payload.friendly_name)
    if res.get("ok"):
        rec = ConnectedNumber(
            phone_number=payload.phone_number,
            friendly_name=payload.friendly_name,
            country=payload.country,
            provider="twilio",
            status="pending",
            validation_code=res.get("validation_code"),
            call_sid=res.get("call_sid"),
        )
        await db.connected_numbers.update_one(
            {"phone_number": payload.phone_number},
            {"$set": rec.model_dump()},
            upsert=True,
        )
    return res


@router.post("/verify/confirm",
             summary="Confirm — polls Twilio to see if the caller ID is now verified.")
async def verify_confirm(payload: NumberVerifyConfirm):
    db = get_db()
    twilio = get_twilio()
    if not twilio.configured:
        raise HTTPException(400, "Twilio no configurado.")
    ok = await twilio.check_verified(payload.phone_number)
    status = "verified" if ok else "pending"
    upd = {"status": status, "updated_at": _now()}
    await db.connected_numbers.update_one({"phone_number": payload.phone_number},
                                          {"$set": upd})
    doc = await db.connected_numbers.find_one({"phone_number": payload.phone_number},
                                              {"_id": 0})
    return {"ok": ok, "status": status, "number": doc}


@router.post("/import", response_model=ConnectedNumber,
             summary="Import an already-verified Twilio number as a connected caller ID.")
async def import_number(payload: NumberImport):
    db = get_db()
    rec = ConnectedNumber(
        phone_number=payload.phone_number,
        friendly_name=payload.friendly_name,
        country=payload.country,
        provider="twilio",
        status="imported",
        twilio_sid=payload.twilio_sid,
    )
    await db.connected_numbers.update_one(
        {"phone_number": payload.phone_number},
        {"$set": rec.model_dump()},
        upsert=True,
    )
    return rec


@router.get("/twilio/verified",
            summary="Passthrough — list ALL verified caller IDs in the Twilio account.")
async def twilio_verified():
    return await get_twilio().list_verified()


@router.delete("/{number_id}",
               summary="Remove a locally-connected number (does NOT unverify in Twilio).")
async def delete_number(number_id: str):
    r = await get_db().connected_numbers.delete_one({"id": number_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Número no encontrado")
    return {"ok": True, "id": number_id}



# ============================================================================
# DIDWW SIP TRUNK  ·  register in ElevenLabs · place outbound calls via Sofía
# ============================================================================
@router.get("/sip/config", summary="Read the current SIP config (mask secrets).")
async def sip_config_read():
    """Report which SIP env vars are set. Secrets NEVER leak — only booleans."""
    return {
        "provider":            os.environ.get("SIP_PROVIDER", "didww"),
        "sip_domain":          os.environ.get("DIDWW_SIP_DOMAIN", ""),
        "sip_username_set":    bool(os.environ.get("DIDWW_SIP_USERNAME")),
        "sip_password_set":    bool(os.environ.get("DIDWW_SIP_PASSWORD")),
        "outbound_trunk_id":   os.environ.get("DIDWW_OUTBOUND_TRUNK_ID", ""),
        "caller_id_number":    os.environ.get("CALLER_ID_NUMBER", ""),
        "elevenlabs_agent_id": os.environ.get("ELEVENLABS_AGENT_ID", ""),
    }


@router.post("/sip/test", summary="Validate SIP configuration (format + reachability).")
async def sip_test():
    cfg = await sip_config_read()
    problems = []
    if not cfg["sip_domain"]:            problems.append("DIDWW_SIP_DOMAIN vacío")
    if not cfg["sip_username_set"]:      problems.append("DIDWW_SIP_USERNAME vacío")
    if not cfg["sip_password_set"]:      problems.append("DIDWW_SIP_PASSWORD vacío")
    caller = cfg["caller_id_number"]
    if not caller:                       problems.append("CALLER_ID_NUMBER vacío")
    elif not caller.startswith("+"):     problems.append("CALLER_ID_NUMBER debe ser E.164 (+57…)")
    if not cfg["elevenlabs_agent_id"]:   problems.append("ELEVENLABS_AGENT_ID vacío")
    return {"ok": len(problems) == 0, "provider": cfg["provider"],
            "issues": problems, "config": cfg}


@router.post("/sip/register", response_model=ConnectedNumber,
             summary="Register the DIDWW SIP trunk in ElevenLabs so the agent can dial out.")
async def sip_register(payload: SipConnectionIn | None = None):
    caller = (payload.caller_id_number if payload else os.environ.get("CALLER_ID_NUMBER", "")).strip()
    domain = (payload.sip_domain if payload else os.environ.get("DIDWW_SIP_DOMAIN", "")).strip()
    user   = (payload.sip_username if payload else os.environ.get("DIDWW_SIP_USERNAME", "")).strip()
    pw     = (payload.sip_password if payload else os.environ.get("DIDWW_SIP_PASSWORD", "")).strip()
    label  = (payload.friendly_name if payload else None) or f"Litper DIDWW {caller}"
    if not (caller and domain and user and pw):
        raise HTTPException(400, "SIP credentials incompletas. Añade DIDWW_* + CALLER_ID_NUMBER en backend/.env "
                                "o envíalos en el body.")

    res = await get_eleven().register_sip_trunk(
        label=label, address=domain, username=user, password=pw, phone_number=caller)
    if not res.get("ok"):
        # Return 400 (not 502) so the ingress does not swallow the error detail.
        raise HTTPException(400, detail={"error": "ElevenLabs SIP register failed", "elevenlabs": res})
    pn_id = res.get("phone_number_id")
    db = get_db()
    rec = ConnectedNumber(
        phone_number=caller, friendly_name=label, country="CO",
        provider="didww_sip", status="sip_registered",
        elevenlabs_phone_number_id=pn_id,
        sip_domain=domain, caller_id_number=caller,
    )
    await db.connected_numbers.update_one(
        {"phone_number": caller, "provider": "didww_sip"},
        {"$set": rec.model_dump()}, upsert=True)
    return rec


@router.post("/call/test",
             summary="Place a test outbound call via ElevenLabs + the registered SIP number.")
async def place_test_call(payload: PlaceCallIn):
    db = get_db()
    num = await db.connected_numbers.find_one(
        {"provider": "didww_sip", "status": "sip_registered"},
        {"_id": 0}, sort=[("updated_at", -1)])
    if not num or not num.get("elevenlabs_phone_number_id"):
        raise HTTPException(400, "No hay número SIP registrado en ElevenLabs. Regístralo primero.")

    to_num = payload.to_number
    country = "CO"
    queue = None
    if payload.queue_id and payload.queue_id != "test":
        queue = await db.call_queue.find_one({"id": payload.queue_id}, {"_id": 0})
        if not queue:
            raise HTTPException(404, "queue_id no encontrado")
        order = await db.orders.find_one({"id": queue["order_id"]}, {"_id": 0})
        if not to_num and order:
            to_num = order.get("customer_phone")
        country = (order or {}).get("country", "CO")
    if not to_num:
        raise HTTPException(400, "Falta 'to_number' o un queue_id válido.")

    voice = await db.voice_profiles.find_one(
        {"country": country, "is_default": True}, {"_id": 0}) \
        or await db.voice_profiles.find_one({}, {"_id": 0})

    agent_id = os.environ.get("ELEVENLABS_AGENT_ID", "").strip()
    if not agent_id:
        raise HTTPException(400, "ELEVENLABS_AGENT_ID no configurado en backend/.env.")

    metadata = {"queue_id": payload.queue_id or "test", "country": country,
                "voice_name": (voice or {}).get("name", ""),
                "caller_id": num.get("caller_id_number")}
    res = await get_eleven().sip_outbound_call(
        phone_number_id=num["elevenlabs_phone_number_id"],
        agent_id=agent_id, to_number=to_num, metadata=metadata)
    if not res.get("ok"):
        raise HTTPException(400, detail={"error": "ElevenLabs SIP call failed", "elevenlabs": res})

    import uuid as _u
    await db.message_log.insert_one({
        "id": str(_u.uuid4()),
        "order_id": (queue or {}).get("order_id"),
        "queue_id": payload.queue_id,
        "direction": "outbound", "channel": "call",
        "phone": to_num,
        "body": f"Llamada SIP iniciada (agent {agent_id}, voz {(voice or {}).get('name','?')}).",
        "provider": "elevenlabs_sip",
        "provider_message_id": res.get("conversation_id"),
        "status": "sent", "created_at": _now(),
    })
    return {"ok": True, "conversation_id": res.get("conversation_id"),
            "to": to_num, "from": num.get("caller_id_number"),
            "voice": (voice or {}).get("name")}


# ---------------------------------------------------------------------------
# TELNYX SIP TRUNK (primary provider going forward — DIDWW/Twilio secondary).
# ---------------------------------------------------------------------------
@router.post("/telnyx/register",
             summary="Register the Telnyx SIP trunk in ElevenLabs so the agent can dial out.")
async def telnyx_register(payload: TelnyxRegisterIn | None = None):
    """
    Uses TELNYX_* env by default; body fields override for one-off setups.
    Requires:
      - TELNYX_SIP_USERNAME / TELNYX_SIP_PASSWORD  (SIP credentials for outbound)
      - TELNYX_SIP_DOMAIN                         (usually sip.telnyx.com)
      - TELNYX_PHONE_NUMBER                       (E.164 caller ID from the trunk)
    """
    caller = (payload.telnyx_phone_number if payload else None) \
        or os.environ.get("TELNYX_PHONE_NUMBER", "").strip()
    domain = os.environ.get("TELNYX_SIP_DOMAIN", "sip.telnyx.com").strip()
    user   = os.environ.get("TELNYX_SIP_USERNAME", "").strip()
    pw     = os.environ.get("TELNYX_SIP_PASSWORD", "").strip()
    conn_id = (payload.telnyx_connection_id if payload else None) \
        or os.environ.get("TELNYX_CONNECTION_ID", "").strip()
    label  = (payload.friendly_name if payload else None) or f"Litper Telnyx {caller}"

    missing: list[str] = []
    if not caller: missing.append("TELNYX_PHONE_NUMBER")
    if not user:   missing.append("TELNYX_SIP_USERNAME")
    if not pw:     missing.append("TELNYX_SIP_PASSWORD")
    if missing:
        raise HTTPException(400, f"Faltan variables en backend/.env: {', '.join(missing)}")

    res = await get_eleven().register_sip_trunk(
        label=label, address=domain, username=user, password=pw, phone_number=caller)
    if not res.get("ok"):
        raise HTTPException(400, detail={"error": "ElevenLabs SIP register failed",
                                        "elevenlabs": res})

    pn_id = res.get("phone_number_id")
    db = get_db()
    rec = ConnectedNumber(
        phone_number=caller, friendly_name=label, country="CO",
        provider="telnyx_sip", status="sip_registered",
        elevenlabs_phone_number_id=pn_id,
        sip_domain=domain, caller_id_number=caller,
    )
    await db.connected_numbers.update_one(
        {"phone_number": caller, "provider": "telnyx_sip"},
        {"$set": {**rec.model_dump(),
                  "telnyx_connection_id": conn_id or None}},
        upsert=True)
    return {**rec.model_dump(), "telnyx_connection_id": conn_id or None}


@router.get("/telnyx/config",
            summary="Return the current Telnyx env config (masked) — for the UI.")
async def telnyx_config():
    ap = os.environ.get("TELNYX_API_KEY", "")
    return {
        "provider": "telnyx",
        "api_key_present":       bool(ap),
        "connection_id_present": bool(os.environ.get("TELNYX_CONNECTION_ID")),
        "phone_number":          os.environ.get("TELNYX_PHONE_NUMBER", ""),
        "sip_domain":            os.environ.get("TELNYX_SIP_DOMAIN", "sip.telnyx.com"),
        "sip_username_present":  bool(os.environ.get("TELNYX_SIP_USERNAME")),
        "sip_password_present":  bool(os.environ.get("TELNYX_SIP_PASSWORD")),
        # never leak the full key
        "api_key_masked":        (ap[:4] + "…" + ap[-4:]) if len(ap) > 8 else "",
    }
