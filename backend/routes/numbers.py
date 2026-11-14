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
from deps import get_org, require_api_key
from models import (ConnectedNumber, NumberVerifyStart, NumberVerifyConfirm,
                    NumberImport, SipConnectionIn, PlaceCallIn, TelnyxRegisterIn)
from twilio_client import client_for as twilio_for, NOT_CONNECTED as TWILIO_OFF
from elevenlabs_client import client_for as eleven_for
from org_credentials import get_credentials

router = APIRouter(prefix="/numbers", tags=["numbers"],
                   dependencies=[Depends(require_api_key)])


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _org_country(org: str) -> str:
    """País del perfil del cliente ("CO" si no lo definió — valor histórico)."""
    from routes.org_profile import get_profile
    return (await get_profile(org))["pais"] or "CO"


@router.get("", response_model=List[ConnectedNumber],
            summary="List locally-connected phone numbers.")
async def list_numbers(org: str = Depends(get_org)):
    docs = await get_db().connected_numbers.find({"org_id": org}, {"_id": 0}) \
        .sort("created_at", -1).to_list(100)
    return docs


@router.post("/verify/start",
             summary="Start a Twilio caller-ID validation. Returns validation_code to show to the user.")
async def verify_start(payload: NumberVerifyStart, org: str = Depends(get_org)):
    db = get_db()
    twilio = await twilio_for(org)
    if not twilio.configured:
        return {"ok": False, "configured": False, "error": TWILIO_OFF}
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
            {"org_id": org, "phone_number": payload.phone_number},
            {"$set": {**rec.model_dump(), "org_id": org}},
            upsert=True,
        )
    return res


@router.post("/verify/confirm",
             summary="Confirm — polls Twilio to see if the caller ID is now verified.")
async def verify_confirm(payload: NumberVerifyConfirm, org: str = Depends(get_org)):
    db = get_db()
    twilio = await twilio_for(org)
    if not twilio.configured:
        raise HTTPException(400, TWILIO_OFF)
    ok = await twilio.check_verified(payload.phone_number)
    status = "verified" if ok else "pending"
    upd = {"status": status, "updated_at": _now()}
    await db.connected_numbers.update_one(
        {"org_id": org, "phone_number": payload.phone_number}, {"$set": upd})
    doc = await db.connected_numbers.find_one(
        {"org_id": org, "phone_number": payload.phone_number}, {"_id": 0})
    return {"ok": ok, "status": status, "number": doc}


@router.post("/import", response_model=ConnectedNumber,
             summary="Import an already-verified Twilio number as a connected caller ID.")
async def import_number(payload: NumberImport, org: str = Depends(get_org)):
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
        {"org_id": org, "phone_number": payload.phone_number},
        {"$set": {**rec.model_dump(), "org_id": org}},
        upsert=True,
    )
    return rec


@router.get("/twilio/verified",
            summary="Passthrough — list ALL verified caller IDs in the Twilio account.")
async def twilio_verified(org: str = Depends(get_org)):
    return await (await twilio_for(org)).list_verified()


@router.delete("/{number_id}",
               summary="Remove a locally-connected number (does NOT unverify in Twilio).")
async def delete_number(number_id: str, org: str = Depends(get_org)):
    r = await get_db().connected_numbers.delete_one({"id": number_id, "org_id": org})
    if r.deleted_count == 0:
        raise HTTPException(404, "Número no encontrado")
    return {"ok": True, "id": number_id}



# ============================================================================
# DIDWW SIP TRUNK  ·  register in ElevenLabs · place outbound calls via Sofía
# ============================================================================
def _platform_env(org: str, name: str, default: str = "") -> str:
    """Variable de entorno del SERVIDOR, solo para clientes con permiso de
    llaves de plataforma (PLATFORM_KEYS_ORGS). Para el resto: vacío."""
    from org_credentials import platform_keys_allowed
    return os.environ.get(name, default).strip() if platform_keys_allowed(org) else default


@router.get("/sip/config", summary="Read the current SIP config (mask secrets).")
async def sip_config_read(org: str = Depends(get_org)):
    """Report which SIP settings are set for THIS client. Secrets NEVER leak — only booleans."""
    eleven = await eleven_for(org)
    return {
        "provider":            _platform_env(org, "SIP_PROVIDER", "didww") or "didww",
        "sip_domain":          _platform_env(org, "DIDWW_SIP_DOMAIN"),
        "sip_username_set":    bool(_platform_env(org, "DIDWW_SIP_USERNAME")),
        "sip_password_set":    bool(_platform_env(org, "DIDWW_SIP_PASSWORD")),
        "outbound_trunk_id":   _platform_env(org, "DIDWW_OUTBOUND_TRUNK_ID"),
        "caller_id_number":    _platform_env(org, "CALLER_ID_NUMBER"),
        "elevenlabs_agent_id": eleven.agent_id,
    }


@router.post("/sip/test", summary="Validate SIP configuration (format + reachability).")
async def sip_test(org: str = Depends(get_org)):
    cfg = await sip_config_read(org)
    problems = []
    if not cfg["sip_domain"]:            problems.append("Dominio SIP vacío")
    if not cfg["sip_username_set"]:      problems.append("Usuario SIP vacío")
    if not cfg["sip_password_set"]:      problems.append("Contraseña SIP vacía")
    caller = cfg["caller_id_number"]
    if not caller:                       problems.append("Número de salida vacío")
    elif not caller.startswith("+"):     problems.append("El número de salida debe ser E.164 (+57…)")
    if not cfg["elevenlabs_agent_id"]:   problems.append("Falta el Agent ID de ElevenLabs (Conexiones)")
    return {"ok": len(problems) == 0, "provider": cfg["provider"],
            "issues": problems, "config": cfg}


@router.post("/sip/register", response_model=ConnectedNumber,
             summary="Register the DIDWW SIP trunk in ElevenLabs so the agent can dial out.")
async def sip_register(payload: SipConnectionIn | None = None, org: str = Depends(get_org)):
    caller = (payload.caller_id_number if payload else _platform_env(org, "CALLER_ID_NUMBER")).strip()
    domain = (payload.sip_domain if payload else _platform_env(org, "DIDWW_SIP_DOMAIN")).strip()
    user   = (payload.sip_username if payload else _platform_env(org, "DIDWW_SIP_USERNAME")).strip()
    pw     = (payload.sip_password if payload else _platform_env(org, "DIDWW_SIP_PASSWORD")).strip()
    label  = (payload.friendly_name if payload else None) or f"DIDWW {caller}"
    if not (caller and domain and user and pw):
        raise HTTPException(400, "Credenciales SIP incompletas: envía dominio, usuario, contraseña y número de salida.")

    res = await (await eleven_for(org)).register_sip_trunk(
        label=label, address=domain, username=user, password=pw, phone_number=caller)
    if not res.get("ok"):
        # Return 400 (not 502) so the ingress does not swallow the error detail.
        raise HTTPException(400, detail={"error": "ElevenLabs SIP register failed", "elevenlabs": res})
    pn_id = res.get("phone_number_id")
    db = get_db()
    rec = ConnectedNumber(
        phone_number=caller, friendly_name=label, country=await _org_country(org),
        provider="didww_sip", status="sip_registered",
        elevenlabs_phone_number_id=pn_id,
        sip_domain=domain, caller_id_number=caller,
    )
    await db.connected_numbers.update_one(
        {"org_id": org, "phone_number": caller, "provider": "didww_sip"},
        {"$set": {**rec.model_dump(), "org_id": org}}, upsert=True)
    return rec


@router.post("/call/test",
             summary="Place a test outbound call via ElevenLabs + the registered SIP number.")
async def place_test_call(payload: PlaceCallIn, org: str = Depends(get_org)):
    db = get_db()
    num = await db.connected_numbers.find_one(
        {"org_id": org, "provider": "didww_sip", "status": "sip_registered"},
        {"_id": 0}, sort=[("updated_at", -1)])
    if not num or not num.get("elevenlabs_phone_number_id"):
        raise HTTPException(400, "No hay número SIP registrado en ElevenLabs. Regístralo primero.")

    to_num = payload.to_number
    country = await _org_country(org)
    queue = None
    if payload.queue_id and payload.queue_id != "test":
        queue = await db.call_queue.find_one({"id": payload.queue_id, "org_id": org}, {"_id": 0})
        if not queue:
            raise HTTPException(404, "queue_id no encontrado")
        order = await db.orders.find_one({"id": queue["order_id"], "org_id": org}, {"_id": 0})
        if not to_num and order:
            to_num = order.get("customer_phone")
        country = (order or {}).get("country") or country
    if not to_num:
        raise HTTPException(400, "Falta 'to_number' o un queue_id válido.")

    voice = await db.voice_profiles.find_one(
        {"org_id": org, "country": country, "is_default": True}, {"_id": 0}) \
        or await db.voice_profiles.find_one({"org_id": org}, {"_id": 0})

    eleven = await eleven_for(org)   # cuenta y agente de ESTE cliente
    agent_id = eleven.agent_id
    if not agent_id:
        raise HTTPException(400, "Falta el Agent ID de ElevenLabs. Conecta tu cuenta de ElevenLabs en Conexiones.")

    metadata = {"queue_id": payload.queue_id or "test", "country": country,
                "voice_name": (voice or {}).get("name", ""),
                "caller_id": num.get("caller_id_number")}
    res = await eleven.sip_outbound_call(
        phone_number_id=num["elevenlabs_phone_number_id"],
        agent_id=agent_id, to_number=to_num, metadata=metadata)
    if not res.get("ok"):
        raise HTTPException(400, detail={"error": "ElevenLabs SIP call failed", "elevenlabs": res})

    import uuid as _u
    await db.message_log.insert_one({
        "id": str(_u.uuid4()),
        "org_id": org,
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
async def telnyx_register(payload: TelnyxRegisterIn | None = None, org: str = Depends(get_org)):
    """
    Uses TELNYX_* env by default; body fields override for one-off setups.
    Requires:
      - TELNYX_SIP_USERNAME / TELNYX_SIP_PASSWORD  (SIP credentials for outbound)
      - TELNYX_SIP_DOMAIN                         (usually sip.telnyx.com)
      - TELNYX_PHONE_NUMBER                       (E.164 caller ID from the trunk)
    """
    tx = await get_credentials("telnyx", org)      # cuenta Telnyx de ESTE cliente
    caller = (payload.telnyx_phone_number if payload else None) or tx.get("phone_number", "")
    domain = tx.get("sip_domain") or "sip.telnyx.com"
    user   = tx.get("sip_username", "")
    pw     = tx.get("sip_password", "")
    conn_id = (payload.telnyx_connection_id if payload else None) or tx.get("connection_id", "")
    label  = (payload.friendly_name if payload else None) or f"Telnyx {caller}"

    missing: list[str] = []
    if not caller: missing.append("número E.164")
    if not user:   missing.append("SIP username")
    if not pw:     missing.append("SIP password")
    if missing:
        raise HTTPException(400, "Conecta tu cuenta de Telnyx en Conexiones. Falta: " + ", ".join(missing))

    res = await (await eleven_for(org)).register_sip_trunk(
        label=label, address=domain, username=user, password=pw, phone_number=caller)
    if not res.get("ok"):
        raise HTTPException(400, detail={"error": "ElevenLabs SIP register failed",
                                        "elevenlabs": res})

    pn_id = res.get("phone_number_id")
    db = get_db()
    rec = ConnectedNumber(
        phone_number=caller, friendly_name=label, country=await _org_country(org),
        provider="telnyx_sip", status="sip_registered",
        elevenlabs_phone_number_id=pn_id,
        sip_domain=domain, caller_id_number=caller,
    )
    await db.connected_numbers.update_one(
        {"org_id": org, "phone_number": caller, "provider": "telnyx_sip"},
        {"$set": {**rec.model_dump(), "org_id": org,
                  "telnyx_connection_id": conn_id or None}},
        upsert=True)
    return {**rec.model_dump(), "telnyx_connection_id": conn_id or None}


@router.get("/telnyx/config",
            summary="Return the current Telnyx env config (masked) — for the UI.")
async def telnyx_config(org: str = Depends(get_org)):
    tx = await get_credentials("telnyx", org)      # nunca la cuenta de otro cliente
    ap = tx.get("api_key", "")
    return {
        "provider": "telnyx",
        "api_key_present":       bool(ap),
        "connection_id_present": bool(tx.get("connection_id")),
        "phone_number":          tx.get("phone_number", ""),
        "sip_domain":            tx.get("sip_domain") or "sip.telnyx.com",
        "sip_username_present":  bool(tx.get("sip_username")),
        "sip_password_present":  bool(tx.get("sip_password")),
        # never leak the full key
        "api_key_masked":        (ap[:4] + "…" + ap[-4:]) if len(ap) > 8 else "",
    }
