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
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from db import get_db
from deps import require_api_key
from models import (ConnectedNumber, NumberVerifyStart, NumberVerifyConfirm,
                    NumberImport)
from twilio_client import get_client as get_twilio

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
