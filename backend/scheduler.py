"""Background dispatcher: every N minutes, mark due attempts as dispatched.

We don't actually place VAPI calls or WhatsApp sends here — that is done by the
external AI agent that consumes this Hub. This job just flips 'pending' →
'dispatched' when an attempt's scheduled_at is due, and moves the queue item
forward. WhatsApp attempts also emit a real Chatea Pro send.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import get_db
from chatea import get_client as get_chatea

log = logging.getLogger("scheduler")


async def dispatch_due_attempts():
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.call_schedules.find({"attempts.scheduled_at": {"$lte": now_iso},
                                     "attempts.status": "pending"},
                                    {"_id": 0})
    async for sched in cursor:
        changed = False
        for att in sched["attempts"]:
            if att["status"] != "pending":
                continue
            if att["scheduled_at"] > now_iso:
                continue
            # Only auto-dispatch WhatsApp; calls are executed by external AI agent.
            if att["channel"] == "whatsapp":
                chatea = get_chatea()
                phone = await _phone_for_queue(sched["queue_id"])
                order = await _order_for_queue(sched["queue_id"])
                product_name = ""
                customer_name = ""
                days_left = 0
                if order:
                    product_name = (order.get("products_display")
                                    or (order.get("items") or [{}])[0].get("product", "")
                                    or "tu pedido")
                    customer_name = order.get("customer_name", "") or ""
                # Fetch queue for days_left (semaphore-driven WA rule)
                q_doc = await db.call_queue.find_one({"id": sched["queue_id"]},
                                                     {"_id": 0, "days_left": 1})
                if q_doc and q_doc.get("days_left") is not None:
                    try: days_left = int(q_doc["days_left"])
                    except Exception: days_left = 0
                greet = f"Hola {customer_name}, " if customer_name else "Hola, "
                body_text = (
                    f"{greet}seguimos pendientes de tu pedido de "
                    f"{product_name or 'la orden'} en oficina. "
                    f"¿Puedes confirmar si lo recogerás hoy?")

                # WhatsApp rule: 0–3 días → reclamo_oficina · +3 → no_oficina
                from routes.whatsapp import resolve_rule_for_days_left, window_open
                rule = await resolve_rule_for_days_left(days_left)
                template_name = None
                if rule:
                    template_name = rule.get("template_name")

                # META 24h window enforcement:
                # If the customer has NOT replied in the last 24h → we MUST use a
                # template (approved by Meta). Free-form messages will be rejected.
                is_open, _ = await window_open(phone) if phone else (False, None)

                if phone and chatea.configured:
                    if not is_open and not template_name:
                        # Refuse — nothing we can send outside window without a template.
                        att["status"] = "skipped"
                        att["result"] = "wa_window_closed_no_template"
                        att["executed_at"] = now_iso
                        continue
                    if template_name and not is_open:
                        # Force template send (proactive outbound outside window)
                        params = {
                            "customer_name": customer_name or "",
                            "product_name":  product_name  or "",
                            "days_left":     str(days_left),
                        }
                        res = await chatea.send_template(phone, template_name,
                                                         params=params,
                                                         language=(rule or {}).get("template_language", "es"))
                    elif template_name and is_open:
                        # Window open — still use the template for consistency
                        params = {
                            "customer_name": customer_name or "",
                            "product_name":  product_name  or "",
                            "days_left":     str(days_left),
                        }
                        res = await chatea.send_template(phone, template_name,
                                                         params=params,
                                                         language=(rule or {}).get("template_language", "es"))
                    else:
                        # Window open + no rule → free-form allowed.
                        res = await chatea.send_message(phone, body_text)
                    att["status"] = "dispatched"
                    att["result"] = "whatsapp_sent" if res.get("ok") else "whatsapp_failed"
                    att["executed_at"] = now_iso
                    await db.message_log.insert_one({
                        "id": _uuid(),
                        "queue_id": sched["queue_id"],
                        "direction": "outbound",
                        "channel": "whatsapp",
                        "phone": phone,
                        "body": body_text if not template_name else f"[template:{template_name}] {days_left}d",
                        "template_name": template_name,
                        "provider": "chatea_pro",
                        "provider_message_id": res.get("provider_message_id"),
                        "status": "sent" if res.get("ok") else "failed",
                        "error": res.get("error"),
                        "created_at": now_iso,
                    })
                else:
                    att["status"] = "dispatched"
                    att["result"] = "whatsapp_unconfigured"
                    att["executed_at"] = now_iso
                changed = True
            else:
                # Mark call as dispatched → external AI must consume & post result.
                att["status"] = "dispatched"
                att["executed_at"] = now_iso
                changed = True
                # Only dispatch ONE call attempt per tick per queue.
                break
        if changed:
            await db.call_schedules.update_one({"id": sched["id"]},
                                               {"$set": {"attempts": sched["attempts"]}})
            await db.call_queue.update_one({"id": sched["queue_id"]},
                                           {"$set": {"status": "in_progress",
                                                     "updated_at": now_iso}})


async def _phone_for_queue(queue_id: str) -> str | None:
    db = get_db()
    q = await db.call_queue.find_one({"id": queue_id}, {"_id": 0, "order_id": 1})
    if not q:
        return None
    o = await db.orders.find_one({"id": q["order_id"]}, {"_id": 0, "customer_phone": 1})
    return o.get("customer_phone") if o else None


async def _order_for_queue(queue_id: str) -> dict | None:
    db = get_db()
    q = await db.call_queue.find_one({"id": queue_id}, {"_id": 0, "order_id": 1})
    if not q:
        return None
    return await db.orders.find_one({"id": q["order_id"]}, {"_id": 0})


def _uuid():
    import uuid
    return str(uuid.uuid4())


_scheduler: AsyncIOScheduler | None = None


def start():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    tick = int(os.environ.get("SCHEDULER_TICK_MINUTES", "2"))
    _scheduler.add_job(dispatch_due_attempts, "interval", minutes=tick,
                       id="dispatch_due_attempts", next_run_time=datetime.now(timezone.utc))
    _scheduler.start()
    log.info("APScheduler started; tick=%s min", tick)
    return _scheduler


def stop():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
