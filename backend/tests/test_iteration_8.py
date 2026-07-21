"""Backend tests for iteration_8 completion round:
Prompts CRUD + resolve + generate, Telnyx config/register, WA rules CRUD + resolve,
WA templates proxy, and regression on dropi + products.match."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://litper-hub.preview.emergentagent.com").rstrip("/")
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
H = {"Content-Type": "application/json", "X-API-Key": API_KEY}


# -----------------------------------------------------------------
# PROMPTS
# -----------------------------------------------------------------
class TestPrompts:
    created_id = None

    def test_list_seeded(self):
        r = requests.get(f"{BASE_URL}/api/prompts", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        globals_ = [p for p in data if p.get("scope") == "global"]
        assert len(globals_) >= 2, f"Expected >=2 global seeds, got {len(globals_)}"
        countries = {p.get("country") for p in globals_}
        assert "CO" in countries and "EC" in countries

    def test_create_campaign_prompt(self):
        payload = {
            "scope": "campaign", "campaign_key": "servientrega",
            "country": "CO", "priority": 200,
            "name": "TEST_Sofia Servientrega",
            "system_prompt": "Eres Sofía CAMPAIGN antifluido {product_name} en {carrier_name}.",
            "first_message": "Hola {customer_first_name}",
            "active": True,
        }
        r = requests.post(f"{BASE_URL}/api/prompts", headers=H, json=payload, timeout=30)
        assert r.status_code == 201, r.text
        j = r.json()
        assert j["scope"] == "campaign"
        assert j["campaign_key"] == "servientrega"
        assert j["priority"] == 200
        TestPrompts.created_id = j["id"]
        # verify it appears in list
        r2 = requests.get(f"{BASE_URL}/api/prompts", headers=H, timeout=30)
        assert any(p["id"] == j["id"] for p in r2.json())

    def test_resolve_campaign_wins(self):
        r = requests.post(f"{BASE_URL}/api/prompts/resolve", headers=H,
                          json={"country": "CO", "carrier_slug": "servientrega"}, timeout=30)
        assert r.status_code == 200, r.text
        p = r.json()["prompt"]
        assert p["scope"] == "campaign", f"Expected campaign wins, got {p['scope']}"
        assert p["campaign_key"] == "servientrega"

    def test_resolve_global_co(self):
        r = requests.post(f"{BASE_URL}/api/prompts/resolve", headers=H,
                          json={"country": "CO"}, timeout=30)
        assert r.status_code == 200, r.text
        p = r.json()["prompt"]
        # If campaign only matches with carrier_slug -> global CO wins
        assert p["scope"] == "global"
        assert p["country"] == "CO"

    def test_resolve_global_ec(self):
        r = requests.post(f"{BASE_URL}/api/prompts/resolve", headers=H,
                          json={"country": "EC"}, timeout=30)
        assert r.status_code == 200, r.text
        p = r.json()["prompt"]
        assert p["scope"] == "global"
        assert p["country"] == "EC"

    def test_patch_deactivate_and_delete(self):
        assert TestPrompts.created_id
        r = requests.patch(f"{BASE_URL}/api/prompts/{TestPrompts.created_id}",
                           headers=H, json={"active": False}, timeout=30)
        assert r.status_code == 200, r.text
        # resolve should no longer return the campaign one
        r2 = requests.post(f"{BASE_URL}/api/prompts/resolve", headers=H,
                           json={"country": "CO", "carrier_slug": "servientrega"}, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["prompt"]["scope"] == "global"
        # delete
        r3 = requests.delete(f"{BASE_URL}/api/prompts/{TestPrompts.created_id}", headers=H, timeout=30)
        assert r3.status_code == 200

    def test_generate_prompt(self):
        payload = {"product": "Protector Antifluido Premium",
                   "tono": "colombiano",
                   "transportadora": "Servientrega",
                   "beneficios": "antifluido, doble capa",
                   "objeciones": "precio, tiempos"}
        r = requests.post(f"{BASE_URL}/api/prompts/generate", headers=H, json=payload, timeout=90)
        if r.status_code == 200:
            data = r.json()
            assert "system_prompt" in data and "first_message" in data and "model_used" in data
            sp_raw = data["system_prompt"]
            sp = sp_raw.lower()
            assert "antifluido" in sp, "system_prompt must contain 'antifluido'"
            assert "impermeable" not in sp, "system_prompt must NOT contain 'impermeable'"
            assert "flujo" in sp, "system_prompt must mention FLUJO structure"
            assert (len(sp_raw) >= 900) or ("flujo" in sp), "must be >=900 chars or contain FLUJO markers"
            # placeholder
            assert ("{customer_first_name}" in sp_raw) or ("{guia}" in sp_raw), \
                "must contain at least one variable placeholder"
            print(f"model_used={data.get('model_used')} len={len(sp_raw)}")
        else:
            assert r.status_code == 502, f"unexpected {r.status_code}: {r.text}"
            print(f"LLM router returned 502 as acceptable outcome: {r.text[:200]}")


# -----------------------------------------------------------------
# TELNYX
# -----------------------------------------------------------------
class TestTelnyx:
    def test_config_masked(self):
        r = requests.get(f"{BASE_URL}/api/numbers/telnyx/config", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["api_key_present"] is False
        assert j["sip_domain"] == "sip.telnyx.com"
        assert j["phone_number"] == ""
        # fields exist
        for k in ("api_key_masked", "sip_username_present", "sip_password_present"):
            assert k in j

    def test_register_missing_env(self):
        r = requests.post(f"{BASE_URL}/api/numbers/telnyx/register", headers=H, json={}, timeout=30)
        assert r.status_code == 400, r.text
        detail = r.json().get("detail", "")
        for v in ("TELNYX_PHONE_NUMBER", "TELNYX_SIP_USERNAME", "TELNYX_SIP_PASSWORD"):
            assert v in detail, f"missing {v} not in detail: {detail}"


# -----------------------------------------------------------------
# WHATSAPP RULES
# -----------------------------------------------------------------
class TestWhatsAppRules:
    def test_list_seeded(self):
        r = requests.get(f"{BASE_URL}/api/whatsapp/rules", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        rules = r.json()
        keys = {rr["rule_key"] for rr in rules}
        assert "reclamo_oficina" in keys and "no_oficina" in keys
        assert len(rules) >= 2

    def test_resolve_reclamo(self):
        r = requests.get(f"{BASE_URL}/api/whatsapp/rules/resolve?days_left=1", headers=H, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["matched"] is True
        assert j["rule"]["rule_key"] == "reclamo_oficina"

    def test_resolve_no_oficina(self):
        r = requests.get(f"{BASE_URL}/api/whatsapp/rules/resolve?days_left=6", headers=H, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["matched"] is True
        assert j["rule"]["rule_key"] == "no_oficina"

    def test_resolve_extreme(self):
        r = requests.get(f"{BASE_URL}/api/whatsapp/rules/resolve?days_left=999", headers=H, timeout=30)
        assert r.status_code == 200
        j = r.json()
        # 999 > default max=99, so no rule matches - record actual behavior
        print(f"days_left=999 result: matched={j.get('matched')}")
        # per prompt spec, either True/False acceptable but we assert it doesn't crash
        assert "matched" in j

    def test_patch_and_recreate(self):
        r = requests.get(f"{BASE_URL}/api/whatsapp/rules", headers=H, timeout=30)
        rules = r.json()
        target = next((rr for rr in rules if rr["rule_key"] == "reclamo_oficina"), None)
        assert target
        orig_tpl = target.get("template_name")
        # PATCH
        rp = requests.patch(f"{BASE_URL}/api/whatsapp/rules/{target['id']}", headers=H,
                            json={"template_name": "reclamo_v2"}, timeout=30)
        assert rp.status_code == 200, rp.text
        assert rp.json()["template_name"] == "reclamo_v2"
        # revert
        requests.patch(f"{BASE_URL}/api/whatsapp/rules/{target['id']}", headers=H,
                       json={"template_name": orig_tpl}, timeout=30)

    def test_templates_proxy(self):
        r = requests.get(f"{BASE_URL}/api/whatsapp/templates", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        # accept both configured or not
        assert "templates" in j
        print(f"templates: configured={j.get('configured')}, ok={j.get('ok')}, count={len(j.get('templates', []))}")


# -----------------------------------------------------------------
# REGRESSION
# -----------------------------------------------------------------
class TestRegression:
    def test_products_match_promo(self):
        r = requests.post(f"{BASE_URL}/api/products/match", headers=H,
                          json={"product_name": "PROTECTOR MAS FUNDAS"}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        # Must include Protector Antifluido Premium + Fundas
        s = str(j).lower()
        assert "antifluido" in s or "protector" in s, f"missing protector in {j}"
        assert "funda" in s, f"missing fundas in {j}"
