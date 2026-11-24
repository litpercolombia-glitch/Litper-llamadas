"""Retell integration — creates/updates a voice agent so the custom agents
built through the wizard can actually receive real calls.

BYOK POR CLIENTE: la llave se lee con org_credentials.get_credentials("retell",
org_id) (respeta PLATFORM_KEYS_ORGS). Un cliente sin llave propia y sin permiso
de plataforma NO usa la del servidor: recibe NOT_CONNECTED. LLM engine is
HARDCODED to Claude Haiku @ temp 0.3 — NEVER a reasoning model (introduces
dead air on the call). This is independent from Lyan (the internal copilot).
"""
from __future__ import annotations
import logging
import httpx

log = logging.getLogger("retell")

RETELL_BASE = "https://api.retellai.com"
LLM_MODEL   = "claude-haiku-4-5"   # explicit — NO reasoning models
LLM_TEMP    = 0.3

NOT_CONNECTED = "Conecta tu cuenta de Retell (telefonía) en Conexiones."


async def api_key(org_id: str) -> str | None:
    """Llave de Retell de ESTE cliente (o None)."""
    from org_credentials import get_credentials
    try:
        v = ((await get_credentials("retell", org_id)).get("api_key") or "").strip()
    except Exception as e:  # noqa: BLE001
        log.warning("No pude leer credenciales retell/%s: %s", org_id, type(e).__name__)
        v = ""
    return v or None


async def configured(org_id: str) -> bool:
    return (await api_key(org_id)) is not None


async def _req(org_id: str, method: str, path: str, json: dict | None = None) -> tuple[bool, dict]:
    key = await api_key(org_id)
    if not key:
        return False, {"error": NOT_CONNECTED}
    try:
        async with httpx.AsyncClient(timeout=15) as x:
            r = await x.request(
                method, f"{RETELL_BASE}{path}",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json=json,
            )
        ok = r.status_code < 400
        try:    body = r.json()
        except Exception: body = {"raw": r.text[:400]}
        return ok, body
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}".replace(key, "***")[:300]
        log.warning("retell %s %s failed: %s", method, path, err)
        return False, {"error": err}


# ======================================================================
# ARMADO DE PAYLOADS — funciones PURAS (sin red ni base de datos), con pruebas
# en tests/test_ronda2.py.
#
# FORMATO PENDIENTE DE VERIFICAR CONTRA LA API DE RETELL. No tenemos una cuenta
# de Retell en este entorno, así que los nombres de campo siguen la
# documentación pública tal como la entendemos (herramientas "custom" con
# `url`/`parameters`, `retell_llm_dynamic_variables` en create-phone-call,
# `webhook_url` en el agente). En Retell real el LLM y sus herramientas pueden
# vivir en un recurso aparte ("retell-llm" + `response_engine`); si la API
# rechaza el bloque `llm` en línea, lo único que hay que tocar son estas
# funciones. Hasta probarlo con una cuenta real, tratar esto como NO verificado.
# ======================================================================
AGENT_TOKEN_HEADER = "X-Agent-Token"

_OBJ = {"type": "object", "properties": {}}

# Herramientas nativas de llamada (las atiende routes/agent_tools.py).
CALL_TOOL_SPECS: dict[str, dict] = {
    "consultar_disponibilidad": {
        "description": "Devuelve próximos horarios laborales (no hay calendario conectado). "
                       "Úsala para proponer fechas; nunca calcules fechas tú.",
        "parameters": {"type": "object", "properties": {
            "duracion_min": {"type": "integer"}, "n": {"type": "integer"}}},
    },
    "proximo_horario_disponible": {
        "description": "Devuelve el próximo horario laboral disponible.",
        "parameters": _OBJ,
    },
    "reagendar_entrega": {
        "description": "Registra una nueva fecha acordada con el cliente y deja una tarea al equipo.",
        "parameters": {"type": "object", "required": ["pedido_id", "nueva_fecha_iso"], "properties": {
            "pedido_id": {"type": "string"}, "nueva_fecha_iso": {"type": "string"},
            "telefono": {"type": "string"}}},
    },
    "confirmar_pedido": {
        "description": "Marca el pedido/cita como confirmado por el cliente.",
        "parameters": {"type": "object", "required": ["pedido_id"], "properties": {
            "pedido_id": {"type": "string"}, "direccion": {"type": "string"},
            "franja": {"type": "string"}}},
    },
    "enviar_whatsapp": {
        "description": "Envía un WhatsApp al cliente de ESTA llamada o pedido (no a otros "
                       "números) con la cuenta conectada del negocio.",
        "parameters": {"type": "object", "properties": {
            "pedido_id": {"type": "string"}, "mensaje": {"type": "string"},
            "plantilla": {"type": "string"}, "telefono": {"type": "string"}}},
    },
    "transferir_a_humano": {
        "description": "Pide que una persona del equipo contacte al cliente (deja una tarea; "
                       "la transferencia en vivo aún no está disponible).",
        "parameters": {"type": "object", "required": ["telefono"], "properties": {
            "telefono": {"type": "string"}, "razon": {"type": "string"}}},
    },
    "registrar_promesa_pago": {
        "description": "Registra que el cliente prometió pagar en una fecha (queda para revisión humana).",
        "parameters": {"type": "object", "required": ["pedido_id", "fecha_iso"], "properties": {
            "pedido_id": {"type": "string"}, "fecha_iso": {"type": "string"},
            "monto": {"type": "number"}}},
    },
    "enviar_link_pago": {
        "description": "Envía un link de pago (todavía no disponible).",
        "parameters": {"type": "object", "required": ["telefono", "pedido_id", "monto"], "properties": {
            "telefono": {"type": "string"}, "pedido_id": {"type": "string"},
            "monto": {"type": "number"}}},
    },
    "crear_tarea": {
        "description": "Crea una tarea de seguimiento para el equipo humano.",
        "parameters": {"type": "object", "required": ["descripcion"], "properties": {
            "descripcion": {"type": "string"}, "tipo": {"type": "string"},
            "pedido_id": {"type": "string"}, "prioridad": {"type": "string"}}},
    },
    "registrar_resultado": {
        "description": "Registra el resultado de la llamada.",
        "parameters": {"type": "object", "required": ["outcome"], "properties": {
            "outcome": {"type": "string"}, "pedido_id": {"type": "string"},
            "telefono": {"type": "string"}, "notas": {"type": "string"},
            "fecha": {"type": "string"}}},
    },
}

# Nombres antiguos guardados en agentes viejos → herramienta vigente.
TOOL_ALIASES = {"reagendar": "reagendar_entrega", "registrar_pago": "registrar_promesa_pago",
                "crear_ticket": "crear_tarea", "transferir_humano": "transferir_a_humano"}
END_CALL_NAMES = {"terminar_llamada", "end_call"}


def _fn_name(name: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(name))[:64]


def build_custom_tools(agent_tools: list | None, mcp_tools: list[dict] | None,
                       base_url: str, agent_token: str) -> list[dict]:
    """Herramientas del agente como funciones personalizadas de Retell que
    apuntan a NUESTRO backend (`/api/agent-tools/...`) con el token del agente.

    * `agent_tools`: nombres guardados en el agente (nativas, alias o `mcp__…`).
    * `mcp_tools`: herramientas MCP ACTIVAS del cliente ({full_name, description,
      input_schema, requires_confirm}); solo se envían las que el agente lleva y
      que NO exigen confirmación humana (en una llamada no hay quién confirme).
    Sin `base_url` o sin token no se puede llamar de vuelta → lista vacía."""
    base = (base_url or "").rstrip("/")
    if not base or not agent_token:
        return []
    headers = {AGENT_TOKEN_HEADER: agent_token}
    wanted = [TOOL_ALIASES.get(str(n), str(n)) for n in (agent_tools or [])]
    out: list[dict] = []
    seen: set[str] = set()
    for name in wanted:
        if name in seen:
            continue
        seen.add(name)
        if name in END_CALL_NAMES:
            out.append({"type": "end_call", "name": "end_call",
                        "description": "Termina la llamada cuando la conversación acabó."})
            continue
        spec = CALL_TOOL_SPECS.get(name)
        if spec:
            out.append({"type": "custom", "name": name, "description": spec["description"],
                        "url": f"{base}/api/agent-tools/{name}", "method": "POST",
                        "headers": dict(headers), "parameters": spec["parameters"],
                        "speak_during_execution": False, "timeout_ms": 15000})
    by_name = {t.get("full_name"): t for t in (mcp_tools or []) if t.get("full_name")}
    for name in wanted:
        t = by_name.get(name)
        if not t or t.get("requires_confirm") or f"mcp:{name}" in seen:
            continue
        seen.add(f"mcp:{name}")
        schema = t.get("input_schema") if isinstance(t.get("input_schema"), dict) else None
        out.append({"type": "custom", "name": _fn_name(name),
                    "description": " ".join(str(t.get("description") or name).split())[:400],
                    "url": f"{base}/api/agent-tools/mcp/{name}", "method": "POST",
                    "headers": dict(headers), "parameters": schema or _OBJ,
                    "speak_during_execution": True, "timeout_ms": 20000})
    return out


def build_agent_payload(a: dict, tools: list[dict] | None = None,
                        webhook_url: str | None = None, kb: str = "") -> dict:
    """Cuerpo de create/update-agent a partir de nuestro custom_agent. `kb` =
    bloque de la base de conocimiento del cliente (routes.kb.kb_prefix): va
    DELANTE del guion, delimitado como información del negocio."""
    payload = {
        "agent_name": a.get("nombre", "Asistente"),
        "voice_id":   a.get("voz_id") or "EXAVITQu4vr4xnSDxMaL",
        "language":   a.get("idioma") or "es-CO",
        "llm": {
            "provider":    "anthropic",
            "model":       LLM_MODEL,
            "temperature": LLM_TEMP,
            "system_prompt": (f"{kb}\n\n" if kb else "") + a.get("prompt", ""),
            # Herramientas que el agente puede usar durante la llamada.
            "tools": list(tools or []),
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
    if a.get("saludo"):
        payload["begin_message"] = a["saludo"]
    if webhook_url:
        payload["webhook_url"] = webhook_url      # URL con el token del cliente
    return payload


def _agent_payload(a: dict) -> dict:
    """Compatibilidad: payload sin herramientas ni webhook."""
    return build_agent_payload(a)


def dynamic_variables(variables: list | None, datos: dict | None) -> dict[str, str]:
    """Valores de las variables {{…}} del guion para UNA llamada. Solo las que
    el agente declara y de las que hay dato; siempre como texto (Retell exige
    strings). Las que falten NO se inventan."""
    datos = datos or {}
    out: dict[str, str] = {}
    for v in variables or []:
        k = str(v).strip().strip("{}").strip()
        val = datos.get(k)
        if k and val is not None and str(val).strip() != "":
            out[k] = str(val)
    return out


def order_variables(order: dict | None, profile: dict | None) -> dict:
    """Datos disponibles para las variables, a partir de un registro y del
    perfil del negocio (nombres usados en los guiones: nombre, empresa, …)."""
    o, p = order or {}, profile or {}
    items = o.get("items") or []
    producto = o.get("products_display") or (items[0].get("product") if items else "") or ""
    total = o.get("total_amount")
    valor = f"{total:,.0f} {o.get('currency') or p.get('moneda') or ''}".strip() if total else ""
    return {
        "nombre": (o.get("customer_name") or "").split(" ")[0] if o.get("customer_name") else "",
        "nombre_completo": o.get("customer_name") or "",
        "empresa": p.get("empresa") or "",
        "producto": producto,
        "pedido_id": o.get("external_ref") or o.get("id") or "",
        "valor": valor,
        "direccion": o.get("address") or "",
        "ciudad": o.get("city") or "",
        "transportadora": o.get("carrier_slug") or "",
        "guia": o.get("tracking_number") or "",
        "telefono": o.get("customer_phone") or "",
        "tipo": o.get("tipo") or "",
    }


def build_call_payload(retell_agent_id: str, to_number: str, from_number: str | None = None,
                       variables: dict | None = None, metadata: dict | None = None) -> dict:
    """Cuerpo de create-phone-call, con las variables dinámicas de ESTA llamada."""
    payload: dict = {"agent_id": retell_agent_id, "to_number": to_number}
    if from_number:
        payload["from_number"] = from_number
    if variables:
        payload["retell_llm_dynamic_variables"] = {str(k): str(v) for k, v in variables.items()}
    if metadata:
        payload["metadata"] = metadata
    return payload


async def _tools_and_webhook(a: dict, org_id: str) -> tuple[list[dict], str | None, str]:
    """(herramientas, webhook_url, aviso) para el agente. Genera y guarda el
    token del agente si no lo tiene. Sin PUBLIC_BASE_URL no se envían
    herramientas (Retell no tendría a dónde llamar) y se devuelve un aviso."""
    import secrets
    import webhook_tokens
    from db import get_db
    base = webhook_tokens.public_base()
    if not base:
        return [], None, ("PUBLIC_BASE_URL no definida: el agente se registró SIN herramientas "
                          "ni webhook de resultados.")
    if not a.get("tool_token"):
        a["tool_token"] = secrets.token_urlsafe(32)
        if a.get("id"):
            await get_db().custom_agents.update_one(
                {"id": a["id"], "org_id": org_id}, {"$set": {"tool_token": a["tool_token"]}})
    mcp: list[dict] = []
    if any(str(n).startswith("mcp__") for n in (a.get("tools") or [])):
        try:
            from routes.mcp_servers import active_tools
            mcp = await active_tools(org_id)
        except Exception as e:  # noqa: BLE001
            log.warning("Sin herramientas MCP para el agente %s: %s", a.get("id"), type(e).__name__)
    tools = build_custom_tools(a.get("tools"), mcp, base, a["tool_token"])
    hook = webhook_tokens.urls_for(base, await webhook_tokens.token_for(org_id))["retell"]
    return tools, hook, ""


async def upsert_agent(a: dict, org_id: str | None = None) -> dict:
    """Create or update the Retell agent con la cuenta del cliente dueño del
    agente, con sus herramientas y su webhook. Returns {ok, retell_agent_id, ...}."""
    org_id = org_id or a.get("org_id") or ""
    if not await configured(org_id):
        return {"ok": False, "beta": True, "detail": NOT_CONNECTED}
    tools, hook, aviso = await _tools_and_webhook(a, org_id)
    from routes.kb import kb_prefix
    kb = await kb_prefix(org_id)          # información del negocio de ESTE cliente
    payload = build_agent_payload(a, tools, hook, kb)
    existing = a.get("retell_agent_id")
    if existing:
        ok, body = await _req(org_id, "PATCH", f"/update-agent/{existing}", payload)
        rid = existing if ok else None
    else:
        ok, body = await _req(org_id, "POST", "/create-agent", payload)
        rid = body.get("agent_id") if ok else None
    out = {"ok": ok, "retell_agent_id": rid, "response": body, "tools_sent": len(tools),
           "kb_incluida": bool(kb)}
    if aviso:
        out["aviso"] = aviso
    return out


async def place_call(org_id: str, retell_agent_id: str, to_number: str,
                     from_number: str | None = None, variables: dict | None = None,
                     metadata: dict | None = None) -> dict:
    """Llamada saliente por la cuenta de Retell de ESTE cliente, con las
    variables dinámicas ({{nombre}}, …) de esta llamada."""
    if not await configured(org_id):
        return {"ok": False, "beta": True, "detail": NOT_CONNECTED}
    payload = build_call_payload(retell_agent_id, to_number, from_number, variables, metadata)
    ok, body = await _req(org_id, "POST", "/create-phone-call", payload)
    return {"ok": ok, "response": body}
