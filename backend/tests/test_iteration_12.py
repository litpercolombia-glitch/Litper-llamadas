"""Iteration 12 tests — BYOK pricing pivot + /api/config/onboarding endpoint."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://litper-hub.preview.emergentagent.com").rstrip("/")
KEY = os.environ.get("PUBLIC_API_KEY", "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H")
H = {"X-API-Key": KEY, "Content-Type": "application/json"}
LLM_PROVIDERS = ["groq", "gemini", "mistral", "cerebras", "claude"]
EXPECTED_STEP_KEYS = ["chatea_pro", "elevenlabs", "telnyx", "dropi", "llm"]


def _onboarding():
    r = requests.get(f"{BASE}/api/config/onboarding", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


class TestOnboardingEndpoint:
    def test_shape(self):
        data = _onboarding()
        assert "org_id" in data
        assert data.get("total") == 5
        assert isinstance(data.get("connected"), int)
        assert isinstance(data.get("minimum_ok"), bool)
        assert isinstance(data.get("ready_message"), str) and data["ready_message"]
        steps = data.get("steps") or []
        assert len(steps) == 5
        keys = [s["key"] for s in steps]
        assert keys == EXPECTED_STEP_KEYS
        for s in steps:
            assert s.get("label") and s.get("doc") and s.get("instructions")
            assert isinstance(s.get("connected"), bool)

    def test_dropi_always_connected(self):
        steps = _onboarding()["steps"]
        drop = next(s for s in steps if s["key"] == "dropi")
        assert drop["connected"] is True

    def test_minimum_ok_logic(self):
        # Attempt to clear chatea_pro + groq to establish baseline, then re-add.
        # But env fallback keys may exist — we just verify the boolean expression via re-fetch after PUT.
        # PUT chatea_pro
        r = requests.put(f"{BASE}/api/config/credentials/chatea_pro",
                         headers=H, json={"values": {"api_key": "cp_e2e_ABC"}})
        assert r.status_code == 200, r.text

        data = _onboarding()
        cp = next(s for s in data["steps"] if s["key"] == "chatea_pro")
        assert cp["connected"] is True

        # PUT groq -> LLM connected
        r = requests.put(f"{BASE}/api/config/credentials/groq",
                         headers=H, json={"values": {"api_key": "gsk_e2e_XYZ"}})
        assert r.status_code == 200

        data2 = _onboarding()
        assert data2["minimum_ok"] is True
        llm_step = next(s for s in data2["steps"] if s["key"] == "llm")
        assert llm_step["connected"] is True


class TestRegressionSuite:
    def test_credentials_lists_9_no_plaintext(self):
        r = requests.get(f"{BASE}/api/config/credentials", headers=H, timeout=15)
        assert r.status_code == 200
        data = r.json()
        provs = data.get("providers") or []
        assert len(provs) == 9, f"expected 9 got {len(provs)}"
        blob = str(data).lower()
        # No plaintext secret should be leaking
        for leak in ["cp_e2e_abc", "gsk_e2e_xyz"]:
            assert leak not in blob

    def test_prompts_seeded_6_blocks(self):
        r = requests.get(f"{BASE}/api/prompts", headers=H, timeout=15)
        assert r.status_code == 200
        prompts = r.json()
        assert isinstance(prompts, list) and len(prompts) >= 1
        headers = ["# Personalidad", "# Entorno", "# Tono", "# Objetivo", "# Guardrails", "# Herramientas"]
        for p in prompts:
            sp = p.get("system_prompt") or ""
            for h in headers:
                assert h in sp, f"missing header {h} in prompt {p.get('id')}"

    def test_whatsapp_window(self):
        # Sample phone
        r = requests.get(f"{BASE}/api/whatsapp/window/573001234567", headers=H, timeout=15)
        assert r.status_code == 200
        assert "open" in r.json() or "within" in r.json() or "seconds_left" in r.json() or r.json() != {}


class TestCleanup:
    """Runs last (alphabetical) — remove test-created credentials to return to env fallback."""
    def test_cleanup(self):
        for p in ("chatea_pro", "groq"):
            r = requests.delete(f"{BASE}/api/config/credentials/{p}", headers=H)
            assert r.status_code == 200
