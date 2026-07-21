"""Routes: /calls — cadence planning and attempt-result registration."""
from datetime import datetime, timezone, date
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from db import get_db
from deps import require_api_key
from models import CallSchedule, ScheduleRequest, AttemptResult, Attempt
from cadence import build_plan
from chatea import get_client as get_chatea

router = APIRouter(prefix="/calls", tags=["cadence"],
                   dependencies=[Depends(require_api_key)])


@router.post("/schedule", response_model=CallSchedule,
             summary="Build (or rebuild) the 5-attempt cadence for a queue item.")
async def schedule(payload: ScheduleRequest):
    db = get_db()
    q = await db.call_queue.find_one({"id": payload.queue_id}, {"_id": 0})
    if not q:
        raise HTTPException(404, "Queue item not found")

    plan = build_plan(country=q.get("country", "CO"),
                      start_date=date.fromisoformat(q["office_arrival_date"][:10]),
                      office_claim_max_days=q.get("office_claim_max_days"))
    sched = CallSchedule(queue_id=payload.queue_id,
                         attempts=[Attempt(**a) for a in plan])

    await db.call_schedules.replace_one({"queue_id": payload.queue_id},
                                        sched.model_dump(), upsert=True)
    await db.call_queue.update_one({"id": payload.queue_id},
                                   {"$set": {"next_attempt_at": plan[0]["scheduled_at"],
                                             "updated_at": _now_iso()}})
    return sched


@router.get("/schedule/{queue_id}", response_model=CallSchedule,
            summary="Fetch the current cadence plan for a queue item.")
async def get_schedule(queue_id: str):
    doc = await get_db().call_schedules.find_one({"queue_id": queue_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "No cadence plan for this queue item")
    return doc


@router.post("/attempt-result",
             summary="Register the outcome of an attempt; advances or stops the cadence.")
async def attempt_result(payload: AttemptResult):
    db = get_db()
    sched = await db.call_schedules.find_one({"queue_id": payload.queue_id}, {"_id": 0})
    if not sched:
        raise HTTPException(404, "No cadence plan for this queue item")

    updated: List[dict] = []
    target = None
    for att in sched["attempts"]:
        if att["attempt_number"] == payload.attempt_number:
            att["status"] = "done"
            att["result"] = payload.result
            att["notes"] = payload.notes
            att["executed_at"] = _now_iso()
            target = att
        updated.append(att)
    if not target:
        raise HTTPException(400, "attempt_number not found in plan")

    # Business rules
    new_queue_status = None
    if payload.result == "confirmado":
        new_queue_status = "confirmado"
    elif payload.result == "ya_recogio":
        new_queue_status = "ya_recogio"
    elif payload.result == "rechaza":
        new_queue_status = "rechazado"
    elif payload.result == "numero_incorrecto":
        new_queue_status = "detenido"
    elif payload.result == "extension":
        new_queue_status = "extension"

    if new_queue_status:
        # Stop remaining attempts
        for att in updated:
            if att["status"] == "pending":
                att["status"] = "skipped"

    # WhatsApp fallback after 3 consecutive no_contesta
    last3 = [a["result"] for a in updated if a["status"] == "done"][-3:]
    if len(last3) == 3 and all(r == "no_contesta" for r in last3):
        q = await db.call_queue.find_one({"id": payload.queue_id}, {"_id": 0})
        order = await db.orders.find_one({"id": q["order_id"]}, {"_id": 0}) if q else None
        if order:
            chatea = get_chatea()
            text = (f"Hola {order.get('customer_name', '')}, hemos intentado llamarte "
                    f"por tu pedido en oficina. ¿Puedes confirmar si lo recogerás?")
            res = await chatea.send_message(order["customer_phone"], text) \
                if chatea.configured else {"ok": False, "error": "unconfigured"}
            await db.message_log.insert_one({
                "id": _uuid(), "order_id": order["id"], "queue_id": payload.queue_id,
                "direction": "outbound", "channel": "whatsapp",
                "phone": order["customer_phone"], "body": text,
                "provider": "chatea_pro", "provider_message_id": res.get("provider_message_id"),
                "status": "sent" if res.get("ok") else "failed",
                "error": res.get("error"),
                "created_at": _now_iso(),
            })

    # Escalate after 5 done without resolution
    done = [a for a in updated if a["status"] == "done"]
    if not new_queue_status and len(done) >= 5:
        new_queue_status = "escalado"

    # next_attempt_at
    next_at = next((a["scheduled_at"] for a in updated if a["status"] == "pending"), None)

    await db.call_schedules.update_one({"queue_id": payload.queue_id},
                                       {"$set": {"attempts": updated}})
    q_upd = {"current_attempt": payload.attempt_number,
             "next_attempt_at": next_at, "updated_at": _now_iso()}
    if new_queue_status:
        q_upd["status"] = new_queue_status
        # If confirmed/refused/etc create a customer task for handoff
        if new_queue_status in ("rechazado", "detenido", "escalado", "extension"):
            await _create_followup_task(payload.queue_id, new_queue_status)
    await db.call_queue.update_one({"id": payload.queue_id}, {"$set": q_upd})
    return {"ok": True, "queue_status": new_queue_status or "in_progress",
            "next_attempt_at": next_at}


async def _create_followup_task(queue_id: str, reason: str):
    db = get_db()
    q = await db.call_queue.find_one({"id": queue_id}, {"_id": 0})
    if not q:
        return
    task_type_map = {"rechazado": "otro", "detenido": "cambio_direccion",
                     "escalado": "otro", "extension": "mas_dias"}
    doc = {
        "id": _uuid(),
        "order_id": q["order_id"],
        "queue_id": queue_id,
        "type": task_type_map.get(reason, "otro"),
        "description": f"Ticket automático por cadencia: resultado {reason}.",
        "source": "ai",
        "status": "open",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await db.customer_tasks.insert_one(doc)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _uuid():
    import uuid
    return str(uuid.uuid4())
