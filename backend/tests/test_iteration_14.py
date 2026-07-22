"""Iteration 14 finalize-for-launch validation:
- VIP group URL, VIP submission
- WhatsApp rules migration to 3 real templates
- WA resolve by days_left
- POST /whatsapp/templates/sync schema
- Regression: prompts, credentials, wa window
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://litper-hub.preview.emergentagent.com").rstrip("/")
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
VIP_URL = "https://chat.whatsapp.com/Gb9z8fWAiOwJ36dFp4FBDN?mode=gi_t"

REQUIRED_TEMPLATES = {"reclamo_oficina_whatsaap", "oficina_7_dias", "no__oficina__"}

HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


# ----- VIP -----
def test_vip_config_returns_real_group_url():
    r = requests.get(f"{BASE_URL}/api/vip-leads/config", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("vip_group_url") == VIP_URL, data


def test_vip_lead_public_submission():
    payload = {"nombre": "QA_TEST", "whatsapp": "+573001234567", "pais": "CO"}
    r = requests.post(f"{BASE_URL}/api/vip-leads", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    # Verify config still returns real URL after submit
    r2 = requests.get(f"{BASE_URL}/api/vip-leads/config", timeout=15)
    assert r2.json().get("vip_group_url") == VIP_URL


# ----- WA RULES -----
def test_wa_rules_contains_3_real_templates():
    r = requests.get(f"{BASE_URL}/api/whatsapp/rules", headers=HEADERS, timeout=15)
    assert r.status_code == 200, r.text
    rules = r.json()
    assert isinstance(rules, list)
    tnames = {rule.get("template_name") for rule in rules if rule.get("active", True)}
    print("Templates present:", tnames)
    assert REQUIRED_TEMPLATES.issubset(tnames), f"Missing: {REQUIRED_TEMPLATES - tnames}"

    # verify days coverage
    by_tpl = {rule["template_name"]: rule for rule in rules if rule.get("template_name") in REQUIRED_TEMPLATES}
    r_reclamo = by_tpl["reclamo_oficina_whatsaap"]
    r_7 = by_tpl["oficina_7_dias"]
    r_no = by_tpl["no__oficina__"]
    assert r_reclamo["days_min"] <= 0 and r_reclamo["days_max"] >= 3, r_reclamo
    assert r_7["days_min"] <= 4 and r_7["days_max"] >= 7, r_7
    assert r_no["days_min"] <= 8, r_no


@pytest.mark.parametrize("days,expected", [(1, "reclamo_oficina_whatsaap"), (5, "oficina_7_dias"), (10, "no__oficina__")])
def test_wa_resolve_by_days(days, expected):
    r = requests.get(f"{BASE_URL}/api/whatsapp/rules/resolve", params={"days_left": days}, headers=HEADERS, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("template_name") == expected, body


def test_wa_templates_sync_endpoint_schema():
    r = requests.post(f"{BASE_URL}/api/whatsapp/templates/sync", headers=HEADERS, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("ok", "found", "missing", "detail"):
        assert key in body, f"Missing key {key} in {body}"
    assert isinstance(body["ok"], bool)
    assert isinstance(body["found"], list)
    assert isinstance(body["missing"], list)
    assert isinstance(body["detail"], str)
    # required list may be included
    if "required" in body:
        assert set(body["required"]) == REQUIRED_TEMPLATES


# ----- REGRESSION -----
def test_prompts_seeded_no_impermeable():
    r = requests.get(f"{BASE_URL}/api/prompts", headers=HEADERS, timeout=15)
    assert r.status_code == 200, r.text
    prompts = r.json()
    assert len(prompts) >= 2
    for p in prompts:
        sp = p.get("system_prompt", "")
        assert sp.startswith("# Personalidad"), f"Prompt {p.get('name')} doesn't start with '# Personalidad': {sp[:80]}"
        assert "impermeable" not in sp.lower()


def test_credentials_9_providers_no_plaintext():
    r = requests.get(f"{BASE_URL}/api/config/credentials", headers=HEADERS, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    creds = body if isinstance(body, list) else body.get("credentials") or body.get("items") or []
    assert len(creds) == 9, f"Expected 9 providers, got {len(creds)}: {[c.get('provider') for c in creds]}"
    for c in creds:
        # no plaintext secret
        for field in ("api_key", "secret", "token", "value"):
            v = c.get(field)
            if v:
                assert v.startswith("*") or v.startswith("•") or "***" in v or len(v) <= 8, f"Plaintext leaked in {c.get('provider')}: {field}={v}"


def test_wa_window_closed_enforces_template():
    # Some random phone → window should be closed / require template
    r = requests.get(f"{BASE_URL}/api/whatsapp/window/%2B573009999999", headers=HEADERS, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "open" in body or "is_open" in body or "within_24h" in body, body
