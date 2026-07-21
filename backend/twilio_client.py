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


class TwilioClient:
    def __init__(self):
        self.sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.status_callback_base = os.environ.get("TWILIO_STATUS_CALLBACK_BASE", "").rstrip("/")

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
                    "error": "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN no configurados"}
        form: dict[str, str] = {"PhoneNumber": phone_number}
        if friendly_name:
            form["FriendlyName"] = friendly_name
        if self.status_callback_base:
            form["StatusCallback"] = f"{self.status_callback_base}/api/webhooks/twilio"
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
            return {"ok": False, "configured": False, "verified": []}
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


def get_client() -> TwilioClient:
    return TwilioClient()
