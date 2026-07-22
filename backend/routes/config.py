"""Routes: /config — per-organization provider credentials.

Frontend only sees NON-SENSITIVE status. Plaintext values only flow in from
the user (PUT /config/credentials/{provider}) and out to internal clients
(via org_credentials.get_credentials()). Never returned by any endpoint.
"""
from __future__ import annotations

import os
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import require_api_key
from org_credentials import (
    PROVIDER_SCHEMAS, get_credentials, set_credentials, status, clear,
    DEFAULT_ORG,
)

router = APIRouter(prefix="/config", tags=["config"],
                   dependencies=[Depends(require_api_key)])


def _org_id(request: Request) -> str:
    # Multi-tenant hook: read X-Org-Id header; default to "default" for now.
    return (request.headers.get("X-Org-Id") or DEFAULT_ORG).strip() or DEFAULT_ORG


class CredentialsIn(BaseModel):
    values: dict[str, str]


@router.get("/providers",
            summary="List the schema of every provider we support (field names, labels, secret flags).")
async def list_providers():
    return {
        "providers": [
            {"provider": p, "fields": [
                {"name": f, "label": s["label"], "env": s.get("env"),
                 "is_secret": f in {"api_key", "auth_token", "sip_password", "connection_id"}}
                for f, s in schema.items()
            ]} for p, schema in PROVIDER_SCHEMAS.items()
        ],
    }


@router.get("/credentials",
            summary="Per-org status of every provider (NEVER returns plaintext).")
async def credentials_status(request: Request):
    return {"org_id": _org_id(request), "providers": await status(_org_id(request))}


@router.put("/credentials/{provider}",
            summary="Upsert (encrypted) credentials for a provider.")
async def upsert_credentials(provider: str, payload: CredentialsIn, request: Request):
    if provider not in PROVIDER_SCHEMAS:
        raise HTTPException(400, f"provider desconocido: {provider}")
    try:
        return await set_credentials(provider, payload.values, _org_id(request))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.delete("/credentials/{provider}",
               summary="Remove ALL stored credentials for the given provider (does NOT touch env fallback).")
async def delete_credentials(provider: str, request: Request):
    if provider not in PROVIDER_SCHEMAS:
        raise HTTPException(400, f"provider desconocido: {provider}")
    await clear(provider, _org_id(request))
    return {"ok": True}


@router.post("/credentials/{provider}/test",
             summary="Live health-check for a provider using the effective credentials "
                     "(org > env fallback). Returns { ok, detail } — never leaks secrets.")
async def test_credentials(provider: str, request: Request):
    org_id = _org_id(request)
    creds = await get_credentials(provider, org_id)

    if provider == "chatea_pro":
        from chatea import ChateaClient
        c = ChateaClient(base_url=creds.get("base_url") or None,
                         api_key=creds.get("api_key") or None)
        if not c.configured:
            return {"ok": False, "detail": "API key vacía."}
        r = await c.health()
        return {"ok": r.get("ok"), "detail": r.get("body") or r.get("error"),
                "status_code": r.get("status_code")}

    if provider == "elevenlabs":
        import httpx
        api_key = creds.get("api_key") or ""
        if not api_key:
            return {"ok": False, "detail": "API key vacía."}
        try:
            async with httpx.AsyncClient(timeout=10) as x:
                r = await x.get("https://api.elevenlabs.io/v1/voices",
                                headers={"xi-api-key": api_key})
                if r.status_code == 200:
                    voices = (r.json() or {}).get("voices") or []
                    return {"ok": True, "detail": f"{len(voices)} voces detectadas"}
                return {"ok": False, "detail": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    if provider == "telnyx":
        import httpx
        api_key = creds.get("api_key") or ""
        if not api_key:
            return {"ok": False, "detail": "API key vacía."}
        try:
            async with httpx.AsyncClient(timeout=10) as x:
                r = await x.get("https://api.telnyx.com/v2/phone_numbers",
                                headers={"Authorization": f"Bearer {api_key}"},
                                params={"page[size]": 1})
                if r.status_code < 400:
                    return {"ok": True, "detail": "auth OK"}
                return {"ok": False, "detail": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    if provider in {"groq", "gemini", "mistral", "cerebras", "claude"}:
        api_key = creds.get("api_key") or ""
        if not api_key:
            return {"ok": False, "detail": "API key vacía."}
        # Round-trip through the LLM router (routes/llm has a ping)
        from agent.router import ping_provider
        try:
            r = await ping_provider(provider)
            return {"ok": bool(r.get("ok")), "detail": r.get("detail") or r.get("error")}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    if provider == "twilio":
        sid = creds.get("account_sid") or ""
        tok = creds.get("auth_token") or ""
        if not sid or not tok:
            return {"ok": False, "detail": "Falta account_sid o auth_token."}
        return {"ok": True, "detail": "Credenciales presentes (no se hizo llamada externa)."}

    return {"ok": False, "detail": "Test no implementado para este provider."}


# ---------------------------------------------------------------------------
# Onboarding progress — helper for the guided wizard.
# ---------------------------------------------------------------------------
REQUIRED_TO_OPERATE = ["chatea_pro"]      # must have at least these to send WA
LLM_PROVIDERS       = ["groq", "gemini", "mistral", "cerebras", "claude"]

_ONBOARDING_STEPS = [
    {"key": "chatea_pro", "label": "Chatea Pro · WhatsApp",
     "doc": "https://chateapro.app/settings#/api",
     "instructions": "Entra a chateapro.app → Configuración → API tokens y crea uno."},
    {"key": "elevenlabs", "label": "ElevenLabs · Voz IA",
     "doc": "https://elevenlabs.io/app/settings/api-keys",
     "instructions": "API Key con permisos ConvAI + TTS. Voice ID desde Voice Lab."},
    {"key": "telnyx", "label": "Telnyx · SIP",
     "doc": "https://portal.telnyx.com",
     "instructions": "Compra un número CO/EC/CL, crea una Voice/SIP Connection y guarda API Key + Connection ID."},
    {"key": "dropi", "label": "Dropi · Fuente de pedidos",
     "doc": "https://dropi.co/",
     "instructions": "No necesita llave — solo exporta 'Reclamos en Oficina' desde tu panel Dropi."},
    {"key": "llm", "label": "Motor de IA (Groq / Gemini / Claude / Mistral / Cerebras)",
     "doc": "https://console.groq.com/keys",
     "instructions": "Con uno basta. Groq es gratis y muy rápido — ideal para empezar."},
]


@router.get("/onboarding",
            summary="Return the guided wizard state: steps, per-step status, and whether the org "
                    "has the MINIMUM connections to start operating (Chatea Pro + 1 LLM).")
async def onboarding_state(request: Request):
    org_id = _org_id(request)
    prov_status = await status(org_id)
    by_provider = {p["provider"]: p for p in prov_status}

    def _connected(prov: str) -> bool:
        p = by_provider.get(prov)
        return bool(p and p.get("configured"))

    steps_out = []
    for s in _ONBOARDING_STEPS:
        key = s["key"]
        if key == "dropi":
            connected = True   # file-based
        elif key == "llm":
            connected = any(_connected(p) for p in LLM_PROVIDERS)
        else:
            connected = _connected(key)
        steps_out.append({**s, "connected": connected})

    connected_count = sum(1 for s in steps_out if s["connected"])
    minimum_ok = _connected("chatea_pro") and any(_connected(p) for p in LLM_PROVIDERS)

    return {
        "org_id":         org_id,
        "steps":          steps_out,
        "connected":      connected_count,
        "total":          len(steps_out),
        "minimum_ok":     minimum_ok,
        "ready_message":  ("Todo listo — ya puedes operar." if minimum_ok
                           else "Conecta Chatea Pro + un motor de IA para empezar."),
    }
