"""Copilot agent — tool catalog + executor.

Each tool is a small async python function that operates on the Hub's own
Mongo state, plus a JSON-schema-lite dict the LLM can read to decide which
tool to call.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Any, Callable, Awaitable
import json
import uuid

from db import get_db
from cadence import days_left as _days_left, build_plan
from data import semaphore_for
from chatea import get_client as get_chatea
from translation import get_provider as get_translation


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------- individual tools ----------
async def tool_get_queue(status: str | None = None, semaphore: str | None = None,
                        carrier_slug: str | None = None, limit: int = 50) -> Any:
    db = get_db()
    q: dict = {}
    if status:
        q["status"] = status
    if carrier_slug:
        q["carrier_slug"] = carrier_slug
    docs = await db.call_queue.find(q, {"_id": 0}).sort("created_at", -1) \
        .limit(min(limit, 200)).to_list(200)
    out = []
    for d in docs:
        dl = _days_left(d["office_arrival_date"], d.get("office_claim_max_days"))
        sem = semaphore_for(d.get("office_claim_max_days"), dl)
        if semaphore and sem != semaphore:
            continue
        order = await db.orders.find_one({"id": d["order_id"]}, {"_id": 0})
        carrier = await db.carriers.find_one({"slug": d["carrier_slug"]}, {"_id": 0, "name": 1})
        out.append({
            "queue_id": d["id"], "order_id": d["order_id"],
            "customer_name": (order or {}).get("customer_name"),
            "customer_phone": (order or {}).get("customer_phone"),
            "city": (order or {}).get("city"),
            "carrier": (carrier or {}).get("name") or d["carrier_slug"],
            "days_left": dl, "semaphore": sem,
            "status": d.get("status"), "current_attempt": d.get("current_attempt"),
        })
    return {"count": len(out), "items": out}


async def tool_get_orders(limit: int = 50, status: str | None = None) -> Any:
    db = get_db()
    q = {"status": status} if status else {}
    docs = await db.orders.find(q, {"_id": 0}).sort("created_at", -1) \
        .limit(min(limit, 200)).to_list(200)
    return {"count": len(docs), "items": docs}


async def tool_get_carriers() -> Any:
    docs = await get_db().carriers.find({}, {"_id": 0}).to_list(50)
    return {"count": len(docs), "items": docs}


async def tool_get_novedades(carrier: str | None = None, categoria: str | None = None) -> Any:
    q: dict = {}
    if carrier:
        q["carrier"] = carrier
    if categoria:
        q["categoria"] = categoria
    docs = await get_db().carrier_novedades.find(q, {"_id": 0}).limit(200).to_list(200)
    return {"count": len(docs), "items": docs}


async def tool_schedule_cadence(queue_id: str) -> Any:
    db = get_db()
    qd = await db.call_queue.find_one({"id": queue_id}, {"_id": 0})
    if not qd:
        return {"error": f"queue_id {queue_id} not found"}
    plan = build_plan(country=qd.get("country", "CO"),
                     start_date=date.fromisoformat(qd["office_arrival_date"][:10]),
                     office_claim_max_days=qd.get("office_claim_max_days"))
    sched = {"id": str(uuid.uuid4()), "queue_id": queue_id, "attempts": plan,
             "created_at": _now()}
    await db.call_schedules.replace_one({"queue_id": queue_id}, sched, upsert=True)
    await db.call_queue.update_one({"id": queue_id},
                                   {"$set": {"next_attempt_at": plan[0]["scheduled_at"],
                                             "updated_at": _now()}})
    return {"ok": True, "queue_id": queue_id, "attempts": plan}


async def tool_register_attempt_result(queue_id: str, attempt_number: int,
                                       result: str, notes: str | None = None) -> Any:
    # Delegate to the existing route handler to keep logic in one place.
    from routes.cadence import attempt_result
    from models import AttemptResult as AR
    r = await attempt_result(AR(queue_id=queue_id, attempt_number=attempt_number,
                                result=result, notes=notes))  # type: ignore[arg-type]
    return r


async def tool_send_whatsapp(phone: str, text: str,
                             queue_id: str | None = None,
                             order_id: str | None = None) -> Any:
    chatea = get_chatea()
    res = await chatea.send_message(phone, text)
    db = get_db()
    await db.message_log.insert_one({
        "id": str(uuid.uuid4()),
        "order_id": order_id, "queue_id": queue_id,
        "direction": "outbound", "channel": "whatsapp",
        "phone": phone, "body": text,
        "provider": "chatea_pro",
        "provider_message_id": res.get("provider_message_id"),
        "status": "sent" if res.get("ok") else "failed",
        "error": res.get("error"),
        "created_at": _now(),
    })
    return {"ok": res.get("ok"), "status_code": res.get("status_code"),
            "phone": phone, "text": text}


async def tool_list_whatsapp_templates() -> Any:
    return await get_chatea().list_templates()


async def tool_create_task(description: str, type: str = "otro",
                          order_id: str | None = None, queue_id: str | None = None,
                          assigned_to: str | None = None) -> Any:
    db = get_db()
    doc = {
        "id": str(uuid.uuid4()),
        "order_id": order_id, "queue_id": queue_id,
        "type": type, "description": description,
        "source": "ai", "assigned_to": assigned_to,
        "status": "open",
        "created_at": _now(), "updated_at": _now(),
    }
    await db.customer_tasks.insert_one(doc)
    return {"ok": True, "task": {k: v for k, v in doc.items() if k != "_id"}}


async def tool_list_tasks(status: str | None = None, limit: int = 20) -> Any:
    q = {"status": status} if status else {}
    docs = await get_db().customer_tasks.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(min(limit, 100)).to_list(100)
    return {"count": len(docs), "items": docs}


async def tool_get_metrics() -> Any:
    from routes.metrics import metrics
    return await metrics()  # type: ignore[misc]


async def tool_translate(text: str, target: str = "es") -> Any:
    prov = get_translation()
    return {"provider": prov.name,
            "target": target,
            "translated": prov.translate(text, "auto", target)}


async def tool_list_voices() -> Any:
    docs = await get_db().voice_profiles.find({}, {"_id": 0}).to_list(20)
    return {"count": len(docs), "items": docs}


async def tool_list_numbers() -> Any:
    docs = await get_db().connected_numbers.find({}, {"_id": 0}).to_list(50)
    return {"count": len(docs), "items": docs}


async def tool_import_orders_from_file(file_id: str,
                                       carrier_slug: str = "servientrega",
                                       country: str = "CO") -> Any:
    """Take a previously-uploaded CSV/XLSX and import each row as an order."""
    db = get_db()
    f = await db.uploaded_files.find_one({"id": file_id}, {"_id": 0})
    if not f:
        return {"error": f"file_id {file_id} not found"}
    rows = f.get("rows_preview") or []
    if f.get("row_count", 0) > len(rows):
        # We only stored a preview — instruct the user to re-upload if they need
        # to import the full file. In this MVP we cap at preview rows.
        pass
    from models import Order, OrderIn, QueueItem
    inserted = 0
    for r in rows:
        # Flexible column mapping
        name = r.get("customer_name") or r.get("cliente") or r.get("nombre") or "Sin nombre"
        phone = str(r.get("customer_phone") or r.get("telefono") or r.get("phone") or "").strip()
        if not phone:
            continue
        city = r.get("city") or r.get("ciudad") or ""
        total = float(r.get("total") or r.get("total_amount") or r.get("valor") or 0)
        tracking = r.get("tracking") or r.get("tracking_number") or r.get("guia") or None
        ext = r.get("external_ref") or r.get("order_id") or r.get("pedido") or None
        order = Order(
            external_ref=str(ext) if ext else None,
            customer_name=str(name), customer_phone=phone,
            address=str(r.get("address") or r.get("direccion") or ""),
            city=str(city), country=country,
            total_amount=total, currency="COP",
            carrier_slug=carrier_slug, tracking_number=str(tracking) if tracking else None,
            products=[], status="in_queue",
        )
        await db.orders.insert_one(order.model_dump())
        carrier = await db.carriers.find_one({"slug": carrier_slug}, {"_id": 0})
        q = QueueItem(order_id=order.id, carrier_slug=carrier_slug,
                     office_arrival_date=date.today().isoformat(),
                     office_claim_max_days=(carrier or {}).get("office_claim_max_days"),
                     country=country)
        await db.call_queue.insert_one(q.model_dump())
        inserted += 1
    return {"ok": True, "inserted": inserted, "file": f["filename"]}


# ---------- registry ----------
ToolFn = Callable[..., Awaitable[Any]]

TOOLS: dict[str, ToolFn] = {
    "get_queue": tool_get_queue,
    "get_orders": tool_get_orders,
    "get_carriers": tool_get_carriers,
    "get_carrier_novedades": tool_get_novedades,
    "schedule_cadence": tool_schedule_cadence,
    "register_attempt_result": tool_register_attempt_result,
    "send_whatsapp": tool_send_whatsapp,
    "list_whatsapp_templates": tool_list_whatsapp_templates,
    "create_task": tool_create_task,
    "list_tasks": tool_list_tasks,
    "get_metrics": tool_get_metrics,
    "translate": tool_translate,
    "list_voices": tool_list_voices,
    "list_numbers": tool_list_numbers,
    "import_orders_from_file": tool_import_orders_from_file,
}

# Schema shown to the LLM (kept small — the description is what the model reads).
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"name": "get_queue",
     "description": "Consulta la cola de pedidos en oficina. Filtros opcionales: status ('pending','in_progress','confirmado','rechazado','ya_recogio','extension','escalado','detenido'), semaphore ('rojo','amarillo','verde','gris'), carrier_slug (ej 'envia','servientrega'), limit (default 50).",
     "args": {"status": "str?", "semaphore": "str?", "carrier_slug": "str?", "limit": "int?"}},
    {"name": "get_orders",
     "description": "Lista pedidos COD. Filtros: status, limit.",
     "args": {"status": "str?", "limit": "int?"}},
    {"name": "get_carriers",
     "description": "Lista las 12 transportadoras colombianas con reglas de reclamo.",
     "args": {}},
    {"name": "get_carrier_novedades",
     "description": "Tabla de referencia: estatus del carrier → significado + acción. Filtros: carrier, categoria ('RECLAMO_EN_OFICINA','DEVOLUCION','NOVEDAD','TRANSITO','ENTREGADO','OTRO').",
     "args": {"carrier": "str?", "categoria": "str?"}},
    {"name": "schedule_cadence",
     "description": "Genera (o regenera) el plan de 5 intentos para un queue_id. Envía queue_id.",
     "args": {"queue_id": "str"}},
    {"name": "register_attempt_result",
     "description": "Registra el resultado de un intento. result debe ser uno de: 'confirmado','extension','rechaza','ya_recogio','no_contesta','numero_incorrecto'.",
     "args": {"queue_id": "str", "attempt_number": "int", "result": "str", "notes": "str?"}},
    {"name": "send_whatsapp",
     "description": "Envía WhatsApp por Chatea Pro. Args: phone (E.164), text. Opcional queue_id, order_id.",
     "args": {"phone": "str", "text": "str", "queue_id": "str?", "order_id": "str?"}},
    {"name": "list_whatsapp_templates",
     "description": "Lista templates aprobadas en Chatea Pro.",
     "args": {}},
    {"name": "create_task",
     "description": "Crea un ticket. type ∈ 'cambio_direccion','factura','mas_dias','cambio_oficina','otro'.",
     "args": {"description": "str", "type": "str?", "order_id": "str?", "queue_id": "str?", "assigned_to": "str?"}},
    {"name": "list_tasks",
     "description": "Lista tickets. Filtros: status ('open','in_progress','resolved','closed').",
     "args": {"status": "str?", "limit": "int?"}},
    {"name": "get_metrics",
     "description": "KPIs del dashboard (cola por estado, intentos 24h, tasa de contacto, tickets abiertos).",
     "args": {}},
    {"name": "translate",
     "description": "Traduce texto. target ∈ 'es','en','pt'.",
     "args": {"text": "str", "target": "str?"}},
    {"name": "list_voices",
     "description": "Lista las voces IA registradas (ElevenLabs).",
     "args": {}},
    {"name": "list_numbers",
     "description": "Lista los caller IDs verificados con Twilio.",
     "args": {}},
    {"name": "import_orders_from_file",
     "description": "Importa pedidos desde un archivo CSV/XLSX previamente subido. Args: file_id (obligatorio), carrier_slug, country.",
     "args": {"file_id": "str", "carrier_slug": "str?", "country": "str?"}},
]


def tools_prompt_block() -> str:
    """Compact JSON block describing the tools for the LLM system prompt."""
    return json.dumps(TOOL_SCHEMAS, ensure_ascii=False)


async def execute(name: str, args: dict[str, Any]) -> dict[str, Any]:
    fn = TOOLS.get(name)
    if not fn:
        return {"error": f"Tool desconocida: {name}"}
    try:
        result = await fn(**(args or {}))
        return {"ok": True, "result": result}
    except TypeError as e:
        return {"error": f"Argumentos inválidos para {name}: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Error ejecutando {name}: {e}"}
