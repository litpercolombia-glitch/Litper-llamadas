"""Routes: /metrics — indicadores del negocio.

Los costos y el retorno son ESTIMADOS con supuestos (margen, tasa base de
pérdida, tipo de cambio, minutos por llamada, costos unitarios). La respuesta
los declara bajo `supuestos` para que la interfaz los muestre. Los montos van
en la MONEDA DEL PERFIL del cliente (`supuestos.moneda`).

CLAVES: los nombres vigentes son neutros (norte.cpr, norte.roi, roi.total_cost,
costos.totals.llamadas / telefonia / voz / whatsapp / ia / total). Las claves
antiguas terminadas en `_cop` (cpr_cop, roi_cop, total_cop, twilio_cop…) se
conservan SOLO como alias con el mismo valor para no romper integraciones
viejas; su valor está en `supuestos.moneda`, no necesariamente en pesos."""
from __future__ import annotations
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta, date
from fastapi import APIRouter, Depends, Query
from typing import Optional

from db import get_db
from deps import get_org, require_api_key
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


def fx_for(moneda: str, cfg: dict) -> tuple[float, str, bool]:
    """(tipo de cambio USD→moneda, moneda efectiva de los montos, ¿definido?).

    Los costos unitarios están en USD. Se convierten a la moneda del perfil con
    USD_TO_<MONEDA> del entorno (USD_TO_COP trae un valor por defecto). Si no
    hay tipo de cambio para esa moneda NO se inventa: los montos quedan en USD
    y se avisa (`tipo_cambio_definido: false`)."""
    moneda = (moneda or "USD").upper()
    if moneda == "USD":
        return 1.0, "USD", True
    if moneda == "COP":
        return cfg["usd_to_cop"], "COP", True
    raw = os.environ.get(f"USD_TO_{moneda}", "").strip()
    try:
        rate = float(raw)
        if rate > 0:
            return rate, moneda, True
    except ValueError:
        pass
    return 1.0, "USD", False


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


# Clave neutra → clave antigua (alias). Las neutras son las vigentes.
COST_ALIASES = {"telefonia": "twilio_cop", "voz": "elevenlabs_cop",
                "whatsapp": "whatsapp_cop", "ia": "llm_cop", "total": "total_cop"}


def _neutral(b: dict) -> dict:
    """Añade a un bloque de costos las claves neutras (telefonia, voz, llamadas,
    whatsapp, ia, total) a partir de las antiguas `*_cop`, que quedan como alias."""
    for new, old in COST_ALIASES.items():
        b[new] = b.get(old, 0)
    b["llamadas"] = round(b["telefonia"] + b["voz"], 2)
    return b


# ---------- endpoint ----------
@router.get("", summary="Full KPI dashboard: NORTE + funnel + WhatsApp + operación + costos.")
async def metrics(
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD, inclusive."),
    date_to:   Optional[str] = Query(None, description="ISO date YYYY-MM-DD, inclusive."),
    country:   Optional[str] = Query(None),
    carrier_slug: Optional[str] = Query(None),
    org: str = Depends(get_org),
):
    return await compute_metrics(org, date_from, date_to, country, carrier_slug)


async def compute_metrics(org: str, date_from: Optional[str] = None,
                          date_to: Optional[str] = None,
                          country: Optional[str] = None,
                          carrier_slug: Optional[str] = None) -> dict:
    """KPIs de UN cliente. Función plana (sin FastAPI) para poder llamarla desde
    el scheduler y las herramientas del agente pasando siempre el org."""
    db = get_db()
    cfg = _cost_config()
    from routes.org_profile import get_profile
    profile = await get_profile(org)
    fx, moneda, fx_ok = fx_for(profile.get("moneda"), cfg)
    # A partir de aquí el "tipo de cambio" es el de la moneda del perfil.
    cfg = {**cfg, "usd_to_cop": fx, "fx": fx, "moneda": moneda}
    minutos_por_llamada = 2.0
    cpr_target = round(5000 / 4200 * fx, 2)       # ≈ 1,19 USD por recuperado
    supuestos = {
        "moneda": moneda,
        "moneda_perfil": (profile.get("moneda") or "USD").upper(),
        "tipo_cambio_usd": fx,
        "tipo_cambio_definido": fx_ok,
        "margen_pct": cfg["cod_margin_pct"],
        "tasa_base_pct": cfg["rto_baseline_pct"],
        "minutos_por_llamada": minutos_por_llamada,
        "costos_unitarios_usd": {
            "telefonia_por_min": cfg["twilio_per_min"],
            "voz_ia_por_min":    cfg["elevenlabs_per_min"],
            "whatsapp_por_msg":  cfg["whatsapp_per_msg"],
            "llm_por_1k_tokens": cfg["llm_per_1k"],
        },
        "costo_por_recuperado_objetivo": cpr_target,
        "son_estimaciones": True,
        "nota": ("Costos y retorno ESTIMADOS con estos supuestos (no son facturación real). "
                 "El margen, la tasa base, el tipo de cambio y los costos unitarios son "
                 "valores de referencia de la plataforma; si los tuyos son distintos, "
                 "pide a soporte que los ajuste."
                 + ("" if fx_ok else f" No hay tipo de cambio para {profile.get('moneda')}: "
                                     "los costos se muestran en USD y el retorno NO es confiable.")),
    }

    # Date range → default last 30 days
    today = datetime.now(timezone.utc).date()
    to_d = date.fromisoformat(date_to) if date_to else today
    from_d = date.fromisoformat(date_from) if date_from else (to_d - timedelta(days=29))
    from_iso = _iso(from_d)
    to_iso = _iso(datetime(to_d.year, to_d.month, to_d.day, 23, 59, 59, tzinfo=timezone.utc))

    # Base filter for queue/orders
    q_filter: dict = {"org_id": org}
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
    schedules = await db.call_schedules.find({"org_id": org}, {"_id": 0}).to_list(5000)
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
    minutes = len(done_calls) * minutos_por_llamada  # supuesto: ver `supuestos`
    msg_range = await db.message_log.find({"org_id": org,
                                           "created_at": {"$gte": from_iso, "$lte": to_iso}},
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
    nd = 0 if moneda == "COP" else 2          # decimales según la moneda
    cpr_cop = round(total_cost_cop / recovered, nd) if recovered else 0
    roi = round(margin_recovered - total_cost_cop, nd)

    # RTO reduction — baseline vs observed
    rto_current = _pct(lost, total_range)
    rto_reduction = round(max(0.0, cfg["rto_baseline_pct"] - rto_current), 1)

    norte = {
        "recovery_rate": {"value": recovery_rate, "target": 60, "unit": "%",
                          "status": _status(recovery_rate, 60)},
        "rto_reduction": {"value": rto_reduction, "baseline": cfg["rto_baseline_pct"],
                          "current": rto_current, "unit": "%",
                          "status": _status(rto_reduction, 15)},
        "cpr": {"value": cpr_cop, "unit": moneda,
                "target_max": cpr_target,
                "status": "green" if cpr_cop < cpr_target else "amber" if cpr_cop < cpr_target * 2 else "red"},
        "roi": {"value": roi, "recovered_value": round(recovered_value, 0),
                "margin_recovered": round(margin_recovered, 0),
                "total_cost": round(total_cost_cop, 0),
                "unit": moneda,
                # sin tipo de cambio, valor recuperado y costo están en monedas distintas
                "confiable": fx_ok,
                "status": "green" if roi > 0 else "red"},
    }
    # Alias antiguos (mismo valor, en `supuestos.moneda`).
    norte["roi"].update({"recovered_value_cop": norte["roi"]["recovered_value"],
                         "margin_recovered_cop": norte["roi"]["margin_recovered"],
                         "total_cost_cop": norte["roi"]["total_cost"]})
    norte["cpr_cop"], norte["roi_cop"] = norte["cpr"], norte["roi"]

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
    ords = await db.orders.find({"org_id": org,
                                 "customer_phone": {"$in": list(inbound_phones)}},
                                {"_id": 0, "customer_phone": 1, "id": 1}).to_list(2000) \
        if inbound_phones else []
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
        {"org_id": org, "created_at": {"$gte": from_iso, "$lte": to_iso}},
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
        _neutral(b)
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
        "moneda": moneda,
        "son_estimaciones": True,
    }
    _neutral(costos["totals"])

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
    messages_24h = await db.message_log.count_documents(
        {"org_id": org, "created_at": {"$gte": since24}})

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
        # Supuestos con los que se estimaron costos y retorno (mostrarlos en la UI).
        "supuestos": supuestos,
        "moneda": moneda,
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
