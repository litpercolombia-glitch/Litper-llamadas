"""POST /api/calls/webhook/{org_token} — Retell posts call_ended events here
(URL por cliente; la antigua /api/calls/webhook exige RETELL_WEBHOOK_SECRET).
GET  /api/calls          — list the org's calls for the "Llamadas" tab.
"""
from __future__ import annotations
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from db import get_db
from deps import require_api_key


router = APIRouter(prefix="/calls", tags=["calls"])
log = logging.getLogger("calls")

WEBHOOK_SECRET_HEADER = "X-Webhook-Secret"


def _check_webhook_secret(request: Request) -> bool:
    """Ruta antigua (sin token): FALLA CERRADO. Sin RETELL_WEBHOOK_SECRET en el
    servidor → 503; cabecera X-Webhook-Secret ausente o distinta → 401."""
    secret = os.environ.get("RETELL_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(503, "Webhook de llamadas sin configurar: falta "
                                 "RETELL_WEBHOOK_SECRET. Usa la URL con token de tu cuenta "
                                 "(GET /api/org/webhook-urls).")
    given = request.headers.get(WEBHOOK_SECRET_HEADER, "") or ""
    if not hmac.compare_digest(given.encode(), secret.encode()):
        raise HTTPException(401, "Secreto de webhook inválido.")
    return True


async def _resolve_call_owner(call_id: str, call: dict, meta: dict,
                              org: str | None = None) -> tuple:
    """(org_id, agent_id) del dueño de la llamada, SIEMPRE desde lo guardado.

    * Con `org` (URL con token del cliente): el dueño ES ese cliente; el agente
      solo se busca entre SUS agentes.
    * Sin `org` (ruta antigua, secreto de plataforma ya verificado):
        1. la llamada ya registrada (mismo call_id);
        2. el agente guardado cuyo retell_agent_id coincide;
        3. el agente guardado con id == zynex_agent_id.
    Nunca se confía en `zynex_org_id` del cuerpo. Sin dueño → (None, None)."""
    db = get_db()
    scope = {"org_id": org} if org else {}
    if not org:
        prev = await db.calls.find_one({"call_id": call_id},
                                       {"_id": 0, "org_id": 1, "agent_id": 1})
        if prev and prev.get("org_id"):
            return prev["org_id"], prev.get("agent_id")
    agent = None
    if call.get("agent_id"):
        agent = await db.custom_agents.find_one({**scope, "retell_agent_id": call["agent_id"]},
                                                {"_id": 0, "id": 1, "org_id": 1})
    if not agent and meta.get("zynex_agent_id"):
        agent = await db.custom_agents.find_one({**scope, "id": meta["zynex_agent_id"]},
                                                {"_id": 0, "id": 1, "org_id": 1})
    if org:
        return org, (agent or {}).get("id")
    return ((agent or {}).get("org_id"), (agent or {}).get("id"))


def _iso() -> str: return datetime.now(timezone.utc).isoformat()


async def _org_id(request: Request) -> str:
    from tenant import org_from_request
    return org_from_request(request)


async def _store_call(body: dict, org: str | None) -> dict:
    """Guarda/actualiza la llamada. El upsert filtra SIEMPRE por (call_id, org_id):
    un evento nunca pisa la llamada de otro cliente."""
    if not isinstance(body, dict):
        raise HTTPException(400, "Cuerpo inválido")
    # Retell schema uses either flat or nested `call` — support both.
    call = body.get("call") if isinstance(body.get("call"), dict) else body
    event = body.get("event") or body.get("type") or "call_ended"
    call_id = call.get("call_id") or call.get("id") or call.get("callId")
    if not call_id:
        raise HTTPException(400, "call_id ausente")
    call_id = str(call_id)

    meta = call.get("metadata") if isinstance(call.get("metadata"), dict) else {}
    org_id, agent_id = await _resolve_call_owner(call_id, call, meta, org)
    doc = {
        "id":            call_id,
        "call_id":       call_id,
        "org_id":        org_id,      # None = sin dueño verificable (nadie la ve)
        "agent_id":      agent_id,
        "retell_agent_id": call.get("agent_id"),
        "telefono":      call.get("to_number") or call.get("customer_number"),
        "from_number":   call.get("from_number"),
        "direction":     call.get("direction"),
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
    try:
        await get_db().calls.update_one(
            # org_id None = huérfana (sin dueño): el dueño verificado puede adoptarla.
            {"call_id": call_id, "org_id": {"$in": [org_id, None]}}, {"$set": doc}, upsert=True,
        )
    except Exception as e:  # noqa: BLE001 — call_id único: ya existe en OTRO cliente
        if "duplicate" in str(e).lower() or type(e).__name__ == "DuplicateKeyError":
            raise HTTPException(409, "Esa llamada pertenece a otra cuenta.")
        raise
    return {"ok": True, "stored": call_id, "org_resolved": bool(org_id)}


@router.post("/webhook/{org_token}",
             summary="Retell post-call webhook del cliente dueño del token.")
async def calls_webhook_org(org_token: str, request: Request):
    import webhook_tokens
    org = await webhook_tokens.org_for_token(org_token)
    if not org:
        raise HTTPException(401, "Token de webhook inválido.")
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "JSON inválido")
    return await _store_call(body, org)


@router.post("/webhook",
             summary="(Antigua) Exige X-Webhook-Secret == RETELL_WEBHOOK_SECRET; sin secreto → 503.")
async def calls_webhook(request: Request):
    _check_webhook_secret(request)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "JSON inválido")
    return await _store_call(body, None)


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
