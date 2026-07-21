"""Chatea Pro WhatsApp client — real endpoints wired per confirmed spec.

Base URL: https://chateapro.app/api (env-overridable)
Auth: Authorization: Bearer {CHATEA_PRO_API_KEY}

Endpoints wired (all overridable via env so the paths stay editable):
  * GET  /me                                → workspace/token validation
  * GET  /subscriber/get-info?phone_number  → find subscriber by phone
  * POST /subscriber/create                 → create subscriber if not found
  * POST /subscriber/send-text              → free-text WhatsApp
  * POST /subscriber/send-whatsapp-template → template WhatsApp
  * POST /whatsapp-template/list            → list approved templates

High-level flow for send_text / send_template:
  1. GET subscriber/get-info?phone_number={phone}
  2. If not found → POST subscriber/create with { phone_number, first_name? }
  3. POST send-text / send-whatsapp-template with the subscriber id (falls
     back to phone_number if the API accepts it).
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
        self.base_url = os.environ.get("CHATEA_PRO_BASE_URL", "https://chateapro.app/api").rstrip("/")
        self.me_path = os.environ.get("CHATEA_PRO_ME_PATH", "/me")
        self.send_text_path = os.environ.get("CHATEA_PRO_SEND_TEXT_PATH", "/subscriber/send-text")
        self.send_template_path = os.environ.get("CHATEA_PRO_SEND_TEMPLATE_PATH",
                                                 "/subscriber/send-whatsapp-template")
        self.template_list_path = os.environ.get("CHATEA_PRO_TEMPLATE_LIST_PATH",
                                                 "/whatsapp-template/list")
        self.subscriber_get_path = os.environ.get("CHATEA_PRO_SUBSCRIBER_GET_PATH",
                                                  "/subscriber/get-info")
        self.subscriber_create_path = os.environ.get("CHATEA_PRO_SUBSCRIBER_CREATE_PATH",
                                                     "/subscriber/create")
        if not self.api_key:
            log.warning("CHATEA_PRO_API_KEY is empty — outbound WhatsApp will fail.")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"}

    # ------- primitives -------
    async def _req(self, method: str, path: str, *, params=None, json=None,
                   timeout: int = 15) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.request(method, url, headers=self._headers(),
                                      params=params, json=json)
            ok = 200 <= r.status_code < 300
            body = _safe_json(r)
            return {"ok": ok, "status_code": r.status_code, "body": body, "url": url}
        except Exception as e:  # noqa: BLE001
            log.exception("Chatea Pro request failed: %s %s", method, url)
            return {"ok": False, "status_code": 0, "error": str(e), "url": url}

    # ------- high-level -------
    async def me(self) -> dict[str, Any]:
        """GET /me → validate the token and return workspace/user info."""
        return await self._req("GET", self.me_path, timeout=10)

    async def test_connection(self) -> dict[str, Any]:
        res = await self.me()
        # normalise
        return {
            "ok": res.get("ok"),
            "status_code": res.get("status_code"),
            "body": res.get("body"),
            "error": res.get("error"),
            "url": res.get("url"),
        }

    async def list_templates(self) -> dict[str, Any]:
        return await self._req("POST", self.template_list_path, json={})

    async def get_subscriber(self, phone: str) -> dict[str, Any]:
        # Try GET with phone_number query param first
        res = await self._req("GET", self.subscriber_get_path, params={"phone_number": phone})
        if res.get("ok"):
            return res
        # fallback: POST with json body
        return await self._req("POST", self.subscriber_get_path, json={"phone_number": phone})

    async def create_subscriber(self, phone: str, name: str | None = None,
                                country: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"phone_number": phone}
        if name:
            payload["first_name"] = name
        if country:
            payload["country"] = country
        return await self._req("POST", self.subscriber_create_path, json=payload)

    async def _ensure_subscriber(self, phone: str, name: str | None = None) -> dict[str, Any]:
        """Return subscriber dict — create if not found."""
        r = await self.get_subscriber(phone)
        body = r.get("body") or {}
        sub = _extract_subscriber(body)
        if sub:
            return {"subscriber": sub, "created": False, "raw": r}
        # Try to create.
        r2 = await self.create_subscriber(phone, name=name)
        sub2 = _extract_subscriber(r2.get("body") or {})
        return {"subscriber": sub2 or {"phone_number": phone}, "created": bool(sub2), "raw": r2}

    async def send_message(self, phone: str, text: str,
                           name: str | None = None) -> dict[str, Any]:
        """Ensure subscriber then POST /subscriber/send-text."""
        step = await self._ensure_subscriber(phone, name=name)
        sub = step["subscriber"]
        payload: dict[str, Any] = {"text": text}
        _fill_recipient(payload, sub, phone)
        res = await self._req("POST", self.send_text_path, json=payload)
        return {
            "ok": res.get("ok"),
            "status_code": res.get("status_code"),
            "body": res.get("body"),
            "error": res.get("error"),
            "url": res.get("url"),
            "subscriber": sub,
            "created_subscriber": step.get("created"),
            "provider_message_id": _extract_message_id(res.get("body") or {}),
        }

    async def send_template(self, phone: str, template_name: str,
                            params: dict[str, Any] | None = None,
                            language: str = "es",
                            name: str | None = None) -> dict[str, Any]:
        step = await self._ensure_subscriber(phone, name=name)
        sub = step["subscriber"]
        payload: dict[str, Any] = {
            "template_name": template_name,
            "language": language,
            "parameters": params or {},
        }
        _fill_recipient(payload, sub, phone)
        res = await self._req("POST", self.send_template_path, json=payload)
        return {
            "ok": res.get("ok"),
            "status_code": res.get("status_code"),
            "body": res.get("body"),
            "error": res.get("error"),
            "url": res.get("url"),
            "subscriber": sub,
            "provider_message_id": _extract_message_id(res.get("body") or {}),
        }


# ---------- helpers ----------
def _safe_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"text": r.text[:500]}


def _extract_subscriber(body: Any) -> dict | None:
    if not isinstance(body, dict):
        return None
    # Common shapes
    for key in ("subscriber", "data", "result"):
        if isinstance(body.get(key), dict):
            inner = body[key]
            if inner.get("id") or inner.get("subscriber_id") or inner.get("phone_number"):
                return inner
    if body.get("id") or body.get("subscriber_id") or body.get("phone_number"):
        return body
    return None


def _fill_recipient(payload: dict, sub: dict, phone: str) -> None:
    """Populate whichever recipient key the endpoint accepts."""
    sid = sub.get("id") or sub.get("subscriber_id")
    if sid is not None:
        payload["subscriber_id"] = sid
    payload["phone_number"] = sub.get("phone_number") or phone


def _extract_message_id(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    return (body.get("id") or body.get("message_id")
            or (body.get("data") or {}).get("id")
            or (body.get("data") or {}).get("message_id"))


_singleton: ChateaProClient | None = None


def get_client() -> ChateaProClient:
    global _singleton
    if _singleton is None:
        _singleton = ChateaProClient()
    return _singleton


def reset_client() -> None:
    """Force a re-read of env vars on next call (used by tests / hot reload)."""
    global _singleton
    _singleton = None
