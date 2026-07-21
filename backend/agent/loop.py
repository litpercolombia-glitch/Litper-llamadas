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
import os
import re
import logging
from typing import Any
from emergentintegrations.llm.chat import LlmChat, UserMessage

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
    key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not key:
        # Optional fallback env keys
        for fallback in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            v = os.environ.get(fallback)
            if v:
                return v
    return key


def _new_chat(session_id: str, extra_system: str = "") -> LlmChat:
    system = SYSTEM_PROMPT + "\n" + tools_prompt_block()
    if extra_system:
        system += "\n\n--- Skill activada ---\n" + extra_system
    return LlmChat(
        api_key=_api_key(),
        session_id=session_id,
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")


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
                    auto_mode: bool = False) -> dict[str, Any]:
    """Run the agent loop for one user turn.

    Returns dict:
      { 'final_text': str,
        'steps': [{ 'assistant_text': str,
                    'tool_calls': [{name, args, result}] }, ...] }
    """
    if not _api_key():
        return {"final_text": "⚠️ No hay LLM key configurada. Añade EMERGENT_LLM_KEY o "
                              "ANTHROPIC_API_KEY en backend/.env y reinicia.",
                "steps": []}

    chat = _new_chat(session_id, extra_system=skill_instructions)

    # Replay history so the LLM has context
    for m in history:
        role = m.get("role")
        content = m.get("content") or ""
        if role and content and role in ("user", "assistant"):
            # emergentintegrations manages this via session_id when we use send_message
            # sequentially; but since we're creating a fresh chat, we prepend history
            # by sending it as a compact context block.
            pass

    context_prefix = ""
    if history:
        joined = "\n\n".join(
            f"[{m['role']}] {m['content']}" for m in history[-8:]
            if m.get("role") in ("user", "assistant") and m.get("content")
        )
        if joined:
            context_prefix = f"CONTEXTO PREVIO (resumen breve):\n{joined}\n\n---\n\n"

    if auto_mode:
        context_prefix += ("MODO AUTÓNOMO ACTIVADO: ejecuta la petición completa con "
                           "múltiples herramientas si hace falta y reporta lo hecho.\n\n")

    current_user_text = context_prefix + user_text
    steps: list[dict[str, Any]] = []

    for i in range(max_iterations):
        reply = await chat.send_message(UserMessage(text=current_user_text))
        assistant_text = reply if isinstance(reply, str) else str(reply)

        calls = _parse_tool_calls(assistant_text)
        visible_text = _strip_tool_blocks(assistant_text)

        if not calls:
            # Final answer.
            steps.append({"assistant_text": visible_text or assistant_text,
                          "tool_calls": []})
            return {"final_text": visible_text or assistant_text, "steps": steps}

        # Execute each tool and collect the results
        executed: list[dict[str, Any]] = []
        for c in calls:
            res = await execute(c["name"], c.get("args") or {})
            executed.append({"name": c["name"], "args": c.get("args") or {},
                             "result": res})

        steps.append({"assistant_text": visible_text, "tool_calls": executed})

        # Build tool_result blocks to feed back
        blocks = []
        for e in executed:
            payload = json.dumps({"name": e["name"], "result": e["result"]},
                                 ensure_ascii=False, default=str)
            # Truncate huge results
            if len(payload) > 6000:
                payload = payload[:6000] + "…(truncado)"
            blocks.append(f"```tool_result\n{payload}\n```")
        current_user_text = "\n\n".join(blocks)

    # If we hit the iteration cap
    return {"final_text": "Se alcanzó el máximo de iteraciones. Aquí lo que hice hasta ahora.",
            "steps": steps}
