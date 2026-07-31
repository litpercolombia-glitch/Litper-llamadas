"""Retell integration — creates/updates a voice agent so the custom agents
built through the wizard can actually receive real calls.

BYOK: reads `RETELL_API_KEY` from env. If missing, we short-circuit and
return `configured=False` so the wizard/UI can stay in BETA mode without
raising errors. LLM engine is HARDCODED to Claude Haiku @ temp 0.3 —
NEVER a reasoning model (introduces dead air on the call). This is
independent from Lyan (the internal Sonnet copilot).
"""
from __future__ import annotations
import os
import logging
import httpx

log = logging.getLogger("retell")

RETELL_BASE = "https://api.retellai.com"
LLM_MODEL   = "claude-haiku-4-5"   # explicit — NO reasoning models
LLM_TEMP    = 0.3


def api_key() -> str | None:
    v = os.environ.get("RETELL_API_KEY", "").strip()
    return v or None


def configured() -> bool:
    return api_key() is not None


async def _req(method: str, path: str, json: dict | None = None) -> tuple[bool, dict]:
    if not configured():
        return False, {"error": "RETELL_API_KEY no configurada"}
    try:
        async with httpx.AsyncClient(timeout=15) as x:
            r = await x.request(
                method, f"{RETELL_BASE}{path}",
                headers={"Authorization": f"Bearer {api_key()}",
                         "Content-Type": "application/json"},
                json=json,
            )
        ok = r.status_code < 400
        try:    body = r.json()
        except Exception: body = {"raw": r.text[:400]}
        return ok, body
    except Exception as e:
        log.warning("retell %s %s failed: %s", method, path, e)
        return False, {"error": str(e)}


def _agent_payload(a: dict) -> dict:
    """Compose the Retell create/update body from our custom_agent doc."""
    return {
        "agent_name": a.get("nombre", "Sofía"),
        "voice_id":   a.get("voz_id") or "EXAVITQu4vr4xnSDxMaL",
        "language":   a.get("idioma") or "es-CO",
        "llm": {
            "provider":    "anthropic",
            "model":       LLM_MODEL,
            "temperature": LLM_TEMP,
            "system_prompt": a.get("prompt", ""),
        },
        "enable_backchannel":  True,
        "responsiveness":      1.0,
        "interruption_sensitivity": 1.0,
        # Zynex meta so we can trace which org owns the agent.
        "metadata": {
            "zynex_agent_id": a.get("id"),
            "zynex_org_id":   a.get("org_id"),
            "zynex_purpose":  a.get("proposito"),
        },
    }


async def upsert_agent(a: dict) -> dict:
    """Create or update the Retell agent. Returns {ok, retell_agent_id, ...}."""
    if not configured():
        return {"ok": False, "beta": True,
                "detail": "RETELL_API_KEY no configurada; agente en BETA."}
    payload = _agent_payload(a)
    existing = a.get("retell_agent_id")
    if existing:
        ok, body = await _req("PATCH", f"/update-agent/{existing}", payload)
        rid = existing if ok else None
    else:
        ok, body = await _req("POST", "/create-agent", payload)
        rid = body.get("agent_id") if ok else None
    return {"ok": ok, "retell_agent_id": rid, "response": body}


async def place_call(retell_agent_id: str, to_number: str,
                     from_number: str | None = None) -> dict:
    """BETA: trigger a Retell outbound call. If Retell is not configured or
    the number isn't provisioned, callers should handle beta=true upstream."""
    if not configured():
        return {"ok": False, "beta": True,
                "detail": "RETELL_API_KEY no configurada"}
    payload = {"agent_id": retell_agent_id, "to_number": to_number}
    if from_number:
        payload["from_number"] = from_number
    ok, body = await _req("POST", "/create-phone-call", payload)
    return {"ok": ok, "response": body}
