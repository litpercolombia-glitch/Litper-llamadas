"""Chatea Pro WhatsApp client — real endpoints wired per confirmed spec.

Base URL: https://chateapro.app/api (por cliente, en Conexiones)
Auth: Authorization: Bearer <llave del cliente (org)> — ver client_for(org_id).
NUNCA se usa una llave global: cada cliente envía por SU cuenta.

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


NOT_CONNECTED = "Conecta tu cuenta de Chatea Pro (WhatsApp) en Conexiones."


class ChateaProClient:
    """Cliente de UN cliente (org). La llave NUNCA se lee del entorno aquí:
    llega de org_credentials.get_credentials("chatea_pro", org_id) — usar
    `await client_for(org_id)`. Sin llave → `configured` False y toda llamada
    devuelve {"ok": False, "error": NOT_CONNECTED} sin tocar la red."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 org_id: str | None = None):
        self.org_id = org_id
        self.api_key = (api_key or "").strip()
        base = (base_url or "").strip() or "https://chateapro.app/api"
        self.base_url = base.rstrip("/")
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
        if not self.configured:
            return {"ok": False, "status_code": 0, "error": NOT_CONNECTED, "url": url}
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.request(method, url, headers=self._headers(),
                                      params=params, json=json)
            ok = 200 <= r.status_code < 300
            body = _safe_json(r)
            return {"ok": ok, "status_code": r.status_code, "body": body, "url": url}
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}".replace(self.api_key, "***")[:300]
            log.warning("Chatea Pro request failed: %s %s — %s", method, url, err)
            return {"ok": False, "status_code": 0, "error": err, "url": url}

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
        return await self._req("POST", self.template_list_path, json={"limit": 200})

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


async def client_for(org_id: str) -> ChateaProClient:
    """Cliente de Chatea Pro con las credenciales de ESTE cliente (org).

    get_credentials respeta PLATFORM_KEYS_ORGS: un cliente sin llave propia y
    sin permiso de plataforma obtiene un cliente NO configurado (jamás la
    llave del servidor)."""
    from org_credentials import get_credentials
    try:
        creds = await get_credentials("chatea_pro", org_id)
    except Exception as e:  # noqa: BLE001 — sin credenciales legibles = no conectado
        log.warning("No pude leer credenciales chatea_pro/%s: %s", org_id, type(e).__name__)
        creds = {}
    return ChateaProClient(api_key=creds.get("api_key"), base_url=creds.get("base_url"),
                           org_id=org_id)


def reset_client() -> None:
    """Compatibilidad: ya no hay cliente global que reiniciar."""


# Public alias used by /config/credentials/{provider}/test to instantiate
# a one-off client with per-org credentials.
ChateaClient = ChateaProClient


# Health-check helper (used by /config credentials test). Adds a `health()`
# method to any ChateaProClient instance via monkey-patch.
async def _chatea_health(self) -> dict[str, Any]:
    if not self.configured:
        return {"ok": False, "status_code": 0, "error": NOT_CONNECTED, "body": None}
    async with httpx.AsyncClient(timeout=10) as x:
        try:
            r = await x.get(f"{self.base_url}{self.me_path}",
                            headers={"Authorization": f"Bearer {self.api_key}"})
            body = None
            try:
                body = r.json()
            except Exception:
                body = r.text[:400]
            return {"ok": r.status_code < 400, "status_code": r.status_code, "body": body}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status_code": 0, "error": str(e), "body": None}


ChateaProClient.health = _chatea_health  # type: ignore[attr-defined]
