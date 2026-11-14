"""Herramientas que el agente de VOZ llama durante una conversación en vivo.

REGLA: ninguna herramienta devuelve `ok: true` sin haber hecho algo real.
  · Las que se pueden hacer con lo que existe SE HACEN (y dejan rastro en la
    base de datos del cliente): crear tarea, registrar resultado, confirmar,
    reagendar, registrar promesa de pago, enviar WhatsApp con la cuenta del
    cliente, ejecutar una herramienta MCP activa.
  · Las que no (transferencia en vivo, link de pago) devuelven
    `{"ok": false, "error": "no disponible todavía"}`.
  · No existe `human_confirmed`: quien llama no puede declararse confirmado
    por un humano. Si llega en el cuerpo, se ignora.

AUTENTICACIÓN (una de dos):
  · Cabecera `X-Agent-Token` (o `?agent_token=`): el token propio del agente
    (custom_agents.tool_token), que retell_service envía en cada función
    personalizada. Resuelve agente Y cliente; el agente solo puede usar las
    herramientas que tiene asignadas.
  · Sesión JWT o X-API-Key de plataforma (+ X-Org-Id): uso interno/pruebas.
El cliente (org) NUNCA sale del cuerpo.

Las fechas no las calcula el LLM: `consultar_disponibilidad` y
`proximo_horario_disponible` devuelven horarios laborales en la zona horaria
del perfil del cliente. OJO: no hay calendario conectado; son horarios
laborales genéricos y así lo dice la respuesta (`calendario_conectado: false`).
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from db import get_db
from deps import get_org, require_api_key

NO_DISPONIBLE = "no disponible todavía"
# Solo lectura: cualquier agente autenticado puede usarlas.
_READ_ONLY = {"consultar_disponibilidad", "proximo_horario_disponible"}


async def tool_ctx(request: Request,
                   x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
                   x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    """Contexto de la llamada: {"org_id", "agent_id", "tools"}."""
    tok = (x_agent_token or request.query_params.get("agent_token") or "").strip()
    if tok:
        a = await get_db().custom_agents.find_one(
            {"tool_token": tok}, {"_id": 0, "id": 1, "org_id": 1, "tools": 1})
        if not a or not a.get("org_id"):
            raise HTTPException(401, "Token de agente inválido.")
        return {"org_id": a["org_id"], "agent_id": a["id"], "tools": list(a.get("tools") or [])}
    await require_api_key(request, x_api_key)
    return {"org_id": get_org(request), "agent_id": None, "tools": None}


router = APIRouter(prefix="/agent-tools", tags=["agent-tools"])


def _iso() -> str: return datetime.now(timezone.utc).isoformat()


def _allowed(ctx: dict, tool: str) -> None:
    """Con token de agente: solo las herramientas asignadas a ESE agente."""
    if ctx.get("tools") is None or tool in _READ_ONLY:
        return
    from retell_service import TOOL_ALIASES
    mine = {TOOL_ALIASES.get(t, t) for t in ctx["tools"]}
    if tool not in mine:
        raise HTTPException(403, f"Este agente no tiene asignada la herramienta {tool}.")


async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    return body if isinstance(body, dict) else {}


async def _args(request: Request, model: type[BaseModel]):
    """Cuerpo → modelo. Acepta los argumentos en la raíz o dentro de `args`
    (formato de las funciones personalizadas de Retell)."""
    body = await _body(request)
    if isinstance(body.get("args"), dict):
        body = body["args"]
    try:
        return model(**body)
    except ValidationError as e:
        raise HTTPException(422, [{"campo": ".".join(str(x) for x in err["loc"]),
                                   "error": err["msg"]} for err in e.errors()])


async def _log(action: str, payload: dict, ctx: dict, ok: bool, detail: str = "") -> str:
    """Bitácora de cada llamada a herramienta (colección agent_tool_calls)."""
    rec = {
        "id":         uuid4().hex[:12],
        "action":     action, "tool": action, "kind": "voz", "source": "voice_agent",
        "payload":    payload,
        "ok":         bool(ok), "error": "" if ok else detail[:300],
        "org_id":     ctx["org_id"], "agent_id": ctx.get("agent_id"),
        "created_at": _iso(),
    }
    await get_db().agent_tool_calls.insert_one(rec)
    return rec["id"]


async def _fail(action: str, payload: dict, ctx: dict, error: str, **extra) -> dict:
    tid = await _log(action, payload, ctx, False, error)
    return {"ok": False, "error": error, "tool_call_id": tid, **extra}


async def _find_order(org: str, pedido_id: str) -> dict | None:
    """Registro de ESTE cliente por id interno o referencia externa."""
    pedido_id = str(pedido_id or "").strip()
    if not pedido_id:
        return None
    db = get_db()
    return (await db.orders.find_one({"org_id": org, "id": pedido_id}, {"_id": 0})
            or await db.orders.find_one({"org_id": org, "external_ref": pedido_id}, {"_id": 0}))


async def _new_task(ctx: dict, tipo: str, description: str, order: dict | None = None) -> str:
    doc = {
        "id": str(uuid4()), "org_id": ctx["org_id"],
        "order_id": (order or {}).get("id"), "queue_id": None,
        "type": (tipo or "otro")[:60], "description": description[:2000],
        "source": "ai", "assigned_to": None, "status": "open",
        "agent_id": ctx.get("agent_id"),
        "created_at": _iso(), "updated_at": _iso(),
    }
    await get_db().customer_tasks.insert_one(doc)
    return doc["id"]


# --------- Date helpers (backend-only, LLM never computes dates) ---------
async def _org_now(org: str) -> tuple[datetime, str]:
    """(ahora, zona) en la zona horaria del perfil del cliente."""
    from routes.org_profile import get_profile, tz_of
    tz = tz_of(await get_profile(org))
    return datetime.now(tz), str(tz)


def _next_business_hour(base: datetime, hour_start: int = 8, hour_end: int = 18) -> datetime:
    """Round `base` up to the next slot within business hours (Mon-Sat)."""
    d = base.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while True:
        if d.weekday() == 6:                           # Sunday → Monday
            d = d.replace(hour=hour_start) + timedelta(days=1); continue
        if d.hour < hour_start: d = d.replace(hour=hour_start); continue
        if d.hour >= hour_end:                         # roll to next day
            d = d.replace(hour=hour_start) + timedelta(days=1); continue
        return d


_SIN_CALENDARIO = ("Horario laboral genérico (lun-sáb 8-18) en la zona del negocio; "
                   "no hay calendario conectado, no garantiza disponibilidad real.")


class _In(BaseModel):
    model_config = ConfigDict(extra="ignore")     # p. ej. `human_confirmed` se descarta


class DispIn(_In):
    duracion_min: int = 30
    n:            int = 3   # number of slots to propose


@router.post("/consultar_disponibilidad",
             summary="Devuelve N horarios laborales en la zona horaria del negocio — el LLM SOLO lee.")
async def consultar_disponibilidad(request: Request, ctx: dict = Depends(tool_ctx)):
    payload = await _args(request, DispIn)
    now, zona = await _org_now(ctx["org_id"])
    slots = []
    cursor = _next_business_hour(now)
    for _ in range(max(1, min(payload.n, 10))):
        slots.append({
            "iso":     cursor.isoformat(),                    # e.g. 2026-08-03T10:00:00-05:00
            "humano":  cursor.strftime("%A %d/%m %H:%M"),
            "zona":    zona,
        })
        cursor = _next_business_hour(cursor + timedelta(minutes=max(1, payload.duracion_min)))
    await _log("consultar_disponibilidad", payload.model_dump(), ctx, True)
    return {"ok": True, "slots": slots, "calendario_conectado": False, "nota": _SIN_CALENDARIO}


@router.post("/proximo_horario_disponible",
             summary="Devuelve UN solo horario laboral (para reagendar rápido).")
async def proximo_horario_disponible(request: Request, ctx: dict = Depends(tool_ctx)):
    now, zona = await _org_now(ctx["org_id"])
    slot = _next_business_hour(now)
    await _log("proximo_horario_disponible", {}, ctx, True)
    return {"ok": True, "slot": {
        "iso":    slot.isoformat(),
        "humano": slot.strftime("%A %d/%m %H:%M"),
        "zona":   zona,
    }, "calendario_conectado": False, "nota": _SIN_CALENDARIO}


# --------- Acciones reales sobre los datos del cliente ---------
class ReagendarIn(_In):
    pedido_id:       str = Field(..., min_length=1, max_length=120)
    nueva_fecha_iso: str = Field(..., min_length=4, max_length=40)
    telefono:        Optional[str] = Field(None, max_length=40)


@router.post("/reagendar_entrega",
             summary="Guarda la nueva fecha en el registro y crea una tarea para el equipo.")
async def reagendar_entrega(request: Request, ctx: dict = Depends(tool_ctx)):
    _allowed(ctx, "reagendar_entrega")
    p = await _args(request, ReagendarIn)
    org = ctx["org_id"]
    order = await _find_order(org, p.pedido_id)
    if not order:
        return await _fail("reagendar_entrega", p.model_dump(), ctx,
                           f"No encontré el registro {p.pedido_id}.")
    await get_db().orders.update_one(
        {"id": order["id"], "org_id": org},
        {"$set": {"metadata.reagendado_para": p.nueva_fecha_iso, "metadata.reagendado_at": _iso()}})
    tarea = await _new_task(ctx, "reagendar_entrega",
                            f"El cliente pidió reprogramar {p.pedido_id} para {p.nueva_fecha_iso}."
                            + (f" Tel: {p.telefono}." if p.telefono else ""), order)
    tid = await _log("reagendar_entrega", p.model_dump(), ctx, True)
    return {"ok": True, "tool_call_id": tid, "tarea_id": tarea,
            "detail": (f"Nueva fecha {p.nueva_fecha_iso} guardada en {p.pedido_id} y tarea creada "
                       "para el equipo. No se avisó automáticamente a terceros.")}


class ConfirmarPedidoIn(_In):
    pedido_id: str = Field(..., min_length=1, max_length=120)
    direccion: Optional[str] = Field(None, max_length=300)
    franja:    Optional[str] = Field(None, max_length=120)


@router.post("/confirmar_pedido", summary="Marca el registro como confirmado por el cliente.")
async def confirmar_pedido(request: Request, ctx: dict = Depends(tool_ctx)):
    _allowed(ctx, "confirmar_pedido")
    p = await _args(request, ConfirmarPedidoIn)
    org = ctx["org_id"]
    db = get_db()
    order = await _find_order(org, p.pedido_id)
    if not order:
        return await _fail("confirmar_pedido", p.model_dump(), ctx,
                           f"No encontré el registro {p.pedido_id}.")
    upd = {"metadata.confirmado_at": _iso(), "metadata.confirmado_por": "agente_voz"}
    if p.direccion:
        upd["address"] = p.direccion
    if p.franja:
        upd["metadata.franja"] = p.franja
    await db.orders.update_one({"id": order["id"], "org_id": org}, {"$set": upd})
    # Si está en la cola de contacto, se cierra el caso y se detiene su cadencia.
    q = await db.call_queue.find_one(
        {"org_id": org, "order_id": order["id"], "status": {"$in": ["pending", "in_progress"]}},
        {"_id": 0, "id": 1})
    if q:
        from routes.webhooks import _stop_cadence
        await _stop_cadence(q["id"], "confirmado", org)
    tid = await _log("confirmar_pedido", p.model_dump(), ctx, True)
    return {"ok": True, "tool_call_id": tid, "cola_cerrada": bool(q),
            "detail": f"{p.pedido_id} quedó confirmado."}


class WhatsAppIn(_In):
    # `telefono` es opcional y NO decide el destino: solo se acepta si coincide
    # con el número del cliente de esta llamada o de este pedido.
    telefono:  Optional[str] = Field(None, max_length=40)
    pedido_id: Optional[str] = Field(None, max_length=120)
    call_id:   Optional[str] = Field(None, max_length=120)
    plantilla: Optional[str] = Field(None, max_length=120)
    mensaje:   Optional[str] = Field(None, max_length=2000)


def _digits(phone) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def _same_phone(a, b) -> bool:
    """Mismo número aunque uno traiga prefijo de país o '+' y el otro no."""
    da, db_ = _digits(a), _digits(b)
    if len(da) < 7 or len(db_) < 7:
        return False
    return da == db_ or (min(len(da), len(db_)) >= 10 and (da.endswith(db_) or db_.endswith(da)))


async def _numeros_del_cliente(ctx: dict, envelope: dict, p: "WhatsAppIn") -> list[str]:
    """Números a los que ESTA llamada puede escribir: el del cliente final.
    Salen de datos que el modelo NO controla:
      1. el pedido/registro `pedido_id` de este negocio (customer_phone);
      2. la llamada `call_id` ya registrada de este negocio;
      3. el sobre de Retell (`call.to_number` en salientes, `call.from_number`
         en entrantes), que lo arma Retell y no el modelo. Solo con token de
         agente: con sesión/llave de plataforma no se confía en el cuerpo."""
    org = ctx["org_id"]
    db = get_db()
    out: list[str] = []
    if p.pedido_id:
        order = await _find_order(org, p.pedido_id)
        if order and order.get("customer_phone"):
            out.append(order["customer_phone"])
    call = envelope.get("call") if isinstance(envelope.get("call"), dict) else {}
    call_id = str(call.get("call_id") or p.call_id or "").strip()
    if call_id:
        rec = await db.calls.find_one({"call_id": call_id, "org_id": org}, {"_id": 0})
        if rec:
            out.append(rec.get("from_number") if rec.get("direction") == "inbound"
                       else rec.get("telefono"))
    if ctx.get("agent_id") and call and isinstance(envelope.get("args"), dict):
        out.append(call.get("from_number") if call.get("direction") == "inbound"
                   else call.get("to_number"))
        oid = (call.get("metadata") or {}).get("order_id") if isinstance(call.get("metadata"), dict) else None
        if oid:
            order = await db.orders.find_one({"org_id": org, "id": str(oid)}, {"_id": 0})
            if order and order.get("customer_phone"):
                out.append(order["customer_phone"])
    seen: list[str] = []
    for n in out:
        if n and len(_digits(n)) >= 7 and not any(_same_phone(n, s) for s in seen):
            seen.append(str(n))
    return seen


SOLO_AL_CLIENTE = ("Solo puedo enviar WhatsApp al número del cliente de esta llamada o de "
                   "este pedido. No se envió nada.")


@router.post("/enviar_whatsapp",
             summary="Envía un WhatsApp REAL con la cuenta del cliente, SOLO al número del "
                     "cliente de esta llamada/pedido.")
async def enviar_whatsapp(request: Request, ctx: dict = Depends(tool_ctx)):
    _allowed(ctx, "enviar_whatsapp")
    envelope = await _body(request)
    p = await _args(request, WhatsAppIn)
    org = ctx["org_id"]
    from chatea import client_for, NOT_CONNECTED
    if not (p.mensaje or p.plantilla):
        return await _fail("enviar_whatsapp", p.model_dump(), ctx,
                           "Falta el texto (mensaje) o el nombre de la plantilla.")
    # Destino: el número del cliente de esta llamada/pedido, nunca uno libre.
    permitidos = await _numeros_del_cliente(ctx, envelope, p)
    if not permitidos:
        return await _fail("enviar_whatsapp", p.model_dump(), ctx,
                           SOLO_AL_CLIENTE + " Indica el pedido_id del cliente.")
    if p.telefono:
        destino = next((n for n in permitidos if _same_phone(n, p.telefono)), None)
        if not destino:
            return await _fail("enviar_whatsapp", p.model_dump(), ctx, SOLO_AL_CLIENTE)
    else:
        destino = permitidos[0]
    p.telefono = destino
    chatea = await client_for(org)                 # credenciales de ESTE cliente
    if not chatea.configured:
        return await _fail("enviar_whatsapp", p.model_dump(), ctx, NOT_CONNECTED)
    try:
        if p.plantilla:
            res = await chatea.send_template(p.telefono, p.plantilla, params={})
        else:
            res = await chatea.send_message(p.telefono, p.mensaje)
    except Exception as e:  # noqa: BLE001
        res = {"ok": False, "error": type(e).__name__}
    sent = bool(res.get("ok"))
    await get_db().message_log.insert_one({
        "id": str(uuid4()), "org_id": org, "order_id": None, "queue_id": None,
        "direction": "outbound", "channel": "whatsapp",
        "phone": p.telefono, "body": p.mensaje or f"[plantilla] {p.plantilla}",
        "provider": "chatea_pro", "provider_message_id": res.get("provider_message_id"),
        "status": "sent" if sent else "failed", "error": res.get("error"),
        "source": "voice_agent", "agent_id": ctx.get("agent_id"), "created_at": _iso(),
    })
    if not sent:
        return await _fail("enviar_whatsapp", p.model_dump(), ctx,
                           "WhatsApp no se envió: "
                           + str(res.get("error") or f"HTTP {res.get('status_code')}")[:200])
    tid = await _log("enviar_whatsapp", p.model_dump(), ctx, True)
    return {"ok": True, "tool_call_id": tid, "detail": f"WhatsApp enviado a {p.telefono}."}


class TransferIn(_In):
    telefono: str = Field(..., min_length=6, max_length=40)
    razon:    Optional[str] = Field(None, max_length=500)


@router.post("/transferir_a_humano",
             summary="Transferencia en vivo: no disponible todavía. Deja una tarea para el equipo.")
async def transferir_a_humano(request: Request, ctx: dict = Depends(tool_ctx)):
    _allowed(ctx, "transferir_a_humano")
    p = await _args(request, TransferIn)
    tarea = await _new_task(ctx, "contactar_cliente",
                            f"El cliente {p.telefono} pidió hablar con una persona."
                            + (f" Motivo: {p.razon}" if p.razon else ""))
    return await _fail("transferir_a_humano", p.model_dump(), ctx, NO_DISPONIBLE,
                       tarea_id=tarea,
                       detail=("La transferencia en vivo no está disponible todavía. Quedó una "
                               "tarea para que una persona del equipo contacte al cliente."))


class PromesaPagoIn(_In):
    pedido_id: str = Field(..., min_length=1, max_length=120)
    fecha_iso: str = Field(..., min_length=4, max_length=40)
    monto:     Optional[float] = None


@router.post("/registrar_promesa_pago",
             summary="Registra la promesa (no mueve dinero) y la deja para revisión humana.")
async def registrar_promesa_pago(request: Request, ctx: dict = Depends(tool_ctx)):
    _allowed(ctx, "registrar_promesa_pago")
    p = await _args(request, PromesaPagoIn)
    org = ctx["org_id"]
    order = await _find_order(org, p.pedido_id)
    if not order:
        return await _fail("registrar_promesa_pago", p.model_dump(), ctx,
                           f"No encontré el registro {p.pedido_id}.")
    await get_db().orders.update_one(
        {"id": order["id"], "org_id": org},
        {"$set": {"metadata.promesa_pago": {"fecha": p.fecha_iso, "monto": p.monto,
                                           "registrada_at": _iso(), "revisada": False}}})
    tarea = await _new_task(ctx, "promesa_pago",
                            f"Promesa de pago de {p.pedido_id} para {p.fecha_iso}"
                            + (f" por {p.monto}" if p.monto is not None else "")
                            + ". Pendiente de revisión por una persona.", order)
    tid = await _log("registrar_promesa_pago", p.model_dump(), ctx, True)
    return {"ok": True, "tool_call_id": tid, "tarea_id": tarea,
            "pendiente_revision_humana": True,
            "detail": f"Promesa de pago de {p.pedido_id} registrada para {p.fecha_iso}."}


class LinkPagoIn(_In):
    telefono:  str = Field(..., max_length=40)
    pedido_id: str = Field(..., max_length=120)
    monto:     float


@router.post("/enviar_link_pago", summary="No disponible todavía (no hay pasarela conectada).")
async def enviar_link_pago(request: Request, ctx: dict = Depends(tool_ctx)):
    _allowed(ctx, "enviar_link_pago")
    p = await _args(request, LinkPagoIn)
    return await _fail("enviar_link_pago", p.model_dump(), ctx, NO_DISPONIBLE,
                       detail="Todavía no hay una pasarela de pagos conectada; no se envió nada.")


class TareaIn(_In):
    descripcion: Optional[str] = Field(None, max_length=2000)
    titulo:      Optional[str] = Field(None, max_length=200)
    notas:       Optional[str] = Field(None, max_length=2000)
    tipo:        str = Field("seguimiento", max_length=60)
    prioridad:   Optional[str] = Field(None, max_length=20)
    pedido_id:   Optional[str] = Field(None, max_length=120)


@router.post("/crear_tarea", summary="Crea una tarea de seguimiento para el equipo humano.")
async def crear_tarea(request: Request, ctx: dict = Depends(tool_ctx)):
    _allowed(ctx, "crear_tarea")
    p = await _args(request, TareaIn)
    texto = " — ".join(x.strip() for x in (p.titulo, p.descripcion, p.notas) if x and x.strip())
    if not texto:
        return await _fail("crear_tarea", p.model_dump(), ctx, "Falta la descripción de la tarea.")
    if p.prioridad:
        texto = f"[{p.prioridad}] {texto}"
    order = await _find_order(ctx["org_id"], p.pedido_id) if p.pedido_id else None
    tarea = await _new_task(ctx, p.tipo, texto, order)
    tid = await _log("crear_tarea", p.model_dump(), ctx, True)
    return {"ok": True, "tool_call_id": tid, "tarea_id": tarea, "detail": "Tarea creada."}


class ResultadoIn(_In):
    outcome:   str = Field(..., min_length=1, max_length=60)
    pedido_id: Optional[str] = Field(None, max_length=120)
    telefono:  Optional[str] = Field(None, max_length=40)
    notas:     Optional[str] = Field(None, max_length=2000)
    fecha:     Optional[str] = Field(None, max_length=40)
    fecha_recogida: Optional[str] = Field(None, max_length=40)
    call_id:   Optional[str] = Field(None, max_length=120)


@router.post("/registrar_resultado", summary="Guarda el resultado de la llamada.")
async def registrar_resultado(request: Request, ctx: dict = Depends(tool_ctx)):
    _allowed(ctx, "registrar_resultado")
    p = await _args(request, ResultadoIn)
    org = ctx["org_id"]
    order = await _find_order(org, p.pedido_id) if p.pedido_id else None
    doc = {
        "id": uuid4().hex[:12], "org_id": org, "agent_id": ctx.get("agent_id"),
        "order_id": (order or {}).get("id"), "pedido_ref": p.pedido_id,
        "telefono": p.telefono, "outcome": p.outcome.strip().lower(),
        "notas": p.notas, "fecha": p.fecha or p.fecha_recogida, "call_id": p.call_id,
        "created_at": _iso(),
    }
    await get_db().agent_call_results.insert_one(dict(doc))
    if order:
        await get_db().orders.update_one(
            {"id": order["id"], "org_id": org},
            {"$set": {"metadata.ultimo_resultado": {"outcome": doc["outcome"],
                                                   "fecha": doc["fecha"], "at": doc["created_at"]}}})
    tid = await _log("registrar_resultado", p.model_dump(), ctx, True)
    return {"ok": True, "tool_call_id": tid, "resultado_id": doc["id"],
            "pedido_encontrado": bool(order), "detail": "Resultado registrado."}


# --------- Herramientas MCP activas del cliente ---------
@router.post("/mcp/{full_name}",
             summary="Ejecuta una herramienta MCP ACTIVA del cliente (sin confirmación humana).")
async def mcp_tool(full_name: str, request: Request, ctx: dict = Depends(tool_ctx)):
    from agent.tools import MCP_PREFIX, execute, needs_confirm, result_ok
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    args = body.get("args") if isinstance(body, dict) and isinstance(body.get("args"), dict) \
        else (body if isinstance(body, dict) else {})
    args = {k: v for k, v in args.items() if k not in ("call", "name", "human_confirmed")}
    if not full_name.startswith(MCP_PREFIX):
        raise HTTPException(404, "Herramienta desconocida.")
    if ctx.get("tools") is not None and full_name not in ctx["tools"]:
        raise HTTPException(403, "Este agente no tiene asignada esa herramienta.")
    org = ctx["org_id"]
    if await needs_confirm(full_name, org):
        return await _fail(f"mcp:{full_name}", {}, ctx,
                           "Esta herramienta exige confirmación humana y no se puede usar "
                           "durante una llamada.")
    res = await execute(full_name, args, {"org_id": org, "user_id": None,
                                          "thread_id": None, "source": "voice_agent"})
    ok = result_ok(res)
    if not ok:
        return {"ok": False, "error": str(res.get("error") or "La herramienta falló.")[:300],
                "result": res.get("result")}
    return {"ok": True, "result": res.get("result")}
