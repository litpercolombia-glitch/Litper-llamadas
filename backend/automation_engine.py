"""Motor de AUTOMATIZACIONES ("cuando pase X, haz Y"), por cliente (org).

Regla (colección `automations`):
  {id, org_id, nombre, activa,
   trigger: {tipo: pedido_creado | pedido_estado | llamada_terminada |
                   mensaje_entrante | horario,
             filtro: {campo: valor | {igual|contiene|mayor|menor: valor}},
             cron?: "m h dom mes dow"  (solo `horario`; mínimo cada 15 min)},
   accion:  {tipo: enviar_whatsapp | crear_tarea | lanzar_llamada |
                   llamar_herramienta_mcp, params: {...}},
   limite_diario}

  await emit(org_id, evento, payload)   ← se llama donde OCURRE el evento. NO espera:
                                          las reglas corren en SEGUNDO PLANO
                                          (asyncio.create_task con referencia guardada).
  await emit_now(org_id, evento, payload) ← lo mismo, esperando el resultado.
  await drain()                         ← espera lo que haya en segundo plano (pruebas).
  await tick_horario()                  ← scheduler.py, cada minuto

GARANTÍAS
* Aislamiento: solo se evalúan las reglas de `org_id`, y cada acción usa las
  credenciales de ESE cliente. Si faltan, la ejecución queda registrada como
  fallida con un mensaje claro (nunca se usa la cuenta de otro).
* `emit` NUNCA rompe la petición que lo dispara: todo va en try/except + log.
* Cada ejecución queda en `automation_runs {org_id, rule_id, ok, detalle, …}`.
* `limite_diario` por regla (por defecto 100 ejecuciones al día), ATÓMICO: un
  contador por regla y día en `automation_counters` ($inc con upsert sobre el
  índice único org+key+day), así dos eventos simultáneos no lo exceden.
* TOPE POR DESTINATARIO, por cliente y contando TODAS sus reglas: al mismo
  número, máximo 3 llamadas y 5 WhatsApp por día, y un intervalo mínimo entre
  envíos (llamadas 30 min, WhatsApp 5 min). El exceso queda registrado como
  ejecución fallida ("Tope por destinatario…"). También atómico.
* FRENO A CASCADAS: lo que crea una automatización (llamada, mensaje) va marcado
  `origen: "automatizacion"` con su profundidad. Un evento `llamada_terminada`
  o `mensaje_entrante` causado por una automatización puede disparar reglas UNA
  vez (profundidad 1); lo que salga de ahí ya no dispara nada más.
* Los textos del evento (nombre del cliente, mensaje entrante…) son DATOS: solo
  se copian en los campos `{{variable}}` de la acción; no eligen ni la acción,
  ni la herramienta, ni el destinatario fuera de lo que configuró el negocio.
* Sin confirmación humana posible: una herramienta MCP que exige confirmación
  NO se ejecuta desde una automatización.
"""
from __future__ import annotations
import asyncio
import logging
import re
import uuid
import weakref
from datetime import datetime, timedelta, timezone
from typing import Any

from db import get_db

log = logging.getLogger("automations")

EVENTOS = ("pedido_creado", "pedido_estado", "llamada_terminada", "mensaje_entrante", "horario")
ACCIONES = ("enviar_whatsapp", "crear_tarea", "lanzar_llamada", "llamar_herramienta_mcp")
OPERADORES = ("igual", "contiene", "mayor", "menor")
MAX_RULES = 50
DEFAULT_LIMITE = 100
MAX_LIMITE = 1000
MIN_CRON_MINUTES = 15
ACTION_TIMEOUT_S = 25
# Tope por destinatario (por cliente, sumando todas sus reglas).
DEST_CAPS = {"llamada": 3, "whatsapp": 5}                 # por día y número
DEST_MIN_GAP_S = {"llamada": 30 * 60, "whatsapp": 5 * 60}  # entre envíos al mismo número
MAX_CHAIN_DEPTH = 1            # eventos causados por automatizaciones: 1 salto y no más
CHAIN_EVENTS = ("llamada_terminada", "mensaje_entrante")
INBOUND_CHAIN_WINDOW_S = 10 * 60   # una respuesta en ≤10 min a un mensaje automático hereda su profundidad
MAX_CONCURRENT = 8             # reglas en segundo plano a la vez (importaciones masivas)
MAX_TEMPLATE_PARAMS = 20

# Campos disponibles por evento (para filtros y {{variables}}): los muestra la
# interfaz y los usa la IA al proponer una regla.
CAMPOS = {
    "pedido_creado": ["customer_name", "customer_phone", "city", "tipo", "status",
                      "total_amount", "currency", "external_ref", "carrier_slug", "order_id"],
    "pedido_estado": ["estado", "customer_name", "customer_phone", "city", "tipo",
                      "total_amount", "external_ref", "order_id"],
    "llamada_terminada": ["telefono", "resultado", "duracion", "direction", "agent_id", "call_id"],
    "mensaje_entrante": ["phone", "text", "channel"],
    "horario": ["fecha", "hora"],
}

EJEMPLOS = {
    "pedido_creado": {"order_id": "ejemplo-1", "customer_name": "Cliente de ejemplo",
                      "customer_phone": "+10000000000", "city": "Ciudad", "tipo": "pedido",
                      "status": "imported", "total_amount": 100, "currency": "USD",
                      "external_ref": "REF-1", "carrier_slug": ""},
    "pedido_estado": {"order_id": "ejemplo-1", "estado": "confirmado",
                      "customer_name": "Cliente de ejemplo", "customer_phone": "+10000000000",
                      "city": "Ciudad", "tipo": "pedido", "total_amount": 100, "external_ref": "REF-1"},
    "llamada_terminada": {"call_id": "llamada-ejemplo", "telefono": "+10000000000",
                          "resultado": "sin_clasificar", "duracion": 60, "direction": "outbound",
                          "agent_id": ""},
    "mensaje_entrante": {"phone": "+10000000000", "text": "Hola, quiero información",
                         "channel": "whatsapp"},
    "horario": {"fecha": "2030-01-01", "hora": "09:00"},
}


class RuleError(ValueError):
    """La regla no es válida (mensaje para el usuario)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _txt(v: Any, n: int) -> str:
    return " ".join(str(v if v is not None else "").split())[:n]


# ------------------------------------------------------------------ validación
def validate_cron(expr: str) -> str:
    """Cron de 5 campos, válido y que no dispare más seguido que cada 15 min."""
    from apscheduler.triggers.cron import CronTrigger
    expr = " ".join(str(expr or "").split())
    if len(expr.split(" ")) != 5 or len(expr) > 100:
        raise RuleError("El horario debe ser un cron de 5 campos (minuto hora día mes día-semana), "
                        "por ejemplo «0 9 * * 1-5».")
    try:
        trig = CronTrigger.from_crontab(expr, timezone=timezone.utc)
    except Exception:  # noqa: BLE001
        raise RuleError("El horario (cron) no es válido. Ejemplo: «0 9 * * 1-5».")
    prev, t = None, datetime(2030, 1, 1, tzinfo=timezone.utc)
    for _ in range(60):
        nxt = trig.get_next_fire_time(prev, t)
        if nxt is None:
            break
        if prev is not None and (nxt - prev) < timedelta(minutes=MIN_CRON_MINUTES):
            raise RuleError(f"Una regla con horario puede ejecutarse como mínimo cada "
                            f"{MIN_CRON_MINUTES} minutos.")
        prev, t = nxt, nxt + timedelta(seconds=1)
    if prev is None:
        raise RuleError("Ese horario nunca se cumple.")
    return expr


def _clean_filtro(filtro: Any) -> dict:
    if filtro in (None, ""):
        return {}
    if not isinstance(filtro, dict):
        raise RuleError("El filtro debe ser un objeto {campo: valor}.")
    if len(filtro) > 10:
        raise RuleError("Máximo 10 condiciones por regla.")
    out: dict = {}
    for campo, cond in filtro.items():
        campo = _txt(campo, 60)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,59}", campo):
            raise RuleError(f"Nombre de campo no válido en el filtro: «{campo}».")
        if isinstance(cond, dict):
            if not cond or any(op not in OPERADORES for op in cond):
                raise RuleError("Operadores permitidos en el filtro: igual, contiene, mayor, menor.")
            limpio = {}
            for op, val in cond.items():
                if op in ("mayor", "menor"):
                    try:
                        val = float(val)
                    except (TypeError, ValueError):
                        raise RuleError(f"«{op}» necesita un número (campo {campo}).")
                elif isinstance(val, (dict, list)):
                    raise RuleError(f"Valor no válido en el filtro (campo {campo}).")
                elif isinstance(val, str):
                    val = val[:200]
                limpio[op] = val
            out[campo] = limpio
        elif isinstance(cond, (str, int, float, bool)) or cond is None:
            out[campo] = cond[:200] if isinstance(cond, str) else cond
        else:
            raise RuleError(f"Valor no válido en el filtro (campo {campo}).")
    return out


def _clean_params(tipo: str, params: Any) -> dict:
    p = params if isinstance(params, dict) else {}
    if tipo == "enviar_whatsapp":
        out = {"telefono": _txt(p.get("telefono"), 80),
               "mensaje": str(p.get("mensaje") or "").strip()[:1500],
               "plantilla": _txt(p.get("plantilla"), 120)}
        if not out["mensaje"] and not out["plantilla"]:
            raise RuleError("Escribe el mensaje de WhatsApp (o el nombre de una plantilla aprobada).")
        # Campos que la plantilla DECLARA: {nombre_en_la_plantilla: "valor o {{campo}}"}.
        # Solo esos se envían al proveedor (nunca el evento completo).
        pp = p.get("plantilla_params")
        if pp in (None, ""):
            pp = {}
        if not isinstance(pp, dict) or len(pp) > MAX_TEMPLATE_PARAMS:
            raise RuleError(f"Los datos de la plantilla deben ser hasta {MAX_TEMPLATE_PARAMS} pares nombre → valor.")
        limpio = {}
        for k, v in pp.items():
            k = _txt(k, 60)
            if not re.fullmatch(r"[A-Za-z0-9_]{1,60}", k) or isinstance(v, (dict, list)):
                raise RuleError(f"Dato de plantilla no válido: «{k}».")
            limpio[k] = _txt(v, 300)
        if limpio and not out["plantilla"]:
            raise RuleError("Los datos de plantilla solo se usan si indicas una plantilla.")
        out["plantilla_params"] = limpio
        return out
    if tipo == "crear_tarea":
        out = {"descripcion": str(p.get("descripcion") or "").strip()[:1000],
               "tipo": _txt(p.get("tipo"), 60) or "seguimiento"}
        if not out["descripcion"]:
            raise RuleError("Escribe la descripción de la tarea.")
        return out
    if tipo == "lanzar_llamada":
        out = {"agent_id": _txt(p.get("agent_id"), 40), "telefono": _txt(p.get("telefono"), 80)}
        if not out["agent_id"]:
            raise RuleError("Elige el agente de voz que hará la llamada.")
        return out
    if tipo == "llamar_herramienta_mcp":
        nombre = _txt(p.get("herramienta"), 200)
        if not nombre.startswith("mcp__"):
            raise RuleError("Elige una herramienta de tus conectores (nombre «mcp__servidor__herramienta»).")
        args = p.get("args") if isinstance(p.get("args"), dict) else {}
        import json
        if len(json.dumps(args, ensure_ascii=False, default=str)) > 4000:
            raise RuleError("Los argumentos de la herramienta son demasiado largos.")
        return {"herramienta": nombre, "args": args}
    raise RuleError("Acción no válida.")


def validate_rule(data: Any) -> dict:
    """Normaliza y valida una regla (sin id ni org). RuleError si no es válida."""
    if not isinstance(data, dict):
        raise RuleError("La regla debe ser un objeto.")
    nombre = _txt(data.get("nombre"), 120)
    if not nombre:
        raise RuleError("Ponle un nombre a la regla.")
    trig = data.get("trigger") if isinstance(data.get("trigger"), dict) else {}
    tipo = _txt(trig.get("tipo"), 40)
    if tipo not in EVENTOS:
        raise RuleError("Elige cuándo se ejecuta: " + ", ".join(EVENTOS) + ".")
    trigger: dict = {"tipo": tipo, "filtro": _clean_filtro(trig.get("filtro"))}
    if tipo == "horario":
        trigger["cron"] = validate_cron(trig.get("cron"))
    elif trig.get("cron"):
        raise RuleError("El campo cron solo se usa cuando la regla es por horario.")
    acc = data.get("accion") if isinstance(data.get("accion"), dict) else {}
    atipo = _txt(acc.get("tipo"), 40)
    if atipo not in ACCIONES:
        raise RuleError("Elige qué hace la regla: " + ", ".join(ACCIONES) + ".")
    params = _clean_params(atipo, acc.get("params"))
    if atipo in ("enviar_whatsapp", "lanzar_llamada") and not params.get("telefono"):
        if tipo == "horario":
            raise RuleError("Una regla por horario necesita el teléfono de destino.")
        params["telefono"] = {"mensaje_entrante": "{{phone}}",
                              "llamada_terminada": "{{telefono}}"}.get(tipo, "{{customer_phone}}")
    try:
        limite = int(data.get("limite_diario") if data.get("limite_diario") is not None else DEFAULT_LIMITE)
    except (TypeError, ValueError):
        raise RuleError("El límite diario debe ser un número.")
    if not 1 <= limite <= MAX_LIMITE:
        raise RuleError(f"El límite diario debe estar entre 1 y {MAX_LIMITE}.")
    return {"nombre": nombre, "activa": bool(data.get("activa", True)), "trigger": trigger,
            "accion": {"tipo": atipo, "params": params}, "limite_diario": limite}


# ------------------------------------------------------------------- filtros
def _get(payload: dict, campo: str) -> Any:
    cur: Any = payload
    for part in campo.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _norm(v: Any) -> str:
    return str(v if v is not None else "").strip().casefold()


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def matches(filtro: dict | None, payload: dict | None) -> bool:
    """Filtros simples: igualdad, contiene, mayor y menor (pura)."""
    payload = payload or {}
    for campo, cond in (filtro or {}).items():
        val = _get(payload, campo)
        conds = cond if isinstance(cond, dict) else {"igual": cond}
        for op, arg in conds.items():
            if op == "igual":
                a, b = _num(val), _num(arg)
                if isinstance(arg, (int, float)) and not isinstance(arg, bool) and a is not None:
                    if a != b:
                        return False
                elif _norm(val) != _norm(arg):
                    return False
            elif op == "contiene":
                if _norm(arg) not in _norm(val):
                    return False
            elif op in ("mayor", "menor"):
                a, b = _num(val), _num(arg)
                if a is None or b is None or (a <= b if op == "mayor" else a >= b):
                    return False
            else:
                return False
    return True


_VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]{0,59})\s*\}\}")


def render(template: Any, payload: dict | None) -> Any:
    """Sustituye {{campo}} por el dato del evento (vacío si no existe). El dato
    se copia como texto: no se vuelve a interpretar."""
    if isinstance(template, str):
        return _VAR.sub(lambda m: _txt(_get(payload or {}, m.group(1)), 500), template)
    if isinstance(template, dict):
        return {k: render(v, payload) for k, v in template.items()}
    if isinstance(template, list):
        return [render(v, payload) for v in template]
    return template


def describe(rule: dict, payload: dict | None, raw: bool = False) -> str:
    """Qué haría la regla con este evento, en lenguaje llano (no ejecuta nada).
    `raw=True`: sin evento a la vista (tarjeta de confirmación) → las variables
    se muestran tal cual ({{customer_name}}), nunca vacías."""
    acc = rule.get("accion") or {}
    p = (acc.get("params") or {}) if raw else render(acc.get("params") or {}, payload)
    t = acc.get("tipo")
    if t == "enviar_whatsapp":
        que = f"la plantilla «{p.get('plantilla')}»" if p.get("plantilla") and not p.get("mensaje") \
            else f"«{_txt(p.get('mensaje'), 300)}»"
        return f"Enviaría un WhatsApp a {p.get('telefono') or '(sin teléfono)'}: {que}"
    if t == "crear_tarea":
        return f"Crearía una tarea ({p.get('tipo')}): «{_txt(p.get('descripcion'), 300)}»"
    if t == "lanzar_llamada":
        return f"Llamaría a {p.get('telefono') or '(sin teléfono)'} con el agente {p.get('agent_id')}"
    if t == "llamar_herramienta_mcp":
        return f"Usaría la herramienta «{p.get('herramienta')}» de tus conectores"
    return "Acción desconocida"


# ---------------------------------------------------------------- contadores
def _is_dup(e: Exception) -> bool:
    return type(e).__name__ == "DuplicateKeyError" or "duplicate key" in str(e).lower()


async def _reserve(org: str, key: str, day: str, cap: int) -> bool:
    """Suma 1 al contador (org, key, day) SOLO si aún no llegó a `cap`. Atómico:
    un único find_one_and_update con upsert; si el contador ya está en el tope el
    filtro no encaja, el upsert intenta insertar y choca con el índice único
    (org_id, key, day) → False."""
    coll = get_db().automation_counters
    filtro = {"org_id": org, "key": key, "day": day, "n": {"$lt": int(cap)}}
    upd = {"$inc": {"n": 1}, "$set": {"exp": _now()}}
    try:
        await coll.find_one_and_update(filtro, upd, upsert=True, return_document=True,
                                       projection={"_id": 0, "n": 1})
        return True
    except Exception as e:  # noqa: BLE001
        if not _is_dup(e):
            raise
    # Choque con el índice único: o el contador está en el tope, o dos reservas
    # crearon el contador a la vez. Se reintenta SIN upsert: si aún hay cupo, entra.
    return bool(await coll.find_one_and_update(filtro, upd, return_document=True,
                                               projection={"_id": 0, "n": 1}))


async def _reserve_gap(org: str, key: str, gap_s: int) -> bool:
    """True si pasó al menos `gap_s` desde la última reserva de `key` (y la anota).
    Mismo patrón atómico que `_reserve`."""
    now = _now()
    coll = get_db().automation_counters
    filtro = {"org_id": org, "key": key, "day": "-",
              "last_at": {"$lte": (now - timedelta(seconds=gap_s)).isoformat()}}
    upd = {"$set": {"last_at": now.isoformat(), "exp": now}}
    try:
        await coll.find_one_and_update(filtro, upd, upsert=True, return_document=True,
                                       projection={"_id": 0, "last_at": 1})
        return True
    except Exception as e:  # noqa: BLE001
        if not _is_dup(e):
            raise
    return bool(await coll.find_one_and_update(filtro, upd, return_document=True,
                                               projection={"_id": 0, "last_at": 1}))


def _digits(phone: Any) -> str:
    return re.sub(r"\D", "", str(phone or ""))


async def _local_day(org: str) -> str:
    """Fecha LOCAL del negocio (los topes diarios se cuentan por su día)."""
    from routes.org_profile import get_profile, tz_of
    return _now().astimezone(tz_of(await get_profile(org))).date().isoformat()


class ActionFailed(Exception):
    """La acción no se pudo hacer (mensaje claro para el historial)."""


async def reserve_recipient(org: str, canal: str, phone: str) -> None:
    """Tope por destinatario de ESTE cliente (suma todas sus reglas). Se llama
    justo antes de contactar: si no hay cupo lanza ActionFailed y no se envía."""
    num = _digits(phone)
    if len(num) < 6:
        raise ActionFailed("El teléfono de destino no es válido.")
    cap, gap = DEST_CAPS[canal], DEST_MIN_GAP_S[canal]
    que = "llamadas" if canal == "llamada" else "mensajes de WhatsApp"
    try:
        if not await _reserve_gap(org, f"gap:{canal}:{num}", gap):
            raise ActionFailed(f"Tope por destinatario: ya se contactó a este número hace menos de "
                               f"{gap // 60} minutos ({que}). No se repitió.")
        if not await _reserve(org, f"dest:{canal}:{num}", await _local_day(org), cap):
            raise ActionFailed(f"Tope por destinatario: máximo {cap} {que} por día al mismo número. "
                               "No se envió.")
    except ActionFailed:
        raise
    except Exception as e:  # noqa: BLE001 — sin poder comprobar el tope NO se contacta
        log.warning("tope por destinatario %s: %s", org, type(e).__name__)
        raise ActionFailed("Tope por destinatario: no se pudo comprobar el cupo; no se envió.")


def _depth(payload: dict | None) -> int:
    try:
        return max(0, int((payload or {}).get("_depth") or 0))
    except (TypeError, ValueError):
        return 0


async def inbound_depth(org: str, phone: str) -> int:
    """Profundidad de cadena de un mensaje ENTRANTE: si responde (en ≤10 min) a
    un mensaje que envió una automatización, hereda la de ese mensaje; si no, 0."""
    try:
        desde = (_now() - timedelta(seconds=INBOUND_CHAIN_WINDOW_S)).isoformat()
        docs = await get_db().message_log.find(
            {"org_id": org, "phone_digits": _digits(phone), "origen": "automatizacion",
             "direction": "outbound", "created_at": {"$gte": desde}},
            {"_id": 0, "automation_depth": 1, "created_at": 1}).sort("created_at", -1).limit(1).to_list(1)
        return int(docs[0].get("automation_depth") or 1) if docs else 0
    except Exception:  # noqa: BLE001
        return 0


# ------------------------------------------------------------------ acciones


async def _act_whatsapp(org: str, p: dict, payload: dict) -> str:
    from chatea import client_for, NOT_CONNECTED
    phone = _txt(p.get("telefono"), 40)
    if not phone:
        raise ActionFailed("El evento no trae teléfono de destino.")
    chatea = await client_for(org)
    if not chatea.configured:
        raise ActionFailed(NOT_CONNECTED)
    db = get_db()
    if await db.orders.find_one({"org_id": org, "customer_phone": phone, "opt_out": True},
                                {"_id": 0, "id": 1}):
        raise ActionFailed("Ese contacto pidió no recibir más mensajes; no se envió.")
    plantilla, mensaje = p.get("plantilla") or "", p.get("mensaje") or ""
    if not plantilla:
        from routes.whatsapp import window_open
        abierta, _ = await window_open(phone, org)
        if not abierta:
            raise ActionFailed("WhatsApp solo permite texto libre si el contacto escribió en las "
                               "últimas 24 horas. Usa una plantilla aprobada en esta regla.")
    await reserve_recipient(org, "whatsapp", phone)      # tope por destinatario (atómico)
    if plantilla:
        # Solo los campos que la plantilla declara en la regla (ya con sus
        # {{variables}} sustituidas); nunca el evento completo.
        declarados = p.get("plantilla_params") if isinstance(p.get("plantilla_params"), dict) else {}
        res = await chatea.send_template(phone, plantilla,
                                         params={str(k): _txt(v, 300) for k, v in declarados.items()})
        body = f"[template:{plantilla}]"
    else:
        res = await chatea.send_message(phone, mensaje)
        body = mensaje
    await db.message_log.insert_one({
        "id": str(uuid.uuid4()), "org_id": org, "order_id": (payload or {}).get("order_id"),
        "direction": "outbound", "channel": "whatsapp", "phone": phone, "body": body,
        "template_name": plantilla or None, "provider": "chatea_pro", "source": "automatizacion",
        "origen": "automatizacion", "automation_depth": _depth(payload) + 1,
        "phone_digits": _digits(phone),
        "provider_message_id": res.get("provider_message_id"),
        "status": "sent" if res.get("ok") else "failed", "error": res.get("error"),
        "created_at": _now().isoformat()})
    if not res.get("ok"):
        raise ActionFailed("WhatsApp no se envió: "
                           + str(res.get("error") or f"HTTP {res.get('status_code')}")[:200])
    return f"WhatsApp enviado a {phone}."


async def _act_tarea(org: str, p: dict, payload: dict) -> str:
    now = _now().isoformat()
    doc = {"id": str(uuid.uuid4()), "org_id": org, "order_id": (payload or {}).get("order_id"),
           "queue_id": None, "type": p.get("tipo") or "seguimiento",
           "description": p.get("descripcion") or "", "source": "ai", "assigned_to": None,
           "status": "open", "created_at": now, "updated_at": now, "origen": "automatizacion"}
    await get_db().customer_tasks.insert_one(doc)
    return f"Tarea creada ({doc['id'][:8]})."


async def _act_llamada(org: str, p: dict, payload: dict) -> str:
    from routes.custom_agents import ensure_callable, place_agent_call, TelephonyError
    phone = _txt(p.get("telefono"), 40)
    if not phone:
        raise ActionFailed("El evento no trae teléfono de destino.")
    db = get_db()
    a = await db.custom_agents.find_one({"id": p.get("agent_id"), "org_id": org}, {"_id": 0})
    if not a:
        raise ActionFailed("El agente de voz de esta regla ya no existe.")
    order = None
    if (payload or {}).get("order_id"):
        order = await db.orders.find_one({"id": payload["order_id"], "org_id": org}, {"_id": 0})
    try:
        await ensure_callable(org, a)                    # sin telefonía no se gasta cupo
    except TelephonyError as e:
        raise ActionFailed(str(e))
    await reserve_recipient(org, "llamada", phone)       # tope por destinatario (atómico)
    try:
        r = await place_agent_call(org, a, phone, order, metadata_extra={
            "origen": "automatizacion", "automation_depth": _depth(payload) + 1})
    except TelephonyError as e:
        raise ActionFailed(str(e))
    if not r.get("ok"):
        raise ActionFailed("La telefonía rechazó la llamada.")
    return f"Llamada iniciada a {phone}."


async def _act_mcp(org: str, p: dict, payload: dict) -> str:
    from agent import tools as agent_tools
    nombre = p.get("herramienta") or ""
    from routes.mcp_servers import find_active_tool
    t = await find_active_tool(org, nombre)
    if not t:
        raise ActionFailed("Esa herramienta no está activa en tus conectores. Conéctala en Conexiones.")
    if t.get("requires_confirm"):
        raise ActionFailed("Esa herramienta exige confirmación de una persona; una automatización "
                           "no puede usarla.")
    res = await agent_tools.execute(nombre, p.get("args") or {},
                                    {"org_id": org, "user_id": None, "thread_id": "automatizacion"})
    if not agent_tools.result_ok(res):
        raise ActionFailed(str(res.get("error") or "La herramienta devolvió un error.")[:300])
    return f"Herramienta «{t['name']}» ejecutada."


_ACTIONS = {"enviar_whatsapp": _act_whatsapp, "crear_tarea": _act_tarea,
            "lanzar_llamada": _act_llamada, "llamar_herramienta_mcp": _act_mcp}


# --------------------------------------------------------------------- motor
async def _record(org: str, rule: dict, evento: str, ok: bool, detalle: str,
                  payload: dict | None = None, **extra) -> dict:
    doc = {"id": uuid.uuid4().hex[:12], "org_id": org, "rule_id": rule.get("id"),
           "rule_nombre": rule.get("nombre"), "evento": evento,
           "accion": (rule.get("accion") or {}).get("tipo"), "ok": bool(ok),
           "detalle": _txt(detalle, 500), "cuenta": True,
           "ref": _txt((payload or {}).get("order_id") or (payload or {}).get("call_id")
                       or (payload or {}).get("phone") or "", 80),
           "created_at": _now().isoformat(), **extra}
    await get_db().automation_runs.insert_one(dict(doc))
    return doc


async def run_rule(org: str, rule: dict, evento: str, payload: dict) -> dict | None:
    """Ejecuta UNA regla (ya filtrada) respetando su límite diario y deja el
    registro en `automation_runs`. Devuelve el registro (None si se omitió)."""
    db = get_db()
    dedupe = payload.get("_dedupe")
    if dedupe and not await _reserve(org, f"dedupe:{rule['id']}:{str(dedupe)[:200]}", "-", 1):
        return None                         # el mismo evento ya se procesó (reintento del proveedor)
    dia = await _local_day(org)
    limite = int(rule.get("limite_diario") or DEFAULT_LIMITE)
    clave = f"rule:{rule['id']}"
    if not await _reserve(org, clave, dia, limite):          # atómico: nunca pasa del límite
        primero = await db.automation_counters.find_one_and_update(
            {"org_id": org, "key": clave, "day": dia, "avisado": {"$ne": True}},
            {"$set": {"avisado": True}}, projection={"_id": 0, "n": 1})
        if primero:                                          # el aviso se registra una sola vez al día
            await _record(org, rule, evento, False,
                          f"Límite diario alcanzado ({limite}). La regla se retoma mañana.",
                          payload, cuenta=False, limite=True)
        return None
    acc = rule.get("accion") or {}
    params = render(acc.get("params") or {}, payload)
    extra = {"dedupe": str(dedupe)} if dedupe else {}
    try:
        fn = _ACTIONS.get(acc.get("tipo"))
        if not fn:
            raise ActionFailed("Acción desconocida.")
        detalle = await asyncio.wait_for(fn(org, params, payload), ACTION_TIMEOUT_S)
        ok = True
    except ActionFailed as e:
        ok, detalle = False, str(e)
    except asyncio.TimeoutError:
        ok, detalle = False, "La acción tardó demasiado y se canceló."
    except Exception as e:  # noqa: BLE001 — sin secretos: solo el tipo de error
        log.warning("automatización %s/%s falló: %s", org, rule.get("id"), type(e).__name__)
        ok, detalle = False, f"Error inesperado al ejecutar la acción ({type(e).__name__})."
    run = await _record(org, rule, evento, ok, detalle, payload, **extra)
    await db.automations.update_one({"id": rule["id"], "org_id": org},
                                    {"$set": {"last_run_at": run["created_at"], "last_ok": ok}})
    return run


# ------------------------------------------------------------ segundo plano
_TASKS: set = set()                 # referencias vivas: el recolector no se lleva las tareas
_SEMS: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def _task_done(t: "asyncio.Task") -> None:
    _TASKS.discard(t)
    if t.cancelled():
        return
    e = t.exception()
    if e is not None:               # no debería pasar (emit_now lo captura todo)
        log.warning("tarea de automatización terminó con error: %s", type(e).__name__)


async def _limited(coro) -> Any:
    loop = asyncio.get_running_loop()
    sem = _SEMS.get(loop)
    if sem is None:
        sem = _SEMS[loop] = asyncio.Semaphore(MAX_CONCURRENT)
    async with sem:
        return await coro


def spawn(coro) -> "asyncio.Task | None":
    """Lanza `coro` en segundo plano guardando la referencia. Sin bucle de
    eventos en marcha no hace nada (y cierra la corrutina)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        return None
    t = loop.create_task(_limited(coro))
    _TASKS.add(t)
    t.add_done_callback(_task_done)
    return t


async def drain(timeout: float = 60) -> None:
    """Espera a que termine lo lanzado en segundo plano en ESTE bucle (pruebas,
    apagado ordenado). Incluye lo que esas tareas lancen a su vez."""
    loop = asyncio.get_running_loop()
    fin = loop.time() + timeout
    while True:
        mias = [t for t in list(_TASKS) if not t.done() and t.get_loop() is loop]
        if not mias or loop.time() >= fin:
            return
        await asyncio.wait(mias, timeout=max(0.01, fin - loop.time()))


async def emit(org_id: str, evento: str, payload: dict | None = None) -> "asyncio.Task | None":
    """Avisa de un evento del cliente `org_id` y VUELVE EN EL ACTO: las reglas
    se evalúan y ejecutan en segundo plano, así la petición que lo dispara
    (alta de pedido, webhook…) no espera a WhatsApp ni a la telefonía. Nunca lanza."""
    try:
        return spawn(emit_now(org_id, evento, dict(payload or {})))
    except Exception as e:  # noqa: BLE001
        log.warning("emit(%s, %s) no se pudo programar: %s", org_id, evento, type(e).__name__)
        return None


async def emit_now(org_id: str, evento: str, payload: dict | None = None) -> list[dict]:
    """Evalúa y ejecuta AHORA las reglas activas de `org_id` que coincidan con
    el evento. NUNCA lanza: cualquier fallo se registra en el log y se sigue."""
    out: list[dict] = []
    try:
        if not org_id or evento not in EVENTOS:
            return out
        payload = dict(payload or {})
        rules = await get_db().automations.find(
            {"org_id": org_id, "activa": True, "trigger.tipo": evento}, {"_id": 0}).to_list(MAX_RULES)
        cortada = evento in CHAIN_EVENTS and _depth(payload) > MAX_CHAIN_DEPTH
        for rule in rules:
            try:
                if not matches((rule.get("trigger") or {}).get("filtro"), payload):
                    continue
                if cortada:                 # freno a cascadas: este evento ya viene de una cadena
                    out.append(await _record(
                        org_id, rule, evento, False,
                        "Cadena de automatizaciones cortada: este evento lo provocó otra "
                        "automatización y ya se había encadenado una vez. No se ejecutó.",
                        payload, cuenta=False, cadena=True))
                    continue
                run = await run_rule(org_id, rule, evento, payload)
                if run:
                    out.append(run)
            except Exception as e:  # noqa: BLE001 — una regla rota no frena a las demás
                log.warning("automatización %s/%s: %s", org_id, rule.get("id"), type(e).__name__)
    except Exception as e:  # noqa: BLE001 — jamás se propaga a quien lo disparó
        log.warning("emit(%s, %s) falló: %s", org_id, evento, type(e).__name__)
    return out


def order_payload(order: dict | None, **extra) -> dict:
    """Datos de un pedido/registro que ve una regla (campos planos)."""
    o = order or {}
    out = {"order_id": o.get("id"), "customer_name": o.get("customer_name") or "",
           "customer_phone": o.get("customer_phone") or "", "city": o.get("city") or "",
           "tipo": o.get("tipo") or "pedido", "status": o.get("status") or "",
           "total_amount": o.get("total_amount"), "currency": o.get("currency") or "",
           "external_ref": o.get("external_ref") or "", "carrier_slug": o.get("carrier_slug") or ""}
    out.update(extra)
    return out


async def _order_status_now(org_id: str, order_id: str | None, estado: str,
                            queue_id: str | None = None) -> list[dict]:
    try:
        db = get_db()
        if queue_id and not order_id:
            q = await db.call_queue.find_one({"id": queue_id, "org_id": org_id},
                                             {"_id": 0, "order_id": 1})
            order_id = (q or {}).get("order_id")
        order = await db.orders.find_one({"id": order_id, "org_id": org_id}, {"_id": 0}) \
            if order_id else None
        return await emit_now(org_id, "pedido_estado",
                              order_payload(order, order_id=order_id, estado=estado))
    except Exception as e:  # noqa: BLE001
        log.warning("pedido_estado(%s) falló: %s", org_id, type(e).__name__)
        return []


async def emit_order_status(org_id: str, order_id: str | None, estado: str) -> None:
    """Cambio de estado de un pedido (lo llaman cadencia, webhooks y voz).
    En segundo plano; nunca lanza."""
    try:
        spawn(_order_status_now(org_id, order_id, estado))
    except Exception as e:  # noqa: BLE001
        log.warning("emit_order_status(%s) falló: %s", org_id, type(e).__name__)


async def emit_queue_status(org_id: str, queue_id: str, estado: str) -> None:
    """Igual, a partir del caso de la cola."""
    try:
        spawn(_order_status_now(org_id, None, estado, queue_id=queue_id))
    except Exception as e:  # noqa: BLE001
        log.warning("emit_queue_status(%s) falló: %s", org_id, type(e).__name__)


# ------------------------------------------------------------------- horario
def cron_due(cron: str, tz, last: datetime, now: datetime) -> bool:
    """¿El cron (en la zona `tz`) tuvo una hora de disparo en (last, now]? (pura)"""
    from apscheduler.triggers.cron import CronTrigger
    try:
        trig = CronTrigger.from_crontab(cron, timezone=tz)
        nxt = trig.get_next_fire_time(None, last + timedelta(seconds=1))
    except Exception:  # noqa: BLE001
        return False
    return nxt is not None and nxt <= now


async def tick_horario(now: datetime | None = None) -> int:
    """Corre cada minuto: dispara las reglas `horario` cuya hora llegó, en la
    zona horaria del perfil de su negocio. El "reclamo" es atómico por regla
    (`last_checked_at`): con varias réplicas solo una la ejecuta."""
    from routes.org_profile import get_profile, tz_of
    db = get_db()
    now = now or _now()
    fired = 0
    try:
        rules = await db.automations.find({"activa": True, "trigger.tipo": "horario"},
                                          {"_id": 0}).to_list(2000)
    except Exception as e:  # noqa: BLE001
        log.warning("tick_horario: no pude leer reglas: %s", type(e).__name__)
        return 0
    for rule in rules:
        try:
            org = rule.get("org_id")
            if not org:
                continue
            prev = rule.get("last_checked_at")
            claimed = await db.automations.find_one_and_update(
                {"id": rule["id"], "org_id": org, "last_checked_at": prev},
                {"$set": {"last_checked_at": now.isoformat()}}, projection={"_id": 0, "id": 1})
            if not claimed or not prev:
                continue                    # otra réplica la tomó, o es su primer tick
            last = datetime.fromisoformat(prev)
            # tras una caída larga no se "recuperan" disparos viejos: ventana máx. 1 h
            last = max(last, now - timedelta(hours=1))
            tz = tz_of(await get_profile(org))
            if not cron_due((rule.get("trigger") or {}).get("cron") or "", tz, last, now):
                continue
            local = now.astimezone(tz)
            payload = {"fecha": local.date().isoformat(), "hora": local.strftime("%H:%M")}
            if not matches((rule.get("trigger") or {}).get("filtro"), payload):
                continue
            if await run_rule(org, rule, "horario", payload):
                fired += 1
        except Exception as e:  # noqa: BLE001
            log.warning("tick_horario %s: %s", rule.get("id"), type(e).__name__)
    return fired
