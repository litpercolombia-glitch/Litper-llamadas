"""Token de webhooks POR CLIENTE (org).

Los proveedores (WhatsApp, Twilio, ElevenLabs, Retell) no envían sesión. Para
saber de qué cliente es un evento NO se deduce nada del cuerpo: cada cliente
tiene un token aleatorio que va en la URL que él mismo pega en el panel del
proveedor:

    POST /api/webhooks/{provider}/{org_token}
    POST /api/calls/webhook/{org_token}

Colección `org_webhook_tokens {org_id, token, created_at}` (únicos ambos).
El cliente ve sus URLs en GET /api/org/webhook-urls (autenticado).
"""
from __future__ import annotations
import os
import re
import secrets
from datetime import datetime, timezone

from db import get_db

PROVIDERS = ("chatea", "twilio", "elevenlabs")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{24,128}$")


def new_token() -> str:
    return secrets.token_urlsafe(32)


async def token_for(org_id: str) -> str:
    """Token del cliente; se genera y guarda la primera vez (idempotente)."""
    if not org_id:
        raise ValueError("org_id obligatorio")
    db = get_db()
    await db.org_webhook_tokens.update_one(
        {"org_id": org_id},
        {"$setOnInsert": {"org_id": org_id, "token": new_token(),
                          "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    doc = await db.org_webhook_tokens.find_one({"org_id": org_id}, {"_id": 0, "token": 1})
    return doc["token"]


async def rotate(org_id: str) -> str:
    """Invalida el token anterior (las URLs viejas dejan de funcionar)."""
    tok = new_token()
    await get_db().org_webhook_tokens.update_one(
        {"org_id": org_id},
        {"$set": {"org_id": org_id, "token": tok,
                  "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return tok


async def org_for_token(token: str | None) -> str | None:
    """Cliente dueño del token, o None (token mal formado o desconocido)."""
    if not token or not _TOKEN_RE.match(token):
        return None
    doc = await get_db().org_webhook_tokens.find_one({"token": token}, {"_id": 0, "org_id": 1})
    return (doc or {}).get("org_id") or None


def public_base(request=None) -> str:
    """URL pública del backend: PUBLIC_BASE_URL; si no, la de la petición
    (respetando X-Forwarded-Proto/Host del proxy)."""
    base = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base or request is None:
        return base
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host")
            or request.url.netloc).split(",")[0].strip()
    return f"{proto}://{host}"


def urls_for(base: str, token: str) -> dict[str, str]:
    """URLs listas para pegar en el panel de cada proveedor."""
    base = (base or "").rstrip("/")
    out = {p: f"{base}/api/webhooks/{p}/{token}" for p in PROVIDERS}
    out["retell"] = f"{base}/api/calls/webhook/{token}"
    return out
