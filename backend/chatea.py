"""Chatea Pro WhatsApp client — configurable via env, real-endpoint-ready.

The public docs for "Chatea Pro" are not openly discoverable at the time of writing.
We therefore expose two operations with a clean abstraction so the exact URL/paths
can be corrected via .env without touching code:

    - send_message(phone, text)           -> POST {BASE_URL}{SEND_MESSAGE_PATH}
    - send_template(phone, name, params)  -> POST {BASE_URL}{SEND_TEMPLATE_PATH}
    - test_connection()                   -> GET  {BASE_URL}{TEST_PATH}

Auth header defaults to `Authorization: Bearer <CHATEA_PRO_API_KEY>`, which is the
most common WhatsApp-platform convention. Override behavior by tweaking env or
subclassing.
"""
from __future__ import annotations
import logging
import os
from typing import Any
import httpx

log = logging.getLogger("chatea_pro")


class ChateaProClient:
    def __init__(self):
        self.api_key = os.environ.get("CHATEA_PRO_API_KEY", "")
        self.base_url = os.environ.get("CHATEA_PRO_BASE_URL",
                                       "https://api.chateapro.app").rstrip("/")
        self.send_message_path = os.environ.get("CHATEA_PRO_SEND_MESSAGE_PATH",
                                                "/api/v1/messages/send")
        self.send_template_path = os.environ.get("CHATEA_PRO_SEND_TEMPLATE_PATH",
                                                 "/api/v1/messages/template")
        self.test_path = os.environ.get("CHATEA_PRO_TEST_PATH", "/api/v1/account")
        if not self.api_key:
            log.warning("CHATEA_PRO_API_KEY is empty — outbound WhatsApp will fail.")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }

    async def send_message(self, phone: str, text: str) -> dict[str, Any]:
        url = f"{self.base_url}{self.send_message_path}"
        payload = {"to": phone, "type": "text", "text": {"body": text}}
        return await self._post(url, payload)

    async def send_template(self, phone: str, template_name: str,
                            params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{self.send_template_path}"
        payload = {
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "es"},
                "components": [
                    {"type": "body",
                     "parameters": [{"type": "text", "text": str(v)}
                                    for v in (params or {}).values()]}
                ],
            },
        }
        return await self._post(url, payload)

    async def test_connection(self) -> dict[str, Any]:
        """Ping the account endpoint. Returns {ok, status_code, body}."""
        url = f"{self.base_url}{self.test_path}"
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                r = await cli.get(url, headers=self._headers())
            ok = 200 <= r.status_code < 300
            return {"ok": ok, "status_code": r.status_code,
                    "body": _safe_json(r), "url": url}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status_code": 0, "error": str(e), "url": url}

    async def _post(self, url: str, payload: dict) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15) as cli:
                r = await cli.post(url, headers=self._headers(), json=payload)
            body = _safe_json(r)
            ok = 200 <= r.status_code < 300
            provider_id = None
            if isinstance(body, dict):
                provider_id = (body.get("id") or body.get("message_id")
                               or (body.get("messages", [{}])[0].get("id")
                                   if isinstance(body.get("messages"), list) else None))
            return {"ok": ok, "status_code": r.status_code, "body": body,
                    "provider_message_id": provider_id, "url": url}
        except Exception as e:  # noqa: BLE001
            log.exception("Chatea Pro request failed")
            return {"ok": False, "status_code": 0, "error": str(e), "url": url}


def _safe_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"text": r.text[:500]}


_singleton: ChateaProClient | None = None


def get_client() -> ChateaProClient:
    global _singleton
    if _singleton is None:
        _singleton = ChateaProClient()
    return _singleton
