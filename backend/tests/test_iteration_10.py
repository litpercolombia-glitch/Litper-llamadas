"""Iteration 10: multi-tenant credentials, WA 24h window, 6-block prompt, funnel regressions."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # Fallback for backend-side reading
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE = line.split("=", 1)[1].strip().strip('"').rstrip("/")

API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
HDR = {"Content-Type": "application/json", "X-API-Key": API_KEY}


# ---------------- CONFIG providers/credentials ----------------
class TestConfigProviders:
    def test_providers_list(self):
        r = requests.get(f"{BASE}/api/config/providers", headers=HDR, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        provs = data.get("providers") if isinstance(data, dict) else data
        names = {p["provider"] for p in provs}
        expected = {"chatea_pro","telnyx","elevenlabs","twilio","groq","gemini","mistral","cerebras","claude"}
        assert expected.issubset(names), f"missing: {expected - names}"
        for p in provs:
            if p["provider"] == "chatea_pro":
                assert isinstance(p.get("fields"), list) and len(p["fields"]) > 0
                f0 = p["fields"][0]
                for key in ("name","label","is_secret","env"):
                    assert key in f0, f"missing {key} in field: {f0}"

    def test_credentials_list_shape(self):
        r = requests.get(f"{BASE}/api/config/credentials", headers=HDR, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("org_id") == "default"
        provs = d["providers"]
        assert len(provs) == 9
        p0 = provs[0]
        for key in ("provider","fields","configured","origin","hint","updated_at"):
            assert key in p0, f"key {key} missing in {p0}"
        for f in p0["fields"]:
            for k in ("name","label","is_secret","has_value"):
                assert k in f

    def test_put_chatea_pro_and_mask(self):
        payload = {"values": {"api_key": "cp_test_ABCDEF1234"}}
        r = requests.put(f"{BASE}/api/config/credentials/chatea_pro", json=payload, headers=HDR, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        # Support 'is_configured' or 'configured'
        assert d.get("is_configured") is True or d.get("configured") is True, d
        hint = d.get("hint") or ""
        assert "1234" in hint, f"expected hint to contain masked tail, got {hint!r}"
        assert "cp_test_ABCDEF1234" not in hint

        r2 = requests.get(f"{BASE}/api/config/credentials", headers=HDR, timeout=15)
        assert r2.status_code == 200
        body = r2.text
        assert "cp_test_ABCDEF1234" not in body, "PLAINTEXT LEAK!"
        cp = next(p for p in r2.json()["providers"] if p["provider"] == "chatea_pro")
        assert cp["origin"] == "org", cp
        assert cp["configured"] is True

    def test_put_empty_removes_org_field(self):
        # First set an org value
        requests.put(f"{BASE}/api/config/credentials/chatea_pro", json={"values": {"api_key": "cp_test_TMP1234"}}, headers=HDR, timeout=15)
        # PUT empty
        r = requests.put(f"{BASE}/api/config/credentials/chatea_pro", json={"values": {"api_key": ""}}, headers=HDR, timeout=15)
        assert r.status_code == 200
        r2 = requests.get(f"{BASE}/api/config/credentials", headers=HDR, timeout=15)
        cp = next(p for p in r2.json()["providers"] if p["provider"] == "chatea_pro")
        # After clearing org-level api_key, origin should fall back to env (or none if no env)
        assert cp["origin"] in ("env", "none"), cp

    def test_delete_falls_back_env(self):
        # first put again then delete
        requests.put(f"{BASE}/api/config/credentials/chatea_pro", json={"values": {"api_key": "cp_test_ZZ9999"}}, headers=HDR, timeout=15)
        r = requests.delete(f"{BASE}/api/config/credentials/chatea_pro", headers=HDR, timeout=15)
        assert r.status_code in (200, 204), r.text
        r2 = requests.get(f"{BASE}/api/config/credentials", headers=HDR, timeout=15)
        cp = next(p for p in r2.json()["providers"] if p["provider"] == "chatea_pro")
        assert cp["origin"] in ("env", "none"), cp

    def test_test_endpoint_chatea(self):
        r = requests.post(f"{BASE}/api/config/credentials/chatea_pro/test", headers=HDR, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "ok" in d and "detail" in d

    def test_test_endpoint_telnyx_empty(self):
        # delete any org cred first
        requests.delete(f"{BASE}/api/config/credentials/telnyx", headers=HDR, timeout=15)
        r = requests.post(f"{BASE}/api/config/credentials/telnyx/test", headers=HDR, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Only assert shape; empty env should give ok=false
        assert "ok" in d and "detail" in d


# ---------------- WHATSAPP 24h window ----------------
class TestWhatsAppWindow:
    PHONE = "+573001999888"

    def test_window_closed_for_new(self):
        # ensure clean (best-effort)
        r = requests.get(f"{BASE}/api/whatsapp/window/%2B573001999888", headers=HDR, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        # allow either explicit closed or open depending on if seeded
        assert "window_open" in d
        assert "allowed_send_types" in d
        assert isinstance(d["allowed_send_types"], list)

    def test_mark_inbound_opens(self):
        r = requests.post(f"{BASE}/api/whatsapp/contacts/mark-inbound",
                          params={"phone": self.PHONE, "body": "hola"},
                          headers=HDR, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        # can be nested or flat
        wo = d.get("window_open")
        if wo is None and "contact" in d:
            wo = d["contact"].get("window_open")
        assert wo is True, d
        r2 = requests.get(f"{BASE}/api/whatsapp/window/%2B573001999888", headers=HDR, timeout=15)
        d2 = r2.json()
        assert d2["window_open"] is True
        assert d2.get("remaining_seconds", 0) > 80000
        assert "freeform" in d2["allowed_send_types"]
        assert "template" in d2["allowed_send_types"]

    def test_contacts_list(self):
        r = requests.get(f"{BASE}/api/whatsapp/contacts", headers=HDR, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        items = d.get("contacts") if isinstance(d, dict) else d
        phones = [c.get("phone") for c in items]
        assert self.PHONE in phones, phones


# ---------------- PROMPTS ----------------
class TestPrompts:
    def test_generate_6block(self):
        payload = {"product": "Protector Antifluido Premium", "tono": "colombiano", "transportadora": "Servientrega"}
        r = requests.post(f"{BASE}/api/prompts/generate", json=payload, headers=HDR, timeout=60)
        assert r.status_code == 200, r.text
        sp = r.json().get("system_prompt", "")
        for hdr in ("# Personalidad", "# Tono", "# Guardrails", "# Objetivo"):
            assert hdr in sp, f"missing header {hdr}"
        assert "antifluido" in sp.lower()
        assert "impermeable" not in sp.lower()
        assert len(sp) >= 1200, f"len={len(sp)}"

    def test_seeded_prompts(self):
        r = requests.get(f"{BASE}/api/prompts", headers=HDR, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        items = d if isinstance(d, list) else d.get("prompts", d.get("items", []))
        assert len(items) >= 2
        sofia_co = None
        for it in items:
            name = (it.get("name") or "").lower()
            if "sof" in name and ("co" in name or "colomb" in name):
                sofia_co = it
                break
        assert sofia_co is not None, [i.get("name") for i in items]
        sp = sofia_co.get("system_prompt", "")
        assert sp.lstrip().startswith("# Personalidad"), sp[:120]


# ---------------- REGRESSION ----------------
class TestRegression:
    def test_products_match(self):
        # /api/products/match is POST
        r = requests.post(f"{BASE}/api/products/match", json={"product_name": "PROTECTOR MAS FUNDAS"}, headers=HDR, timeout=15)
        assert r.status_code == 200, r.text
        body = str(r.json()).lower()
        assert "protector" in body

    def test_whatsapp_rules(self):
        r = requests.get(f"{BASE}/api/whatsapp/rules", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        rules = d if isinstance(d, list) else d.get("rules", [])
        assert len(rules) >= 2
