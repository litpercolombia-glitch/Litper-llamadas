"""Routes: /connectors — Chatea Pro / Dropi / WhatsApp / Supabase status."""
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from db import get_db
from deps import require_api_key
from chatea import get_client as get_chatea
from supabase_sync import _configured as supabase_configured

router = APIRouter(prefix="/connectors", tags=["connectors"],
                   dependencies=[Depends(require_api_key)])


def _now():
    return datetime.now(timezone.utc).isoformat()


@router.get("", summary="List all connectors and their status.")
async def list_connectors():
    db = get_db()
    docs = await db.integration_connectors.find({}, {"_id": 0}).to_list(50)
    return docs


@router.post("/chatea_pro/test", summary="Ping Chatea Pro and record result.")
async def test_chatea():
    chatea = get_chatea()
    res = await chatea.test_connection()
    db = get_db()
    status = "connected" if res.get("ok") else "error"
    await db.integration_connectors.update_one(
        {"key": "chatea_pro"},
        {"$set": {"key": "chatea_pro", "name": "Chatea Pro (WhatsApp)",
                  "status": status, "last_checked_at": _now(),
                  "error_message": None if res.get("ok") else str(res.get("error") or res.get("status_code")),
                  "metadata": {"base_url": chatea.base_url,
                               "test_path": chatea.test_path,
                               "status_code": res.get("status_code")}}},
        upsert=True,
    )
    return res


@router.post("/supabase/test", summary="Check Supabase configuration & reachability.")
async def test_supabase():
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
        {"key": "supabase"},
        {"$set": {"key": "supabase", "name": "Supabase Postgres",
                  "status": status, "last_checked_at": _now(),
                  "error_message": error,
                  "metadata": {"url": url,
                               "service_key_present": bool(os.environ.get("SUPABASE_SERVICE_KEY"))}}},
        upsert=True,
    )
    return {"ok": status == "connected", "status": status, "url": url}
