"""Background dispatcher: every N minutes, mark due attempts as dispatched.

We don't actually place VAPI calls or WhatsApp sends here — that is done by the
external AI agent that consumes this Hub. This job just flips 'pending' →
'dispatched' when an attempt's scheduled_at is due, and moves the queue item
forward. WhatsApp attempts also emit a real Chatea Pro send.

Zynex OS v2 adds two more jobs:
  • novedades_sweep — every 15 min, re-classify the semaphore for every
    active queue item and record the count per bucket.
  • daily_ceo_report — cada día a las 08:00 HORA LOCAL de cada negocio (zona
    horaria de su perfil; DAILY_REPORT_HOUR cambia la hora), guarda los
    indicadores NORTE en `ceo_reports` como rastro de auditoría.

AISLAMIENTO: todos los jobs procesan POR CLIENTE. Cada documento lleva su
org_id y se propaga a cada lectura/escritura derivada (pedido, reglas de
WhatsApp, ventana 24h, bitácora). Nunca se mezclan datos de dos clientes;
los documentos antiguos sin org_id se tratan como org "default".
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from db import get_db
from chatea import client_for as chatea_for

log = logging.getLogger("scheduler")

DEFAULT_ORG = "default"


def _org_of(doc: dict) -> str:
    return doc.get("org_id") or DEFAULT_ORG


async def dispatch_due_attempts():
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.call_schedules.find({"attempts.scheduled_at": {"$lte": now_iso},
                                     "attempts.status": "pending"},
                                    {"_id": 0})
    async for sched in cursor:
        org = _org_of(sched)          # todo lo derivado de este plan es de ESTE cliente
        changed = False
        for att in sched["attempts"]:
            if att["status"] != "pending":
                continue
            if att["scheduled_at"] > now_iso:
                continue
            # Only auto-dispatch WhatsApp; calls are executed by external AI agent.
            if att["channel"] == "whatsapp":
                chatea = await chatea_for(org)   # cuenta de ESTE cliente
                phone = await _phone_for_queue(sched["queue_id"], org)
                order = await _order_for_queue(sched["queue_id"], org)
                product_name = ""
                customer_name = ""
                days_left = 0
                if order:
                    product_name = (order.get("products_display")
                                    or (order.get("items") or [{}])[0].get("product", "")
                                    or "tu pedido")
                    customer_name = order.get("customer_name", "") or ""
                # Fetch queue for days_left (semaphore-driven WA rule)
                q_doc = await db.call_queue.find_one({"id": sched["queue_id"], "org_id": org},
                                                     {"_id": 0, "days_left": 1})
                if q_doc and q_doc.get("days_left") is not None:
                    try: days_left = int(q_doc["days_left"])
                    except Exception: days_left = 0
                body_text = await followup_text(org, customer_name, product_name)

                # WhatsApp rule: 0–3 días → reclamo_oficina · +3 → no_oficina
                from routes.whatsapp import resolve_rule_for_days_left, window_open
                rule = await resolve_rule_for_days_left(days_left, org)
                template_name = None
                if rule:
                    template_name = rule.get("template_name")

                # META 24h window enforcement:
                # If the customer has NOT replied in the last 24h → we MUST use a
                # template (approved by Meta). Free-form messages will be rejected.
                is_open, _ = await window_open(phone, org) if phone else (False, None)

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
                        "org_id": org,
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
            await db.call_schedules.update_one({"id": sched["id"], "org_id": org},
                                               {"$set": {"attempts": sched["attempts"]}})
            await db.call_queue.update_one({"id": sched["queue_id"], "org_id": org},
                                           {"$set": {"status": "in_progress",
                                                     "updated_at": now_iso}})


async def followup_text(org: str, customer_name: str = "", product_name: str = "") -> str:
    """Texto del WhatsApp de seguimiento. NEUTRO por defecto (sirve a cualquier
    negocio y usa su marca); la versión "reclamo en oficina" solo se usa si el
    cliente instaló el paquete cod_colombia."""
    from packs import installed_packs
    from routes.org_profile import get_profile
    greet = f"Hola {customer_name}, " if customer_name else "Hola, "
    if "cod_colombia" in await installed_packs(org):
        return (f"{greet}seguimos pendientes de tu pedido de "
                f"{product_name or 'la orden'} en oficina. "
                f"¿Puedes confirmar si lo recogerás hoy?")
    empresa = (await get_profile(org)).get("empresa") or ""
    de = f" de {empresa}" if empresa else ""
    return (f"{greet}te escribimos{de} para hacer seguimiento a "
            f"{product_name or 'tu solicitud'}. ¿Nos confirmas por este medio, por favor?")


async def _phone_for_queue(queue_id: str, org: str) -> str | None:
    o = await _order_for_queue(queue_id, org)
    return o.get("customer_phone") if o else None


async def _order_for_queue(queue_id: str, org: str) -> dict | None:
    db = get_db()
    q = await db.call_queue.find_one({"id": queue_id, "org_id": org},
                                     {"_id": 0, "order_id": 1})
    if not q:
        return None
    return await db.orders.find_one({"id": q["order_id"], "org_id": org}, {"_id": 0})


async def _org_ids() -> list[str]:
    """Clientes conocidos: los de `orgs` + "default" (datos previos al multi-cliente)."""
    ids = [o["id"] async for o in get_db().orgs.find({}, {"_id": 0, "id": 1}) if o.get("id")]
    return list(dict.fromkeys([DEFAULT_ORG, *ids]))


def _uuid():
    import uuid
    return str(uuid.uuid4())


_scheduler: AsyncIOScheduler | None = None


async def novedades_sweep():
    """Re-classify semaphore for every active queue item and log the counts.
    Un tick por cliente: los conteos de un org nunca incluyen pedidos de otro."""
    from cadence import days_left as _days_left
    from data import semaphore_for
    db = get_db()
    rows = await db.call_queue.find(
        {"status": {"$in": ["pending", "in_progress"]}},
        {"_id": 0, "id": 1, "org_id": 1, "office_arrival_date": 1,
         "office_claim_max_days": 1, "days_left": 1, "semaphore": 1}
    ).to_list(2000)
    per_org: dict[str, dict] = {}
    for r in rows:
        org = _org_of(r)
        buckets = per_org.setdefault(org, {"rojo": 0, "amarillo": 0, "verde": 0, "gris": 0})
        dl = _days_left(r.get("office_arrival_date"),
                        r.get("office_claim_max_days"))
        sem = semaphore_for(r.get("office_claim_max_days"), dl)
        buckets[sem] = buckets.get(sem, 0) + 1
        if r.get("days_left") != dl or r.get("semaphore") != sem:
            await db.call_queue.update_one(
                {"id": r["id"], "org_id": r.get("org_id")},
                {"$set": {"days_left": dl, "semaphore": sem,
                          "updated_at": datetime.now(timezone.utc).isoformat()}})
    for org, buckets in per_org.items():
        await db.novedades_ticks.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(), "org_id": org,
            "buckets": buckets, "total": sum(buckets.values()),
        })
    log.info("novedades_sweep: %s active items in %s orgs", len(rows), len(per_org))


REPORT_HOUR_DEFAULT = 8      # hora LOCAL del negocio a la que sale su reporte diario


def report_hour() -> int:
    try:
        return max(0, min(23, int(os.environ.get("DAILY_REPORT_HOUR", REPORT_HOUR_DEFAULT))))
    except ValueError:
        return REPORT_HOUR_DEFAULT


def is_report_hour(tz_name: str | None, now_utc: datetime | None = None,
                   hour: int | None = None) -> bool:
    """¿Es la hora del reporte diario en la zona horaria `tz_name`? (pura)"""
    from routes.org_profile import tz_of
    now_utc = now_utc or datetime.now(timezone.utc)
    local = now_utc.astimezone(tz_of({"zona_horaria": tz_name}))
    # minuto < 30: el job corre dos veces por hora (para zonas con desfase de
    # 30/45 min) pero cada cliente entra una sola vez.
    return local.hour == (report_hour() if hour is None else hour) and local.minute < 30


async def _orgs_due(now_utc: datetime | None = None) -> list[tuple[str, str]]:
    """[(org, fecha_local)] de los clientes para los que AHORA es la hora del
    reporte según la zona horaria de SU perfil."""
    from routes.org_profile import get_profile, tz_of
    now_utc = now_utc or datetime.now(timezone.utc)
    out = []
    for org in await _org_ids():
        profile = await get_profile(org)
        if is_report_hour(profile.get("zona_horaria"), now_utc):
            out.append((org, now_utc.astimezone(tz_of(profile)).date().isoformat()))
    return out


async def daily_ceo_report(now_utc: datetime | None = None):
    """Corre cada hora: genera el reporte de los clientes cuya hora local es la
    del reporte (solo clientes con pedidos o cola)."""
    for org, local_day in await _orgs_due(now_utc):
        await ceo_report_for_org(org, skip_empty=True, day=local_day)


async def ceo_report_for_org(org: str, skip_empty: bool = False, day: str | None = None):
    """Snapshot de los indicadores de UN cliente en `ceo_reports` (idempotente por día)."""
    db = get_db()
    from routes.metrics import compute_metrics
    try:
        m = await compute_metrics(org)
    except Exception as e:
        log.warning("daily_ceo_report[%s]: metrics call failed: %s", org, e)
        return
    if skip_empty and not (m.get("orders_total") or m.get("queue_total")):
        return
    if not day:
        from routes.org_profile import get_profile, tz_of
        day = datetime.now(tz_of(await get_profile(org))).date().isoformat()
    today = day
    doc = {
        "id": today,
        "org_id": org,
        "date": today,
        "norte":     m.get("norte"),
        "operacion": m.get("operacion"),
        "costos":    m.get("costos"),
        "supuestos": m.get("supuestos"),
        "queue_total":   m.get("queue_total"),
        "orders_total":  m.get("orders_total"),
        "generated_at":  datetime.now(timezone.utc).isoformat(),
    }
    await db.ceo_reports.update_one({"org_id": org, "id": today}, {"$set": doc}, upsert=True)
    log.info("daily_ceo_report generated for %s (%s)", today, org)


async def daily_ceo_report_wa():
    """Envía por WhatsApp el reporte del día a quien lo configuró. Corre cada
    hora en el minuto 15 (15 min después de `daily_ceo_report`) y solo para los
    clientes cuya hora local es la del reporte."""
    from routes.agents import ceo_report_send_wa, _get_ceo_wa_target
    for org, _day in await _orgs_due():
        if not await _get_ceo_wa_target(org):
            continue                      # este cliente no pidió el envío
        try:
            r = await ceo_report_send_wa(org)
            log.info("daily_ceo_report_wa[%s]: sent=%s", org, r.get("ok"))
        except Exception as e:
            log.warning("daily_ceo_report_wa[%s] skipped: %s", org, e)


def start():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    tick = int(os.environ.get("SCHEDULER_TICK_MINUTES", "2"))
    _scheduler.add_job(dispatch_due_attempts, "interval", minutes=tick,
                       id="dispatch_due_attempts", next_run_time=datetime.now(timezone.utc))
    _scheduler.add_job(novedades_sweep, "interval", minutes=15,
                       id="novedades_sweep",
                       next_run_time=datetime.now(timezone.utc))
    # Reporte diario a las 08:00 HORA LOCAL de cada negocio (zona horaria de su
    # perfil; DAILY_REPORT_HOUR la cambia). Por eso el job corre cada hora y
    # decide por cliente. Zonas con desfase de media hora salen en su hora :30.
    _scheduler.add_job(daily_ceo_report, CronTrigger(minute="0,30", timezone="UTC"),
                       id="daily_ceo_report")
    # 15 min después: envío por WhatsApp (solo si el cliente configuró destino).
    _scheduler.add_job(daily_ceo_report_wa, CronTrigger(minute="15,45", timezone="UTC"),
                       id="daily_ceo_report_wa")
    _scheduler.start()
    log.info("APScheduler started; dispatch tick=%s min · novedades every 15 min · reporte diario a las %s:00 hora local de cada negocio", tick, report_hour())
    return _scheduler


def stop():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
