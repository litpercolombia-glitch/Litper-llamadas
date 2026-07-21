"""Optional Supabase (PostgREST) mirror — env-driven, non-blocking.

If SUPABASE_URL and either SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY are set,
every write inside the Hub also POSTs to the matching Supabase table. When the
service key is empty (initial state), sync silently no-ops so the Hub still
operates purely on Mongo.
"""
from __future__ import annotations
import logging
import os
from typing import Any
import httpx

log = logging.getLogger("supabase_sync")


def _configured() -> tuple[bool, str, str]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    return bool(url and key), url, key


async def upsert(table: str, row: dict[str, Any], on_conflict: str | None = None) -> dict:
    ok, url, key = _configured()
    if not ok:
        return {"ok": False, "skipped": True, "reason": "supabase not configured"}
    endpoint = f"{url}/rest/v1/{table}"
    if on_conflict:
        endpoint += f"?on_conflict={on_conflict}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(endpoint, headers=headers, json=row)
        return {"ok": 200 <= r.status_code < 300, "status": r.status_code, "body": r.text[:300]}
    except Exception as e:  # noqa: BLE001
        log.warning("supabase sync failed: %s", e)
        return {"ok": False, "error": str(e)}
