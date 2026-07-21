"""Agent loop — LLM plans, tools execute, results feed back until final answer.

Uses emergentintegrations LlmChat with Claude Sonnet 4.6 (recommended).

Tool-call protocol: we ask the model to emit tool calls as JSON objects wrapped
in a ```tool``` fenced block, one call per block. Example:

```tool
{"name": "get_queue", "args": {"semaphore": "rojo", "limit": 20}}
```

The loop parses every such block from the assistant's message, executes the
tools, appends the results as a user message (```tool_result\n{...}```), then
calls the model again. Stops when the model returns a message with no tool
blocks OR max iterations reached.
"""
from __future__ import annotations
import json
import re
import logging
from typing import Any

from .router import call as llm_call, PROVIDERS
from .tools import execute, tools_prompt_block

log = logging.getLogger("agent")

TOOL_BLOCK_RE = re.compile(r"```tool\s*\n(.+?)\n```", re.DOTALL)

MAX_ITERATIONS = 6


SYSTEM_PROMPT = """Eres Marcus, el Copilot de Litper Connect Hub — un asistente
operativo que gestiona el call-center COD de Litper en LATAM (Colombia, Ecuador,
Chile). Hablas y respondes en español a menos que el usuario cambie de idioma.

Tu trabajo: ayudar a los operadores a revisar la cola de "llamadas a oficina",
programar cadencias, registrar resultados de llamadas, enviar WhatsApp por
Chatea Pro, crear tickets, y responder preguntas usando datos reales del Hub.

Tienes las siguientes HERRAMIENTAS. Cuando quieras usar una, escríbela como un
bloque fenced JSON del tipo `tool`, EXACTAMENTE con este formato:

```tool
{"name": "nombre_de_la_tool", "args": { ... }}
```

Puedes emitir varias tools en un mismo turno (una por bloque). Después de tu
mensaje ejecutaré cada tool y te devolveré los resultados como bloques
```tool_result``` para que continúes.

Reglas de uso:
- Antes de contestar sobre pedidos, cola, tickets o mensajes SIEMPRE llama la
  tool relevante para obtener datos reales. No inventes.
- Muestra números y días literalmente. Los "semáforos" son: rojo (≤1 día),
  amarillo (mitad del plazo), verde (más tiempo), gris (sin reclamo).
- Cuando el usuario pida acción (ej. "programa cadencias a los rojos"), usa
  get_queue primero, luego schedule_cadence por cada uno, y resume qué hiciste.
- Cuando envíes WhatsApp, redacta un mensaje cálido en español.
- Cuando termines, responde en Markdown claro y conciso. No repitas los JSON
  crudos; en su lugar, resume qué pasó.

HERRAMIENTAS DISPONIBLES:
"""


def _api_key() -> str:
    return "router"  # legacy placeholder; router handles keys per-provider


def _system_prompt(extra_system: str = "") -> str:
    system = SYSTEM_PROMPT + "\n" + tools_prompt_block()
    if extra_system:
        system += "\n\n--- Skill activada ---\n" + extra_system
    return system


def _parse_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for match in TOOL_BLOCK_RE.finditer(text or ""):
        raw = match.group(1).strip()
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and obj.get("name"):
                calls.append({"name": obj["name"], "args": obj.get("args") or {}})
        except Exception:  # noqa: BLE001
            log.warning("Failed to parse tool call block: %s", raw[:200])
    return calls


def _strip_tool_blocks(text: str) -> str:
    return TOOL_BLOCK_RE.sub("", text or "").strip()


async def run_agent(session_id: str, history: list[dict[str, str]],
                    user_text: str, *, skill_instructions: str = "",
                    max_iterations: int = MAX_ITERATIONS,
                    auto_mode: bool = False,
                    model_override: str | None = None) -> dict[str, Any]:
    """Run the agent loop for one user turn."""
    system = _system_prompt(skill_instructions)
    conv: list[dict[str, str]] = []
    for m in history[-10:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            conv.append({"role": m["role"], "content": m["content"]})

    if auto_mode:
        user_text = ("MODO AUTÓNOMO: ejecuta la petición completa con múltiples "
                     "herramientas si hace falta y reporta lo hecho.\n\n") + user_text

    conv.append({"role": "user", "content": user_text})
    steps: list[dict[str, Any]] = []
    provider_used = None

    for _ in range(max_iterations):
        try:
            tier = "reasoning" if (model_override in ("claude", "gemini")
                                   or "razona" in (skill_instructions or "").lower()) else "default"
            assistant_text, provider_used = await llm_call(
                system, conv, tier=tier, override=model_override,
                session_id=session_id)
        except Exception as e:  # noqa: BLE001
            return {"final_text": f"⚠️ Todos los proveedores LLM fallaron: {e}",
                    "steps": steps, "provider": None}

        calls = _parse_tool_calls(assistant_text)
        visible_text = _strip_tool_blocks(assistant_text)

        if not calls:
            steps.append({"assistant_text": visible_text or assistant_text,
                          "tool_calls": [], "provider": provider_used})
            return {"final_text": visible_text or assistant_text,
                    "steps": steps, "provider": provider_used}

        executed: list[dict[str, Any]] = []
        for c in calls:
            res = await execute(c["name"], c.get("args") or {})
            executed.append({"name": c["name"], "args": c.get("args") or {},
                             "result": res})
        steps.append({"assistant_text": visible_text, "tool_calls": executed,
                      "provider": provider_used})

        conv.append({"role": "assistant", "content": assistant_text})
        blocks = []
        for e in executed:
            payload = json.dumps({"name": e["name"], "result": e["result"]},
                                 ensure_ascii=False, default=str)
            if len(payload) > 6000:
                payload = payload[:6000] + "…(truncado)"
            blocks.append(f"```tool_result\n{payload}\n```")
        conv.append({"role": "user", "content": "\n\n".join(blocks)})

    return {"final_text": "Se alcanzó el máximo de iteraciones.",
            "steps": steps, "provider": provider_used}
