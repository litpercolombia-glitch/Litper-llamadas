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


def get_client() -> ElevenLabsClient:
    return ElevenLabsClient()
