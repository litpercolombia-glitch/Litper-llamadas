"""Provider-agnostic LLM router.

Providers are OpenAI-chat-compatible (Groq, Mistral, Cerebras, Anthropic via
Emergent) plus Gemini (native SDK). All share a single interface:

    async def call(system: str, messages: list[dict], model: str | None = None) -> str

Tier routing:
    tier="default"    → Groq  (fast, tool-calling, high-volume)
    tier="reasoning"  → Claude if configured else Gemini
Fallback chain (on network / rate-limit / auth failures):
    Groq → Gemini → Mistral → Cerebras

Model override: caller may pass provider="groq|gemini|mistral|cerebras|claude"
to bypass tier routing (used by the UI dropdown).
"""
from __future__ import annotations
import os
import logging
from typing import Any
import httpx

log = logging.getLogger("llm.router")


PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
        "compat": "openai",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-large-latest",
        "env_key": "MISTRAL_API_KEY",
        "compat": "openai",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "model": "llama-3.3-70b",
        "env_key": "CEREBRAS_API_KEY",
        "compat": "openai",
    },
    "gemini": {
        "base_url": None,
        "model": "gemini-2.0-flash-exp",
        "env_key": "GEMINI_API_KEY",
        "compat": "gemini",
    },
    "claude": {
        "base_url": None,
        "model": "claude-sonnet-4-6",
        "env_key": "ANTHROPIC_API_KEY",  # or EMERGENT_LLM_KEY (fallback)
        "compat": "emergent",
    },
}

FALLBACK_CHAIN = ["groq", "gemini", "mistral", "cerebras"]


def provider_key(name: str) -> str:
    """Return the API key for a provider. Falls back to EMERGENT_LLM_KEY for claude."""
    if name == "claude":
        return (os.environ.get("ANTHROPIC_API_KEY", "").strip()
                or os.environ.get("EMERGENT_LLM_KEY", "").strip())
    return os.environ.get(PROVIDERS[name]["env_key"], "").strip()


def provider_available(name: str) -> bool:
    return bool(provider_key(name))


def resolve(tier: str = "default", override: str | None = None) -> str:
    if override and override != "auto" and override in PROVIDERS:
        return override
    if tier == "reasoning":
        if provider_available("claude"):
            return "claude"
        if provider_available("gemini"):
            return "gemini"
    # default tier
    default = os.environ.get("LLM_DEFAULT", "groq").lower()
    if provider_available(default):
        return default
    for p in FALLBACK_CHAIN:
        if provider_available(p):
            return p
    return "groq"  # last resort


# ---------- OpenAI-compatible ----------
async def _call_openai_compat(provider: str, system: str,
                              messages: list[dict[str, str]]) -> str:
    p = PROVIDERS[provider]
    key = provider_key(provider)
    url = f"{p['base_url']}/chat/completions"
    payload = {
        "model": p["model"],
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": 0.4,
        "max_tokens": 1500,
    }
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.post(url, headers={"Authorization": f"Bearer {key}",
                                         "Content-Type": "application/json"},
                           json=payload)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"] or ""


# ---------- Gemini ----------
async def _call_gemini(system: str, messages: list[dict[str, str]]) -> str:
    key = provider_key("gemini")
    model = PROVIDERS["gemini"]["model"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    # Gemini expects contents=[{role,parts:[{text}]}]. System goes into systemInstruction.
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500},
    }
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.post(url, json=payload)
    r.raise_for_status()
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:  # noqa: BLE001
        return ""


# ---------- Claude via emergentintegrations ----------
async def _call_claude(system: str, messages: list[dict[str, str]],
                       session_id: str = "router") -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    api_key = provider_key("claude")
    chat = LlmChat(api_key=api_key, session_id=session_id,
                   system_message=system).with_model("anthropic", "claude-sonnet-4-6")
    # emergentintegrations doesn't take pre-built history — replay as one big user
    # message summarising context, followed by the latest user turn.
    ctx = "\n\n".join(f"[{m['role']}] {m['content']}" for m in messages[:-1])
    last = messages[-1]["content"] if messages else ""
    text = (f"CONTEXTO:\n{ctx}\n\n---\n\n{last}") if ctx else last
    reply = await chat.send_message(UserMessage(text=text))
    return reply if isinstance(reply, str) else str(reply)


# ---------- entry point ----------
async def call(system: str, messages: list[dict[str, str]], *,
               tier: str = "default", override: str | None = None,
               session_id: str = "router") -> tuple[str, str]:
    """Return (text, provider_used). Auto-fallbacks on error."""
    chosen = resolve(tier, override)
    tried: list[str] = []
    order = [chosen] + [p for p in FALLBACK_CHAIN if p != chosen]
    last_err = None
    for provider in order:
        if not provider_available(provider):
            continue
        tried.append(provider)
        try:
            compat = PROVIDERS[provider]["compat"]
            if compat == "openai":
                text = await _call_openai_compat(provider, system, messages)
            elif compat == "gemini":
                text = await _call_gemini(system, messages)
            elif compat == "emergent":
                text = await _call_claude(system, messages, session_id)
            else:
                continue
            return text, provider
        except Exception as e:  # noqa: BLE001
            log.warning("LLM provider %s failed: %s", provider, e)
            last_err = e
    raise RuntimeError(f"All LLM providers failed. Tried {tried}. Last error: {last_err}")


async def ping(provider: str) -> dict[str, Any]:
    """Cheap probe: send a 1-token 'ping' and return {ok, model, error?}."""
    if not provider_available(provider):
        return {"ok": False, "configured": False, "provider": provider,
                "error": "API key not configured"}
    try:
        text, _ = await call("Respond with the single word: pong",
                             [{"role": "user", "content": "ping"}],
                             override=provider)
        return {"ok": True, "configured": True, "provider": provider,
                "model": PROVIDERS[provider]["model"],
                "sample": (text or "").strip()[:40]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "configured": True, "provider": provider,
                "error": str(e)}
