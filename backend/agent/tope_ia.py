"""Tope diario de la IA incluida (llave de la plataforma).

Una cuenta nueva puede usar el asistente sin pegar llave si el servidor lo
permite (PLATFORM_KEYS_ORGS). Para que eso no se vuelva un gasto sin control,
cada cuenta SIN llave propia tiene un tope de respuestas por día
(PLATFORM_AI_DAILY_CALLS, por defecto 60). Con llave propia no hay tope: paga
el cliente. Al llegar al tope se le dice claro qué hacer.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from db import get_db

TOPE_MSG = ("Llegaste al tope de hoy de la IA incluida en tu plan. Mañana se renueva; para seguir ahora, "
            "conecta tu propia llave en Conexiones > Credenciales.")


def tope_diario() -> int:
    try:
        return max(0, int(os.environ.get("PLATFORM_AI_DAILY_CALLS", "60")))
    except ValueError:
        return 60


async def tiene_llave_propia(org_id: str) -> bool:
    from agent.router import FALLBACK_CHAIN
    from org_credentials import PROVIDER_SCHEMAS, get_credentials
    for p in FALLBACK_CHAIN:
        if p not in PROVIDER_SCHEMAS:
            continue
        try:
            if (await get_credentials(p, org_id, allow_env=False)).get("api_key"):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def en_tope(org_id: str) -> bool:
    """True si la cuenta usa la llave de la plataforma y ya gastó su día."""
    from org_credentials import platform_keys_allowed
    if not platform_keys_allowed(org_id) or await tiene_llave_propia(org_id):
        return False
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
    usadas = await get_db().llm_calls.count_documents({"org_id": org_id, "ok": True, "created_at": {"$gte": hoy}})
    return usadas >= tope_diario()


def envolver(llamar):
    """Devuelve la misma función de IA, pero revisando antes el tope de la cuenta."""
    async def con_tope(system, messages, **kw):
        if await en_tope(kw.get("org_id") or "default"):
            return TOPE_MSG, None      # respuesta clara, sin gastar
        return await llamar(system, messages, **kw)
    con_tope.__wrapped__ = llamar
    return con_tope
