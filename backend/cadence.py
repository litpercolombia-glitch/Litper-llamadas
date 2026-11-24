"""Cadence engine — builds the up-to-5-attempt plan for a queue item.

Rules (from spec):
  * Up to 5 attempts across up to 3 days.
  * Rotate windows: manana(9-11), mediodia(12-14), tarde(15-18), noche(18-20).
  * Never two attempts in the same window back-to-back.
  * Respect the carrier's `office_claim_max_days`.
    - 1 day  → compress the whole cadence into that day.
    - many   → spread across up to 3 days (capped).
    - None   → default to 3-day spread.
  * Attempts 1-3 = call. After 3 consecutive no-answers a WhatsApp is triggered as
    fallback (marked implicitly by attempt 4 being WhatsApp when the first 3 were
    'no_contesta'). Attempts 4-5 = call. Final WhatsApp on attempt 5.
    (Interpretation: attempt 5 always ends with a WhatsApp companion.)
  * Skip holidays.

For simplicity attempts 1-4 use channel 'call' and attempt 5 uses channel 'whatsapp'.
An extra WhatsApp fallback is *dynamically* triggered by the runtime engine when 3
consecutive no_contesta results are recorded; that logic lives in
`register_attempt_result` (routes/cadence.py).
"""
from __future__ import annotations
from datetime import datetime, date, timedelta, time
from typing import Iterable
from zoneinfo import ZoneInfo

from data import WINDOWS, HOLIDAYS_CO_2026, COUNTRY_TIMEZONES


WINDOW_ORDER = ["manana", "mediodia", "tarde", "noche"]


def _tz_for(country: str | None, tz_name: str | None = None) -> ZoneInfo:
    """Zona del país del pedido si se conoce; si no, la del perfil del cliente
    (`tz_name`); último recurso America/Bogota (comportamiento histórico)."""
    name = COUNTRY_TIMEZONES.get(country or "") or tz_name or "America/Bogota"
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 — zona inválida en el perfil: no romper
        return ZoneInfo("America/Bogota")


def _is_holiday(d: date, country: str | None = "CO") -> bool:
    """Solo tenemos el calendario de festivos de Colombia."""
    return country == "CO" and d in HOLIDAYS_CO_2026


def _next_business_day(d: date) -> date:
    d = d + timedelta(days=1)
    while _is_holiday(d):
        d += timedelta(days=1)
    return d


def _window_time(day: date, window: str, tz: ZoneInfo, offset_min: int = 0) -> datetime:
    start_h, _end_h = WINDOWS[window]
    return datetime.combine(day, time(hour=start_h, minute=offset_min), tzinfo=tz)


def build_plan(*, country: str | None, start_date: date,
               office_claim_max_days: int | None,
               tz_name: str | None = None) -> list[dict]:
    """Return a list of 5 attempt dicts: {attempt_number, channel, window, scheduled_at (UTC ISO)}.

    `tz_name` = zona horaria del perfil del cliente (se usa cuando el país del
    pedido no tiene zona conocida). Festivos: solo se saltan si country == "CO".
    """
    tz = _tz_for(country, tz_name)
    total_attempts = 5

    # Determine cadence layout: (day_offset, window) tuples of length 5.
    if office_claim_max_days == 1:
        # Compressed same-day cadence — hit all 4 windows in a single day,
        # then repeat the mediodia window as fifth attempt.
        layout = [(0, "manana"), (0, "mediodia"), (0, "tarde"),
                  (0, "noche"), (0, "mediodia")]
    elif office_claim_max_days == 2:
        layout = [(0, "manana"), (0, "tarde"), (0, "noche"),
                  (1, "mediodia"), (1, "tarde")]
    else:
        # 3+ day spread (also default when office claim is None).
        layout = [(0, "manana"), (0, "tarde"),
                  (1, "mediodia"), (1, "noche"),
                  (2, "tarde")]

    # Enforce "never two attempts in the same window back-to-back".
    _validate_no_back_to_back(layout)

    # Now materialise dates skipping holidays; never exceed office deadline.
    plan: list[dict] = []
    prev_key: tuple[date, str] | None = None
    for i, (day_off, window) in enumerate(layout):
        target_day = start_date + timedelta(days=day_off)
        while _is_holiday(target_day, country):
            target_day += timedelta(days=1)

        # Never schedule past the office claim deadline (if defined).
        if office_claim_max_days is not None:
            deadline = start_date + timedelta(days=office_claim_max_days)
            if target_day > deadline:
                target_day = deadline

        # Enforce spacing: if same (day, window) as prev, bump minutes.
        offset_min = 0
        if prev_key is not None and prev_key == (target_day, window):
            offset_min = 30
        prev_key = (target_day, window)

        scheduled = _window_time(target_day, window, tz, offset_min).astimezone(ZoneInfo("UTC"))
        channel = "whatsapp" if i == 4 else "call"  # attempt 5 = final WhatsApp
        plan.append({
            "attempt_number": i + 1,
            "channel": channel,
            "window": window,
            "scheduled_at": scheduled.isoformat(),
            "status": "pending",
        })

    assert len(plan) == total_attempts
    return plan


def _validate_no_back_to_back(layout: Iterable[tuple[int, str]]) -> None:
    prev_window = None
    for _day, w in layout:
        if w == prev_window:
            raise ValueError(f"Cadence layout has back-to-back windows: {w}")
        prev_window = w


def days_left(office_arrival_date: str, office_claim_max_days: int | None,
              now: datetime | None = None, tz_name: str | None = None) -> int | None:
    """Days remaining until the office claim deadline (never negative)."""
    if office_claim_max_days is None:
        return None
    arrival = date.fromisoformat(office_arrival_date[:10])
    deadline = arrival + timedelta(days=office_claim_max_days)
    today = (now or datetime.now(_tz_for(None, tz_name))).date()
    return max(0, (deadline - today).days)
