"""
Multi-tenant credentials store — encrypted at rest with Fernet (AES-128-CBC + HMAC).

Each org owns its own set of provider keys (Chatea, Telnyx, ElevenLabs, LLMs).
Secrets are encrypted using ENCRYPTION_KEY from backend/.env. The frontend
NEVER receives the plaintext — only status ("connected"/"not_configured") and a
short masked hint like "sk_…9f2c".

Design:
- Collection `org_credentials`: { org_id, provider, is_configured, hint,
                                  ciphertext (encrypted JSON dict), updated_at }
- Every logged-in operator implicitly belongs to org_id = "default" (single-tenant
  behaviour today); multi-tenant will attach org_id to the operator token later.
- Provider fallback resolution: if the org has no entry for a provider, we fall
  back to `os.environ` so demo mode keeps working.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken

from db import get_db

DEFAULT_ORG = "default"

# Providers supported. Each maps a canonical set of fields (in plaintext form)
# to their expected shape. `frontend_fields` describes which fields the UI
# should show as inputs (booleans -> checkboxes not implemented; treat all as
# strings). `env_map` gives the corresponding backend .env var (for fallback).
PROVIDER_SCHEMAS: dict[str, dict[str, dict[str, str]]] = {
    "chatea_pro": {
        "api_key":  {"env": "CHATEA_PRO_API_KEY",  "label": "API Token"},
        "base_url": {"env": "CHATEA_PRO_BASE_URL", "label": "Base URL"},
    },
    "telnyx": {
        "api_key":       {"env": "TELNYX_API_KEY",      "label": "API Key"},
        "connection_id": {"env": "TELNYX_CONNECTION_ID","label": "Connection ID"},
        "phone_number":  {"env": "TELNYX_PHONE_NUMBER", "label": "Número E.164"},
        "sip_username":  {"env": "TELNYX_SIP_USERNAME", "label": "SIP username"},
        "sip_password":  {"env": "TELNYX_SIP_PASSWORD", "label": "SIP password"},
        "sip_domain":    {"env": "TELNYX_SIP_DOMAIN",   "label": "SIP domain"},
    },
    "elevenlabs": {
        "api_key":          {"env": "ELEVENLABS_API_KEY",         "label": "API Key"},
        "agent_id":         {"env": "ELEVENLABS_AGENT_ID",        "label": "Agent ID"},
        "default_voice_id": {"env": "ELEVENLABS_DEFAULT_VOICE_ID","label": "Voice ID por defecto"},
    },
    "groq":     {"api_key": {"env": "GROQ_API_KEY",     "label": "API Key"}},
    "gemini":   {"api_key": {"env": "GEMINI_API_KEY",   "label": "API Key"}},
    "mistral":  {"api_key": {"env": "MISTRAL_API_KEY",  "label": "API Key"}},
    "cerebras": {"api_key": {"env": "CEREBRAS_API_KEY", "label": "API Key"}},
    "claude":   {"api_key": {"env": "ANTHROPIC_API_KEY","label": "API Key"}},
    "twilio": {
        "account_sid": {"env": "TWILIO_ACCOUNT_SID", "label": "Account SID"},
        "auth_token":  {"env": "TWILIO_AUTH_TOKEN",  "label": "Auth Token"},
    },
}

_SECRET_FIELDS = {"api_key", "auth_token", "sip_password", "connection_id"}


def _fernet() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("ENCRYPTION_KEY no configurada en backend/.env")
    return Fernet(key.encode())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask(value: str) -> str:
    if not value:
        return ""
    v = str(value)
    if len(v) <= 6:
        return "…" + v[-2:]
    return v[:4] + "…" + v[-4:]


# ---------------------------------------------------------------------------
# Public API — used by both /config routes AND by every provider client.
# ---------------------------------------------------------------------------
async def get_credentials(provider: str, org_id: str = DEFAULT_ORG) -> dict[str, str]:
    """Return the effective plaintext credentials for a provider.

    Precedence: org-stored value → backend/.env fallback → empty string.
    NEVER expose the returned dict outside the backend."""
    if provider not in PROVIDER_SCHEMAS:
        raise ValueError(f"unknown provider: {provider}")
    schema = PROVIDER_SCHEMAS[provider]
    out = {f: "" for f in schema}

    # Load org record
    db = get_db()
    doc = await db.org_credentials.find_one(
        {"org_id": org_id, "provider": provider}, {"_id": 0})
    if doc and doc.get("ciphertext"):
        try:
            data = json.loads(_fernet().decrypt(doc["ciphertext"].encode()).decode())
            for k, v in data.items():
                if k in schema and v:
                    out[k] = str(v)
        except (InvalidToken, ValueError):
            # bad ciphertext — treat as empty; fall back to env
            pass

    # Fill remaining fields from env
    for field, spec in schema.items():
        if out[field]:
            continue
        env_val = os.environ.get(spec.get("env", ""), "").strip()
        if env_val:
            out[field] = env_val
    return out


async def set_credentials(provider: str, values: dict[str, str],
                          org_id: str = DEFAULT_ORG) -> dict[str, Any]:
    """Encrypt + upsert the provider credentials for an org.

    Empty-string values are treated as "clear this field"."""
    if provider not in PROVIDER_SCHEMAS:
        raise ValueError(f"unknown provider: {provider}")
    schema = PROVIDER_SCHEMAS[provider]
    filtered = {k: str(v) for k, v in values.items() if k in schema}

    # Merge with the existing decrypted values so we can PATCH partial changes.
    db = get_db()
    existing = await db.org_credentials.find_one(
        {"org_id": org_id, "provider": provider}, {"_id": 0})
    current: dict[str, str] = {}
    if existing and existing.get("ciphertext"):
        try:
            current = json.loads(
                _fernet().decrypt(existing["ciphertext"].encode()).decode())
        except InvalidToken:
            current = {}
    current.update(filtered)
    # Remove empty strings so status accurately reflects what's set
    current = {k: v for k, v in current.items() if v}

    ciphertext = _fernet().encrypt(json.dumps(current).encode()).decode()
    hint = ""
    for f in ("api_key", "auth_token", "sip_password", "token"):
        if current.get(f):
            hint = _mask(current[f])
            break
    doc = {
        "org_id": org_id,
        "provider": provider,
        "is_configured": bool(current),
        "hint": hint,
        "ciphertext": ciphertext,
        "updated_at": _now_iso(),
    }
    await db.org_credentials.update_one(
        {"org_id": org_id, "provider": provider},
        {"$set": doc}, upsert=True)
    return {"provider": provider, "is_configured": doc["is_configured"],
            "hint": hint, "updated_at": doc["updated_at"]}


async def status(org_id: str = DEFAULT_ORG) -> list[dict[str, Any]]:
    """Return the (non-sensitive) status of every provider for an org."""
    db = get_db()
    stored = {d["provider"]: d async for d in db.org_credentials.find(
        {"org_id": org_id}, {"_id": 0}) }
    out = []
    for provider, schema in PROVIDER_SCHEMAS.items():
        doc = stored.get(provider)
        creds = await get_credentials(provider, org_id)
        # Configured = at least one field has a value (from org OR env)
        configured = any(creds.values())
        # Origin: org > env > none
        if doc and doc.get("is_configured"):
            origin = "org"
        elif configured:
            origin = "env"
        else:
            origin = "none"
        hint = (doc or {}).get("hint") or ""
        if not hint and configured:
            for f in ("api_key", "auth_token", "sip_password"):
                if creds.get(f):
                    hint = _mask(creds[f]); break
        out.append({
            "provider": provider,
            "fields": [
                {"name": f, "label": s["label"], "is_secret": f in _SECRET_FIELDS,
                 "has_value": bool(creds.get(f))}
                for f, s in schema.items()
            ],
            "configured": configured,
            "origin": origin,   # 'org' | 'env' | 'none'
            "hint": hint,
            "updated_at": (doc or {}).get("updated_at"),
        })
    return out


async def clear(provider: str, org_id: str = DEFAULT_ORG) -> None:
    await get_db().org_credentials.delete_one({"org_id": org_id, "provider": provider})
