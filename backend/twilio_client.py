"""Twilio REST client — Verified Outbound Caller IDs.

REST endpoints (form-urlencoded, HTTP Basic auth with ACCOUNT_SID:AUTH_TOKEN):
  * POST   https://api.twilio.com/2010-04-01/Accounts/{Sid}/OutgoingCallerIds.json
  * GET    https://api.twilio.com/2010-04-01/Accounts/{Sid}/OutgoingCallerIds.json
  * GET    .../OutgoingCallerIds/{PN...}.json
  * DELETE .../OutgoingCallerIds/{PN...}.json

Response of POST includes `validation_code` (6 digits) to display to the user.
"""
from __future__ import annotations
import os
import logging
from typing import Any
import httpx

log = logging.getLogger("twilio")

TWILIO_BASE = "https://api.twilio.com/2010-04-01"


NOT_CONNECTED = "Conecta tu cuenta de Twilio en Conexiones."


class TwilioClient:
    """Cliente de UN cliente (org): `await client_for(org_id)`."""

    def __init__(self, account_sid: str | None = None, auth_token: str | None = None,
                 org_id: str | None = None):
        self.org_id = org_id
        self.sid = (account_sid or "").strip()
        self.token = (auth_token or "").strip()
        self.status_callback_base = (os.environ.get("TWILIO_STATUS_CALLBACK_BASE", "")
                                     or os.environ.get("PUBLIC_BASE_URL", "")).rstrip("/")
        # Token de webhooks de ESTE cliente (lo fija client_for): la URL de
        # callback lo lleva para que el evento se atribuya solo a él.
        self.webhook_token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.sid and self.token)

    def _auth(self):
        return httpx.BasicAuth(self.sid, self.token)

    def _url(self, path: str) -> str:
        return f"{TWILIO_BASE}/Accounts/{self.sid}{path}"

    async def start_validation(self, phone_number: str, friendly_name: str | None = None
                               ) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "configured": False,
                    "error": NOT_CONNECTED}
        form: dict[str, str] = {"PhoneNumber": phone_number}
        if friendly_name:
            form["FriendlyName"] = friendly_name
        if self.status_callback_base and self.webhook_token:
            form["StatusCallback"] = (f"{self.status_callback_base}/api/webhooks/twilio/"
                                      f"{self.webhook_token}")
        try:
            async with httpx.AsyncClient(timeout=20) as cli:
                r = await cli.post(self._url("/OutgoingCallerIds.json"),
                                   data=form, auth=self._auth())
            if 200 <= r.status_code < 300:
                data = r.json()
                return {"ok": True, "configured": True,
                        "validation_code": data.get("validation_code"),
                        "call_sid": data.get("call_sid"),
                        "phone_number": data.get("phone_number"),
                        "friendly_name": data.get("friendly_name")}
            return {"ok": False, "configured": True,
                    "status_code": r.status_code, "error": r.text[:400]}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "configured": True, "error": str(e)}

    async def list_verified(self) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "configured": False, "error": NOT_CONNECTED, "verified": []}
        try:
            async with httpx.AsyncClient(timeout=15) as cli:
                r = await cli.get(self._url("/OutgoingCallerIds.json"), auth=self._auth())
            if 200 <= r.status_code < 300:
                data = r.json()
                verified = [
                    {"sid": v.get("sid"),
                     "phone_number": v.get("phone_number"),
                     "friendly_name": v.get("friendly_name"),
                     "date_created": v.get("date_created"),
                     "date_updated": v.get("date_updated")}
                    for v in data.get("outgoing_caller_ids", [])
                ]
                return {"ok": True, "configured": True, "verified": verified}
            return {"ok": False, "configured": True,
                    "status_code": r.status_code, "error": r.text[:300], "verified": []}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "configured": True, "error": str(e), "verified": []}

    async def check_verified(self, phone_number: str) -> bool:
        res = await self.list_verified()
        for v in res.get("verified", []):
            if v.get("phone_number") == phone_number:
                return True
        return False


async def client_for(org_id: str) -> TwilioClient:
    """Cliente de Twilio con las credenciales de ESTE cliente (org)."""
    from org_credentials import get_credentials
    try:
        c = await get_credentials("twilio", org_id)
    except Exception as e:  # noqa: BLE001
        log.warning("No pude leer credenciales twilio/%s: %s", org_id, type(e).__name__)
        c = {}
    cli = TwilioClient(account_sid=c.get("account_sid"), auth_token=c.get("auth_token"),
                       org_id=org_id)
    if cli.configured and cli.status_callback_base:
        try:
            import webhook_tokens
            cli.webhook_token = await webhook_tokens.token_for(org_id)
        except Exception as e:  # noqa: BLE001 — sin token no se pide callback
            log.warning("Sin token de webhooks para %s: %s", org_id, type(e).__name__)
    return cli
