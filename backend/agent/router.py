"""Provider-agnostic LLM router (v2.1 — OpenRouter + BYOK por cliente).

Cambios v2 / v2.1 (objetivo #40, oct-2026):
  * OpenRouter es el proveedor PRINCIPAL. Una llave abre cientos de modelos;
    si el modelo principal falla, OpenRouter prueba los de `models=[...]`.
  * Las llaves se leen POR CLIENTE (org_id) desde `org_credentials`
    (cifradas). La llave de plataforma (.env) solo la usan los clientes
    permitidos en PLATFORM_KEYS_ORGS (ver org_credentials.platform_keys_allowed).
  * "claude" sin Emergent: API directa de Anthropic. emergentintegrations fuera.
  * Ningún secreto sale en errores ni logs: _safe_err() limpia todo.
  * Log por intento en la colección `llm_calls` (proveedor, modelo, tokens, ms).
  * ping() prueba SOLO el proveedor pedido (sin cascada): badge honesto.
"""
from __future__ import annotations

import os
import re
import time
import logging
from typing import Any

import httpx

log = logging.getLogger("llm.router")

# IDs de OpenRouter (verificar vigentes en https://openrouter.ai/models).
# Se pueden cambiar sin tocar código con variables de entorno, o por cliente
# en el campo "model" de su tarjeta OpenRouter.
OR_DEFAULT = os.environ.get("OPENROUTER_MODEL_DEFAULT", "google/gemini-2.5-flash")
OR_REASONING = os.environ.get("OPENROUTER_MODEL_REASONING", "anthropic/claude-sonnet-4.5")
OR_FALLBACK = [m.strip() for m in os.environ.get(
    "OPENROUTER_FALLBACK_MODELS",
    "openai/gpt-4o-mini,meta-llama/llama-3.3-70b-instruct").split(",") if m.strip()]

PROVIDERS: dict[str, dict[str, Any]] = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": OR_DEFAULT,
                   "env_key": "OPENROUTER_API_KEY", "compat": "openrouter"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile",
             "env_key": "GROQ_API_KEY", "compat": "openai"},
    "mistral": {"base_url": "https://api.mistral.ai/v1", "model": "mistral-large-latest",
                "env_key": "MISTRAL_API_KEY", "compat": "openai"},
    "cerebras": {"base_url": "https://api.cerebras.ai/v1", "model": "llama-3.3-70b",
                 "env_key": "CEREBRAS_API_KEY", "compat": "openai"},
    "gemini": {"base_url": None, "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
               "env_key": "GEMINI_API_KEY", "compat": "gemini"},
    "claude": {"base_url": "https://api.anthropic.com/v1",
               "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
               "env_key": "ANTHROPIC_API_KEY", "compat": "anthropic"},
}

# OpenRouter primero; los demás son respaldo si el cliente no tiene OpenRouter.
FALLBACK_CHAIN = ["openrouter", "groq", "gemini", "mistral", "cerebras", "claude"]


# ---------------------------------------------------------------- utilidades
_KEY_PATTERNS = re.compile(r"(sk-[A-Za-z0-9_\-]{6,}|gsk_[A-Za-z0-9]{6,}|AIza[0-9A-Za-z_\-]{10,}"
                           r"|csk-[A-Za-z0-9]{6,}|key=[^&\s]+)")


def _safe_err(e: Exception, secrets: list[str] | None = None) -> str:
    """Mensaje de error SIN secretos (ni URL con ?key=, ni la llave)."""
    if isinstance(e, httpx.HTTPStatusError):
        body = ""
        try:
            body = e.response.text[:200]
        except Exception:  # noqa: BLE001
            pass
        msg = f"HTTP {e.response.status_code}: {body}"
    else:
        msg = f"{type(e).__name__}: {e}"
    for s in secrets or []:
        if s:
            msg = msg.replace(s, "***")
    return _KEY_PATTERNS.sub("***", msg)[:400]


class ProviderError(RuntimeError):
    pass


async def _keys_for(org_id: str) -> dict[str, dict[str, str]]:
    """Credenciales efectivas por proveedor para este cliente. Nunca salen del backend."""
    from org_credentials import get_credentials, PROVIDER_SCHEMAS
    out: dict[str, dict[str, str]] = {}
    for name in PROVIDERS:
        if name not in PROVIDER_SCHEMAS:
            out[name] = {"api_key": ""}
            continue
        try:
            out[name] = await get_credentials(name, org_id)
        except Exception as e:  # noqa: BLE001 — sin llave, NUNCA caer al .env aquí
            log.warning("No pude leer credenciales %s/%s: %s", org_id, name, type(e).__name__)
            out[name] = {"api_key": ""}
    return out


def provider_available(name: str, keys: dict[str, dict[str, str]] | None = None) -> bool:
    if keys is not None:
        return bool((keys.get(name) or {}).get("api_key"))
    return bool(os.environ.get(PROVIDERS[name]["env_key"], "").strip())


def resolve(tier: str, override: str | None, keys: dict[str, dict[str, str]]) -> str:
    if override and override not in ("auto", "") and override in PROVIDERS:
        return override
    for p in FALLBACK_CHAIN:
        if provider_available(p, keys):
            return p
    return "openrouter"


# ---------------------------------------------------------------- llamadas
async def _post(url: str, *, headers: dict, json: dict) -> dict:
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.post(url, headers=headers, json=json)
    r.raise_for_status()
    return r.json()


async def _call_openrouter(system, messages, key, tier, model_override):
    primary = model_override or (OR_REASONING if tier == "reasoning" else OR_DEFAULT)
    models = [primary] + [m for m in OR_FALLBACK if m != primary]
    data = await _post("https://openrouter.ai/api/v1/chat/completions",
                       headers={"Authorization": f"Bearer {key}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": os.environ.get("APP_PUBLIC_URL", "https://app.zynexapp.com"),
                                "X-Title": "Zynex OS"},
                       json={"models": models[:3],
                             "messages": [{"role": "system", "content": system}, *messages],
                             "temperature": 0.4, "max_tokens": 1500})
    if data.get("error"):
        raise ProviderError(f"OpenRouter: {str(data['error'])[:200]}")
    return (data["choices"][0]["message"]["content"] or "",
            {"model": data.get("model", primary), "usage": data.get("usage", {})})


async def _call_openai_compat(provider, system, messages, key):
    p = PROVIDERS[provider]
    data = await _post(f"{p['base_url']}/chat/completions",
                       headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                       json={"model": p["model"],
                             "messages": [{"role": "system", "content": system}, *messages],
                             "temperature": 0.4, "max_tokens": 1500})
    return data["choices"][0]["message"]["content"] or "", {"model": p["model"], "usage": data.get("usage", {})}


async def _call_gemini(system, messages, key):
    model = PROVIDERS["gemini"]["model"]
    # La llave va en header (NO en la URL) para que nunca aparezca en errores.
    data = await _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                       headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                       json={"systemInstruction": {"parts": [{"text": system}]},
                             "contents": [{"role": "user" if m["role"] == "user" else "model",
                                           "parts": [{"text": m["content"]}]} for m in messages],
                             "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500}})
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"], {"model": model}
    except Exception:  # noqa: BLE001
        raise ProviderError("Gemini devolvió una respuesta vacía")


async def _call_anthropic(system, messages, key):
    """Claude por API directa (sin Emergent)."""
    model = PROVIDERS["claude"]["model"]
    data = await _post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                "content-type": "application/json"},
                       json={"model": model, "system": system, "max_tokens": 1500, "temperature": 0.4,
                             "messages": [m for m in messages if m["role"] in ("user", "assistant")]})
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return text, {"model": model, "usage": data.get("usage", {})}


async def _call_one(provider, keys, system, messages, tier, model_override):
    key = (keys.get(provider) or {}).get("api_key", "")
    compat = PROVIDERS[provider]["compat"]
    if compat == "openrouter":
        cust_model = (keys.get("openrouter") or {}).get("model") or None
        return await _call_openrouter(system, messages, key, tier, model_override or cust_model)
    if compat == "openai":
        return await _call_openai_compat(provider, system, messages, key)
    if compat == "gemini":
        return await _call_gemini(system, messages, key)
    if compat == "anthropic":
        return await _call_anthropic(system, messages, key)
    raise ProviderError(f"compat desconocido: {compat}")


async def _log_call(org_id, session_id, provider, model, usage, ms, error):
    try:
        from db import get_db
        from datetime import datetime, timezone
        await get_db().llm_calls.insert_one({
            "org_id": org_id, "session_id": session_id, "provider": provider,
            "model": model, "usage": usage or {}, "ms": ms, "ok": error is None,
            "error": error or "", "created_at": datetime.now(timezone.utc).isoformat()})
    except Exception:  # noqa: BLE001 — el log nunca tumba la respuesta
        pass


# ---------------------------------------------------------------- entrada
NO_AI_MSG = ("No hay IA conectada. Ve a Conexiones > Credenciales y pega tu llave de "
             "OpenRouter (openrouter.ai/keys).")


async def call(system: str, messages: list[dict[str, str]], *,
               tier: str = "default", override: str | None = None,
               session_id: str = "router", org_id: str = "default",
               model_override: str | None = None) -> tuple[str, str]:
    """Devuelve (texto, proveedor_usado). Cascada automática entre proveedores."""
    keys = await _keys_for(org_id)
    chosen = resolve(tier, override, keys)
    order = [chosen] + [p for p in FALLBACK_CHAIN if p != chosen]
    secrets = [v.get("api_key", "") for v in keys.values()]
    tried: list[str] = []
    last_err = ""
    for provider in order:
        if not provider_available(provider, keys):
            continue
        tried.append(provider)
        t0 = time.monotonic()
        try:
            text, meta = await _call_one(provider, keys, system, messages, tier, model_override)
            await _log_call(org_id, session_id, provider, meta.get("model"), meta.get("usage"),
                            int((time.monotonic() - t0) * 1000), None)
            return text, provider
        except Exception as e:  # noqa: BLE001
            last_err = _safe_err(e, secrets)
            log.warning("LLM %s falló (org=%s): %s", provider, org_id, last_err)
            await _log_call(org_id, session_id, provider, PROVIDERS[provider]["model"], None,
                            int((time.monotonic() - t0) * 1000), last_err)
    if not tried:
        raise RuntimeError(NO_AI_MSG)
    raise RuntimeError(f"Todos los proveedores LLM fallaron. Intentados {tried}. Último error: {last_err}")


async def ping(provider: str, org_id: str = "default") -> dict[str, Any]:
    """Prueba REAL solo del proveedor pedido, con la llave de ESTE cliente (sin cascada)."""
    if provider not in PROVIDERS:
        return {"ok": False, "configured": False, "provider": provider, "error": "Proveedor desconocido"}
    keys = await _keys_for(org_id)
    if not provider_available(provider, keys):
        return {"ok": False, "configured": False, "provider": provider, "error": "Llave no configurada"}
    secrets = [v.get("api_key", "") for v in keys.values()]
    t0 = time.monotonic()
    try:
        text, meta = await _call_one(provider, keys, "Responde solo: pong",
                                     [{"role": "user", "content": "ping"}], "default", None)
        await _log_call(org_id, "ping", provider, meta.get("model"), meta.get("usage"),
                        int((time.monotonic() - t0) * 1000), None)
        return {"ok": True, "configured": True, "provider": provider,
                "model": meta.get("model"), "sample": (text or "").strip()[:40]}
    except Exception as e:  # noqa: BLE001
        err = _safe_err(e, secrets)
        await _log_call(org_id, "ping", provider, PROVIDERS[provider]["model"], None,
                        int((time.monotonic() - t0) * 1000), err)
        return {"ok": False, "configured": True, "provider": provider, "error": err}
