"""Routes: /metrics — comprehensive KPI dashboard for COD llamadas-a-oficina."""
from __future__ import annotations
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta, date
from fastapi import APIRouter, Depends, Query
from typing import Optional

from db import get_db
from deps import require_api_key
from cadence import days_left as _days_left
from data import semaphore_for

router = APIRouter(prefix="/metrics", tags=["metrics"],
                   dependencies=[Depends(require_api_key)])


# ---------- helpers ----------
def _env_float(k: str, default: float) -> float:
    try:
        return float(os.environ.get(k, default))
    except Exception:
        return default


def _cost_config():
    return {
        "twilio_per_min":     _env_float("TWILIO_COST_PER_MIN", 0.014),
        "elevenlabs_per_min": _env_float("ELEVENLABS_COST_PER_MIN", 0.30),
        "whatsapp_per_msg":   _env_float("WHATSAPP_COST_PER_MSG", 0.005),
        "llm_per_1k":         _env_float("LLM_COST_PER_1K", 0.003),
        "usd_to_cop":         _env_float("USD_TO_COP", 4200.0),
        "rto_baseline_pct":   _env_float("RTO_BASELINE_PCT", 30.0),
        "cod_margin_pct":     _env_float("COD_MARGIN_PCT", 30.0),
    }


def _iso(d: datetime | date) -> str:
    if isinstance(d, date) and not isinstance(d, datetime):
        d = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return d.isoformat()


def _status(value: float, target_min: float, target_max: float | None = None) -> str:
    """Traffic-light coloring vs target range."""
    if target_max is None:
        if value >= target_min:
            return "green"
        if value >= target_min * 0.7:
            return "amber"
        return "red"
    if value >= target_min:
        return "green"
    if value >= target_min * 0.6:
        return "amber"
    return "red"


def _pct(num: float, den: float) -> float:
    return round((num / den) * 100, 1) if den else 0.0


# ---------- endpoint ----------
@router.get("", summary="Full KPI dashboard: NORTE + funnel + WhatsApp + operación + costos.")
async def metrics(
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD, inclusive."),
    date_to:   Optional[str] = Query(None, description="ISO date YYYY-MM-DD, inclusive."),
    country:   Optional[str] = Query(None),
    carrier_slug: Optional[str] = Query(None),
):
    db = get_db()
    cfg = _cost_config()

    # Date range → default last 30 days
    today = datetime.now(timezone.utc).date()
    to_d = date.fromisoformat(date_to) if date_to else today
    from_d = date.fromisoformat(date_from) if date_from else (to_d - timedelta(days=29))
    from_iso = _iso(from_d)
    to_iso = _iso(datetime(to_d.year, to_d.month, to_d.day, 23, 59, 59, tzinfo=timezone.utc))

    # Base filter for queue/orders
    q_filter: dict = {}
    if country:
        q_filter["country"] = country
    if carrier_slug:
        q_filter["carrier_slug"] = carrier_slug
    # Note: queue.created_at filter applied per-metric; we don't want to filter all
    # for the "urgencia" section (that's always "current state").

    # ------ Load working sets ------
    queue_current = await db.call_queue.find(q_filter, {"_id": 0}).to_list(2000)
    queue_range_filter = {**q_filter,
                         "created_at": {"$gte": from_iso, "$lte": to_iso}}
    queue_range = await db.call_queue.find(queue_range_filter, {"_id": 0}).to_list(5000)
    schedules = await db.call_schedules.find({}, {"_id": 0}).to_list(5000)
    q_ids_in_range = {q["id"] for q in queue_range}
    scheds_in_range = [s for s in schedules if s.get("queue_id") in q_ids_in_range]

    # ------ GROUP A · NORTE ------
    # Recovery: queue items with status ∈ {confirmado, ya_recogio} out of total
    recovered = sum(1 for q in queue_range if q.get("status") in ("confirmado", "ya_recogio"))
    lost = sum(1 for q in queue_range if q.get("status") in ("rechazado", "escalado", "detenido"))
    total_range = len(queue_range)
    recovery_rate = _pct(recovered, total_range)

    orders = await db.orders.find(q_filter, {"_id": 0, "total_amount": 1, "id": 1,
                                             "created_at": 1}).to_list(5000)
    order_by_id = {o["id"]: o for o in orders}
    recovered_value = sum(order_by_id.get(q["order_id"], {}).get("total_amount", 0) or 0
                         for q in queue_range if q.get("status") in ("confirmado", "ya_recogio"))
    margin_recovered = recovered_value * (cfg["cod_margin_pct"] / 100.0)

    # Cost model — approximate
    all_attempts = [a for s in scheds_in_range for a in s.get("attempts", [])]
    done_calls = [a for a in all_attempts if a.get("status") == "done" and a.get("channel") == "call"]
    minutes = len(done_calls) * 2.0  # assume 2 min average per call
    msg_range = await db.message_log.find({"created_at": {"$gte": from_iso, "$lte": to_iso}},
                                           {"_id": 0, "created_at": 1, "channel": 1,
                                            "direction": 1, "provider": 1, "body": 1}).to_list(20000)
    msg_count = sum(1 for m in msg_range if m.get("channel") == "whatsapp")
    tokens_est = (sum(len(m.get("body", "") or "") for m in msg_range) + len(all_attempts) * 800) / 4
    twilio_cost = minutes * cfg["twilio_per_min"]
    elevenlabs_cost = minutes * cfg["elevenlabs_per_min"]
    whatsapp_cost = msg_count * cfg["whatsapp_per_msg"]
    llm_cost = (tokens_est / 1000.0) * cfg["llm_per_1k"]
    total_cost_usd = twilio_cost + elevenlabs_cost + whatsapp_cost + llm_cost
    total_cost_cop = total_cost_usd * cfg["usd_to_cop"]
    cpr_cop = round(total_cost_cop / recovered, 0) if recovered else 0
    roi = round(margin_recovered - total_cost_cop, 0)

    # RTO reduction — baseline vs observed
    rto_current = _pct(lost, total_range)
    rto_reduction = round(max(0.0, cfg["rto_baseline_pct"] - rto_current), 1)

    norte = {
        "recovery_rate": {"value": recovery_rate, "target": 60, "unit": "%",
                          "status": _status(recovery_rate, 60)},
        "rto_reduction": {"value": rto_reduction, "baseline": cfg["rto_baseline_pct"],
                          "current": rto_current, "unit": "%",
                          "status": _status(rto_reduction, 15)},
        "cpr_cop": {"value": cpr_cop, "unit": "COP",
                    "target_max": 5000, "status": "green" if cpr_cop < 5000 else "amber" if cpr_cop < 10000 else "red"},
        "roi_cop": {"value": roi, "recovered_value_cop": round(recovered_value, 0),
                    "margin_recovered_cop": round(margin_recovered, 0),
                    "total_cost_cop": round(total_cost_cop, 0),
                    "unit": "COP",
                    "status": "green" if roi > 0 else "red"},
    }

    # ------ GROUP B · FUNNEL / EMBUDO ------
    programados = len(all_attempts)  # planned attempts
    marcados = sum(1 for a in all_attempts if a.get("status") in ("dispatched", "done"))
    done_all = [a for a in all_attempts if a.get("status") == "done"]
    contact_results = ("confirmado", "ya_recogio", "extension", "rechaza")
    contactados = sum(1 for a in done_all if a.get("result") in contact_results)
    confirmados = sum(1 for a in done_all if a.get("result") in ("confirmado", "extension"))
    recogidos = sum(1 for a in done_all if a.get("result") == "ya_recogio")
    no_answer = sum(1 for a in done_all if a.get("result") == "no_contesta")
    wrong = sum(1 for a in done_all if a.get("result") == "numero_incorrecto")

    # Avg attempts to first contact
    attempts_to_contact = []
    for s in scheds_in_range:
        for a in s.get("attempts", []):
            if a.get("status") == "done" and a.get("result") in contact_results:
                attempts_to_contact.append(a.get("attempt_number", 1))
                break
    avg_attempts = round(sum(attempts_to_contact) / len(attempts_to_contact), 2) if attempts_to_contact else 0

    connect_rate = _pct(contactados, len(done_all))
    right_party = _pct(confirmados + recogidos, contactados) if contactados else 0
    confirmation_rate = _pct(confirmados + recogidos, contactados) if contactados else 0

    funnel = {
        "connect_rate":     {"value": connect_rate, "target_min": 25, "target_max": 45, "unit": "%",
                             "status": _status(connect_rate, 25)},
        "right_party":      {"value": right_party, "target_min": 60, "unit": "%",
                             "status": _status(right_party, 60)},
        "confirmation_rate":{"value": confirmation_rate, "target_min": 40, "unit": "%",
                             "status": _status(confirmation_rate, 40)},
        "avg_attempts_to_contact": {"value": avg_attempts, "target_max": 3,
                                    "status": "green" if avg_attempts and avg_attempts <= 3 else "amber" if avg_attempts else "gris"},
        "no_answer_pct":    {"value": _pct(no_answer, len(done_all)), "unit": "%",
                             "status": "gris"},
        "wrong_number_pct": {"value": _pct(wrong, len(done_all)), "unit": "%",
                             "status": "red" if _pct(wrong, len(done_all)) > 5 else "green"},
        "stages": [
            {"name": "Programados",  "count": programados},
            {"name": "Marcados",     "count": marcados},
            {"name": "Contactados",  "count": contactados},
            {"name": "Confirmados",  "count": confirmados + recogidos},
            {"name": "Recogidos",    "count": recogidos},
        ],
    }

    # ------ GROUP C · WHATSAPP ------
    wa_msgs = [m for m in msg_range if m.get("channel") == "whatsapp"]
    outbound = [m for m in wa_msgs if m.get("direction") == "outbound"]
    inbound  = [m for m in wa_msgs if m.get("direction") == "inbound"]
    delivered = sum(1 for m in outbound if m.get("status") in ("sent", "delivered"))
    read_msgs = sum(1 for m in outbound if m.get("status") == "delivered")  # proxy — Chatea Pro delivery receipt maps here
    read_rate = _pct(read_msgs, delivered)
    response_rate = _pct(len(inbound), len(outbound))

    # Conversion to confirmation — % of queue items with an inbound WA followed by confirmado/ya_recogio
    inbound_phones = {m.get("phone") for m in inbound}
    conv_to_confirm = 0
    conv_denom = 0
    for q in queue_range:
        order = order_by_id.get(q["order_id"])
        if not order:
            continue
        # Skip if we don't have message log; we approximate with any inbound.
        conv_denom += 1
    # Simpler: of inbound-received phones, how many map to queue items now confirmed?
    phones_to_status = {}
    order_ids_by_phone: dict[str, list[str]] = defaultdict(list)
    ords = await db.orders.find({"customer_phone": {"$in": list(inbound_phones)}} if inbound_phones else {"_id": 0},
                                {"_id": 0, "customer_phone": 1, "id": 1}).to_list(2000)
    for o in ords:
        order_ids_by_phone[o["customer_phone"]].append(o["id"])
    for p in inbound_phones:
        for oid in order_ids_by_phone.get(p, []):
            for q in queue_range:
                if q["order_id"] == oid:
                    phones_to_status.setdefault(p, q.get("status"))
    converted = sum(1 for s in phones_to_status.values() if s in ("confirmado", "ya_recogio"))
    conv_rate = _pct(converted, len(phones_to_status)) if phones_to_status else 0

    # Avg response time (minutes) — inbound.created_at − nearest previous outbound.created_at for same phone
    response_deltas: list[float] = []
    by_phone_out: dict[str, list[datetime]] = defaultdict(list)
    for m in outbound:
        try:
            by_phone_out[m["phone"]].append(datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")))
        except Exception:
            continue
    for lst in by_phone_out.values():
        lst.sort()
    for m in inbound:
        try:
            t = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        outs = by_phone_out.get(m.get("phone"), [])
        prev = [o for o in outs if o <= t]
        if prev:
            response_deltas.append((t - prev[-1]).total_seconds() / 60.0)
    avg_response_min = round(sum(response_deltas) / len(response_deltas), 1) if response_deltas else 0

    whatsapp = {
        "sent": len(outbound),
        "delivered": delivered,
        "received": len(inbound),
        "read_rate":     {"value": read_rate, "target_min": 80, "target_max": 95, "unit": "%",
                          "status": _status(read_rate, 80)},
        "response_rate": {"value": response_rate, "target_min": 15, "target_max": 55, "unit": "%",
                          "status": _status(response_rate, 15)},
        "conversion_to_confirmation": {"value": conv_rate, "target_min": 30, "unit": "%",
                                       "status": _status(conv_rate, 30)},
        "avg_response_min": {"value": avg_response_min, "target_max": 5,
                             "status": "green" if avg_response_min and avg_response_min <= 5 else "amber" if avg_response_min else "gris",
                             "note": "Responder en <5 min = 21x más conversión."},
    }

    # ------ GROUP D · OPERACIÓN / URGENCIA ------
    by_sem: Counter = Counter()
    vencen_hoy: Counter = Counter()
    vencen_manana: Counter = Counter()
    for q in queue_current:
        dl = _days_left(q["office_arrival_date"], q.get("office_claim_max_days"))
        sem = semaphore_for(q.get("office_claim_max_days"), dl)
        by_sem[sem] += 1
        if q.get("status") in ("confirmado", "ya_recogio", "rechazado", "detenido"):
            continue
        if dl is not None and dl <= 0:
            vencen_hoy[q["carrier_slug"]] += 1
        elif dl == 1:
            vencen_manana[q["carrier_slug"]] += 1

    escalados_range = sum(1 for q in queue_range if q.get("status") == "escalado")
    escalation_rate = _pct(escalados_range, total_range)

    tasks_range = await db.customer_tasks.find(
        {"created_at": {"$gte": from_iso, "$lte": to_iso}},
        {"_id": 0, "type": 1, "status": 1}).to_list(5000)
    tasks_by_type = Counter(t.get("type", "otro") for t in tasks_range)
    tasks_open = sum(1 for t in tasks_range if t.get("status") in ("open", "in_progress"))

    operacion = {
        "by_semaphore": [
            {"name": "rojo", "count": by_sem.get("rojo", 0)},
            {"name": "amarillo", "count": by_sem.get("amarillo", 0)},
            {"name": "verde", "count": by_sem.get("verde", 0)},
            {"name": "gris", "count": by_sem.get("gris", 0)},
        ],
        "vencen_hoy":    [{"carrier_slug": k, "count": v} for k, v in vencen_hoy.most_common()],
        "vencen_manana": [{"carrier_slug": k, "count": v} for k, v in vencen_manana.most_common()],
        "escalation_rate": {"value": escalation_rate, "target_max": 20, "unit": "%",
                            "status": _status(20 - escalation_rate, 5)},
        "tasks_by_type": [{"type": k, "count": v} for k, v in tasks_by_type.most_common()],
        "tasks_open": tasks_open,
    }

    # ------ GROUP E · COSTOS por día ------
    days: dict[str, dict] = {}
    def _bucket(d_key: str):
        return days.setdefault(d_key, {"date": d_key, "twilio_cop": 0.0, "elevenlabs_cop": 0.0,
                                      "whatsapp_cop": 0.0, "llm_cop": 0.0, "total_cop": 0.0,
                                      "minutes": 0.0, "messages": 0, "attempts": 0})

    for s in scheds_in_range:
        for a in s.get("attempts", []):
            ex = a.get("executed_at")
            if not ex or a.get("status") != "done":
                continue
            day = ex[:10]
            if day < from_d.isoformat() or day > to_d.isoformat():
                continue
            b = _bucket(day)
            b["attempts"] += 1
            if a.get("channel") == "call":
                mins = 2.0
                b["minutes"] += mins
                b["twilio_cop"] += mins * cfg["twilio_per_min"] * cfg["usd_to_cop"]
                b["elevenlabs_cop"] += mins * cfg["elevenlabs_per_min"] * cfg["usd_to_cop"]
    for m in wa_msgs:
        day = (m.get("created_at") or "")[:10]
        if not day or day < from_d.isoformat() or day > to_d.isoformat():
            continue
        b = _bucket(day)
        b["messages"] += 1
        b["whatsapp_cop"] += cfg["whatsapp_per_msg"] * cfg["usd_to_cop"]

    # Fill missing days with zeros for a nice chart
    d = from_d
    while d <= to_d:
        _bucket(d.isoformat())
        d += timedelta(days=1)

    # LLM cost approximation: distribute uniformly across days as a small placeholder
    llm_cop_daily = (llm_cost * cfg["usd_to_cop"]) / max(1, (to_d - from_d).days + 1)
    for b in days.values():
        b["llm_cop"] = round(llm_cop_daily, 2)
        b["twilio_cop"] = round(b["twilio_cop"], 2)
        b["elevenlabs_cop"] = round(b["elevenlabs_cop"], 2)
        b["whatsapp_cop"] = round(b["whatsapp_cop"], 2)
        b["total_cop"] = round(b["twilio_cop"] + b["elevenlabs_cop"]
                              + b["whatsapp_cop"] + b["llm_cop"], 2)
    daily = sorted(days.values(), key=lambda x: x["date"])

    costos = {
        "days": daily,
        "totals": {
            "twilio_cop":     round(sum(x["twilio_cop"]     for x in daily), 2),
            "elevenlabs_cop": round(sum(x["elevenlabs_cop"] for x in daily), 2),
            "whatsapp_cop":   round(sum(x["whatsapp_cop"]   for x in daily), 2),
            "llm_cop":        round(sum(x["llm_cop"]        for x in daily), 2),
            "total_cop":      round(sum(x["total_cop"]      for x in daily), 2),
            "minutes":        round(sum(x["minutes"]        for x in daily), 1),
            "messages":       sum(x["messages"]     for x in daily),
        },
        "config": cfg,
    }

    # ------ TREND 14 días ------
    trend_days = 14
    tr_from = today - timedelta(days=trend_days - 1)
    trend_recovery = []
    trend_cpr = []
    for i in range(trend_days):
        day = tr_from + timedelta(days=i)
        day_iso = day.isoformat()
        recovered_d = 0
        total_d = 0
        cost_d = 0.0
        for q in queue_range:
            if (q.get("created_at") or "")[:10] == day_iso:
                total_d += 1
                if q.get("status") in ("confirmado", "ya_recogio"):
                    recovered_d += 1
        for b in daily:
            if b["date"] == day_iso:
                cost_d = b["total_cop"]
                break
        rr = _pct(recovered_d, total_d)
        cpr = round(cost_d / recovered_d, 0) if recovered_d else 0
        trend_recovery.append({"date": day_iso, "value": rr})
        trend_cpr.append({"date": day_iso, "value": cpr})

    trend = {"recovery_rate_14d": trend_recovery, "cpr_14d": trend_cpr}

    # ------ Also legacy top-level keys used by old dashboard ------
    since24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    attempts_today_all = [a for s in schedules for a in s.get("attempts", [])
                         if (a.get("executed_at") or "") >= since24]
    messages_24h = await db.message_log.count_documents({"created_at": {"$gte": since24}})

    queue_by_status = dict(Counter(q.get("status", "unknown") for q in queue_current))
    return {
        "filters": {"date_from": from_d.isoformat(), "date_to": to_d.isoformat(),
                   "country": country, "carrier_slug": carrier_slug},
        "norte": norte,
        "funnel": funnel,
        "whatsapp": whatsapp,
        "operacion": operacion,
        "costos": costos,
        "trend": trend,
        # Legacy compat with v1.0 dashboard
        "queue_by_status": queue_by_status,
        "queue_total": len(queue_current),
        "orders_total": len(orders),
        "attempts_today": len(attempts_today_all),
        "completed_today": sum(1 for a in attempts_today_all if a.get("status") == "done"),
        "contact_rate_pct": funnel["connect_rate"]["value"],
        "tasks_open": tasks_open,
        "messages_24h": messages_24h,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
