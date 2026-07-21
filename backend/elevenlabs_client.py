"""ElevenLabs REST client (voice picker)."""
from __future__ import annotations
import os
import logging
from typing import Any
import httpx

log = logging.getLogger("elevenlabs")


class ElevenLabsClient:
    def __init__(self):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        self.base_url = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io/v1").rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self.api_key, "Accept": "application/json"}

    async def list_voices(self) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "configured": False,
                    "error": "ELEVENLABS_API_KEY no configurada",
                    "voices": []}
        url = f"{self.base_url}/voices"
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                r = await cli.get(url, headers=self._headers())
            if 200 <= r.status_code < 300:
                data = r.json()
                voices = [
                    {"voice_id": v.get("voice_id"),
                     "name": v.get("name"),
                     "labels": v.get("labels", {}),
                     "category": v.get("category"),
                     "preview_url": v.get("preview_url")}
                    for v in data.get("voices", [])
                ]
                return {"ok": True, "configured": True, "voices": voices}
            return {"ok": False, "configured": True,
                    "status_code": r.status_code, "error": r.text[:300], "voices": []}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "configured": True, "error": str(e), "voices": []}

    async def synthesize(self, voice_id: str, text: str,
                         model_id: str = "eleven_multilingual_v2") -> tuple[bytes | None, str | None]:
        """POST /text-to-speech/{voice_id} → returns (audio_bytes, error)."""
        if not self.configured:
            return None, "ELEVENLABS_API_KEY no configurada"
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        try:
            async with httpx.AsyncClient(timeout=30) as cli:
                r = await cli.post(url, headers={**self._headers(),
                                                 "Content-Type": "application/json",
                                                 "Accept": "audio/mpeg"},
                                   json=payload)
            if 200 <= r.status_code < 300:
                return r.content, None
            return None, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:  # noqa: BLE001
            return None, str(e)

    async def register_sip_trunk(self, *, label: str, address: str,
                                 username: str, password: str,
                                 phone_number: str) -> dict:
        """Register a DIDWW (or any) SIP trunk in ElevenLabs Conversational AI."""
        import os as _os
        if not self.configured:
            return {"ok": False, "configured": False,
                    "error": "ELEVENLABS_API_KEY no configurada"}
        path = _os.environ.get("ELEVENLABS_SIP_REGISTER_PATH",
                              "/convai/phone-numbers/create")
        url = f"{self.base_url}{path}"
        payload = {
            "label": label,
            "phone_number": phone_number,
            "provider": "sip_trunk",
            "sip_trunk_credentials": {
                "address": address,
                "username": username,
                "password": password,
                "transport": "udp",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=20) as cli:
                r = await cli.post(url, headers={**self._headers(),
                                                 "Content-Type": "application/json"},
                                   json=payload)
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") \
                else {"text": r.text[:400]}
            ok = 200 <= r.status_code < 300
            return {"ok": ok, "status_code": r.status_code, "body": body,
                    "phone_number_id": (body or {}).get("phone_number_id")
                                       or (body or {}).get("id") if ok else None}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    async def sip_outbound_call(self, *, phone_number_id: str, agent_id: str,
                                to_number: str, metadata: dict | None = None) -> dict:
        """Trigger a SIP outbound call from ElevenLabs to `to_number` using our trunk."""
        import os as _os
        if not self.configured:
            return {"ok": False, "configured": False,
                    "error": "ELEVENLABS_API_KEY no configurada"}
        path = _os.environ.get("ELEVENLABS_SIP_CALL_PATH",
                              "/convai/sip-trunk/outbound-call")
        url = f"{self.base_url}{path}"
        payload = {
            "agent_id": agent_id,
            "agent_phone_number_id": phone_number_id,
            "to_number": to_number,
            "conversation_initiation_client_data": {
                "dynamic_variables": metadata or {},
            },
        }
        try:
            async with httpx.AsyncClient(timeout=20) as cli:
                r = await cli.post(url, headers={**self._headers(),
                                                 "Content-Type": "application/json"},
                                   json=payload)
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") \
                else {"text": r.text[:400]}
            return {"ok": 200 <= r.status_code < 300,
                    "status_code": r.status_code, "body": body,
                    "conversation_id": (body or {}).get("conversation_id")
                                       or (body or {}).get("id")}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}


def get_client() -> ElevenLabsClient:
    return ElevenLabsClient()
