"""Routes: /connectors — Chatea Pro / Dropi / WhatsApp / Supabase status."""
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from db import get_db
from deps import get_org, require_api_key
from chatea import client_for as chatea_for
from supabase_sync import _configured as supabase_configured

router = APIRouter(prefix="/connectors", tags=["connectors"],
                   dependencies=[Depends(require_api_key)])


def _now():
    return datetime.now(timezone.utc).isoformat()


# Catálogo fijo (global, en código). El ESTADO de cada conector es por cliente
# y se guarda en integration_connectors con org_id — ya no se siembra al arrancar.
CONNECTOR_CATALOG = [
    ("chatea_pro", "Chatea Pro (WhatsApp)"),
    ("dropi", "Dropi (Fulfillment)"),
    ("whatsapp_business", "WhatsApp Business (Meta Cloud)"),
    ("supabase", "Supabase Postgres"),
    ("elevenlabs", "ElevenLabs (Voz IA)"),
    ("twilio", "Twilio (Caller ID)"),
]


@router.get("", summary="List all connectors and their status.")
async def list_connectors(org: str = Depends(get_org)):
    db = get_db()
    docs = await db.integration_connectors.find({"org_id": org}, {"_id": 0}).to_list(50)
    mine = {d["key"]: d for d in docs}
    return [mine.get(key) or {"key": key, "name": name, "status": "unconfigured",
                              "metadata": {}}
            for key, name in CONNECTOR_CATALOG]


@router.post("/chatea_pro/test", summary="Ping Chatea Pro (GET /me) and record result + workspace name.")
async def test_chatea(org: str = Depends(get_org)):
    chatea = await chatea_for(org)
    res = await chatea.test_connection()
    db = get_db()
    status = "connected" if res.get("ok") else "error"
    body = res.get("body") or {}
    # Extract a workspace/user name from common shapes
    ws_name = None
    if isinstance(body, dict):
        ws_name = (body.get("name")
                   or body.get("workspace_name")
                   or (body.get("workspace") or {}).get("name")
                   or (body.get("user") or {}).get("name")
                   or body.get("email"))
    await db.integration_connectors.update_one(
        {"org_id": org, "key": "chatea_pro"},
        {"$set": {"org_id": org, "key": "chatea_pro", "name": "Chatea Pro (WhatsApp)",
                  "status": status, "last_checked_at": _now(),
                  "error_message": None if res.get("ok") else (
                      res.get("error") or f"HTTP {res.get('status_code')}"),
                  "metadata": {"base_url": chatea.base_url,
                               "me_path": chatea.me_path,
                               "workspace_name": ws_name,
                               "status_code": res.get("status_code")}}},
        upsert=True,
    )
    return {**res, "workspace_name": ws_name}


@router.post("/elevenlabs/test", summary="Verify ElevenLabs API key by listing voices.")
async def test_elevenlabs(org: str = Depends(get_org)):
    from elevenlabs_client import client_for as eleven_for
    r = await (await eleven_for(org)).list_voices()
    db = get_db()
    status = "connected" if r.get("ok") else ("unconfigured" if not r.get("configured") else "error")
    await db.integration_connectors.update_one(
        {"org_id": org, "key": "elevenlabs"},
        {"$set": {"org_id": org, "key": "elevenlabs", "name": "ElevenLabs (Voz IA)",
                  "status": status, "last_checked_at": _now(),
                  "error_message": r.get("error"),
                  "metadata": {"voices_count": len(r.get("voices", []))}}},
        upsert=True,
    )
    return r


@router.post("/twilio/test", summary="Verify Twilio credentials by listing verified caller IDs.")
async def test_twilio(org: str = Depends(get_org)):
    from twilio_client import client_for as twilio_for
    r = await (await twilio_for(org)).list_verified()
    db = get_db()
    status = "connected" if r.get("ok") else ("unconfigured" if not r.get("configured") else "error")
    await db.integration_connectors.update_one(
        {"org_id": org, "key": "twilio"},
        {"$set": {"org_id": org, "key": "twilio", "name": "Twilio (Caller ID)",
                  "status": status, "last_checked_at": _now(),
                  "error_message": r.get("error"),
                  "metadata": {"verified_count": len(r.get("verified", []))}}},
        upsert=True,
    )
    return r


@router.post("/supabase/test", summary="Check Supabase configuration & reachability.")
async def test_supabase(org: str = Depends(get_org)):
    ok, url, _key = supabase_configured()
    db = get_db()
    status = "unconfigured"
    error = None
    if ok:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=8) as cli:
                r = await cli.get(f"{url}/rest/v1/", headers={"apikey": os.environ.get("SUPABASE_ANON_KEY", "")})
            status = "connected" if r.status_code < 500 else "error"
            if r.status_code >= 500:
                error = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            status = "error"
            error = str(e)
    await db.integration_connectors.update_one(
        {"org_id": org, "key": "supabase"},
        {"$set": {"org_id": org, "key": "supabase", "name": "Supabase Postgres",
                  "status": status, "last_checked_at": _now(),
                  "error_message": error,
                  "metadata": {"url": url,
                               "service_key_present": bool(os.environ.get("SUPABASE_SERVICE_KEY"))}}},
        upsert=True,
    )
    return {"ok": status == "connected", "status": status, "url": url}
