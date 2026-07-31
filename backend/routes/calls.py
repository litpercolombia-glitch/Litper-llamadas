"""POST /api/calls/webhook — Retell posts call_ended events here.
GET  /api/calls          — list the org's calls for the "Llamadas" tab.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from db import get_db
from deps import require_api_key


router = APIRouter(prefix="/calls", tags=["calls"])


def _iso() -> str: return datetime.now(timezone.utc).isoformat()


async def _org_id(request: Request) -> str:
    try:
        from routes.auth import _decode, COOKIE_NAME
        tok = request.cookies.get(COOKIE_NAME)
        claims = _decode(tok) if tok else None
        if claims and claims.get("org"): return claims["org"]
    except Exception: pass
    return request.headers.get("X-Org-Id", "").strip() or "default"


@router.post("/webhook",
             summary="Retell post-call webhook — stores the transcript + recording.")
async def calls_webhook(request: Request):
    body = await request.json()
    # Retell schema uses either flat or nested `call` — support both.
    call = body.get("call") if isinstance(body.get("call"), dict) else body
    event = body.get("event") or body.get("type") or "call_ended"
    call_id = call.get("call_id") or call.get("id") or call.get("callId")
    if not call_id:
        raise HTTPException(400, "call_id ausente")

    meta = call.get("metadata") or {}
    doc = {
        "id":            call_id,
        "call_id":       call_id,
        "org_id":        meta.get("zynex_org_id"),
        "agent_id":      meta.get("zynex_agent_id"),
        "retell_agent_id": call.get("agent_id"),
        "telefono":      call.get("to_number") or call.get("customer_number"),
        "from_number":   call.get("from_number"),
        "duracion":      call.get("call_length") or call.get("duration_ms"),
        "recording_url": call.get("recording_url") or call.get("recordingUrl"),
        "transcript":    call.get("transcript"),
        "resultado":     (call.get("call_analysis") or {}).get("call_summary_title")
                          or call.get("disposition")
                          or "sin_clasificar",
        "cost_usd":      call.get("cost") or call.get("cost_usd"),
        "event":         event,
        "created_at":    _iso(),
    }
    await get_db().calls.update_one(
        {"call_id": call_id}, {"$set": doc}, upsert=True,
    )
    return {"ok": True, "stored": call_id}


@router.get("",
            summary="Lista las llamadas de la org actual (pestaña Llamadas).",
            dependencies=[Depends(require_api_key)])
async def list_calls(request: Request, agent_id: Optional[str] = None,
                     limit: int = 100):
    org_id = await _org_id(request)
    q: dict = {"org_id": org_id}
    if agent_id: q["agent_id"] = agent_id
    docs = await get_db().calls.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(min(limit, 500)).to_list(limit)
    return {"calls": docs}


@router.get("/count", dependencies=[Depends(require_api_key)])
async def calls_count(request: Request):
    org_id = await _org_id(request)
    total = await get_db().calls.count_documents({"org_id": org_id})
    return {"total": total}
