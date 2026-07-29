"""Iteration 19 backend regression: providers list, dropi + shopify test endpoints,
auth/agents/cascade/WA templates untouched."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
BASE_URL = BASE_URL.rstrip("/")
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"

EMAIL = "qa2@litper.co"
PASSWORD = "Litper!2026"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"X-API-Key": API_KEY, "Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


# ------------------ AUTH regression ------------------
def test_auth_me(client):
    r = client.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200
    assert r.json().get("user", {}).get("email") == EMAIL


# ------------------ Config providers (new: dropi + shopify) ------------------
def test_config_providers_includes_dropi_and_shopify(client):
    r = client.get(f"{BASE_URL}/api/config/providers")
    assert r.status_code == 200
    names = {p["provider"] for p in r.json()["providers"]}
    assert "dropi" in names
    assert "shopify" in names
    # legacy still present
    assert {"chatea_pro", "telnyx", "elevenlabs"} <= names


def test_shopify_save_and_test_and_cleanup(client):
    # PUT shopify creds
    r = client.put(
        f"{BASE_URL}/api/config/credentials/shopify",
        json={"values": {"access_token": "shpat_test", "store_url": "nonexistent.myshopify.com"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "shopify"
    assert body["is_configured"] is True

    # POST test — must NOT be 500
    r = client.post(f"{BASE_URL}/api/config/credentials/shopify/test")
    assert r.status_code == 200, f"shopify/test returned {r.status_code}: {r.text}"
    js = r.json()
    assert "ok" in js  # ok:false is expected since domain doesn't exist
    assert js["ok"] is False or js["ok"] is True

    # DELETE cleanup
    r = client.delete(f"{BASE_URL}/api/config/credentials/shopify")
    assert r.status_code == 200


def test_dropi_test_endpoint_shape(client):
    # Only trigger the branch — don't expect success unless env is set
    r = client.post(f"{BASE_URL}/api/config/credentials/dropi/test")
    assert r.status_code == 200
    assert "ok" in r.json()


# ------------------ Agents regression ------------------
def test_agents_list_five(client):
    r = client.get(f"{BASE_URL}/api/agents")
    assert r.status_code == 200
    data = r.json()
    agents = data.get("agents") if isinstance(data, dict) else data
    assert isinstance(agents, list)
    assert len(agents) == 5


def test_cascade_processed_zero(client):
    r = client.post(
        f"{BASE_URL}/api/agents/cascade",
        json={"segment": "red_this_week", "limit": 25, "require_confirm_for_money": True},
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("processed") == 0


# ------------------ WhatsApp templates ------------------
def test_whatsapp_rules_three(client):
    r = client.get(f"{BASE_URL}/api/whatsapp/rules")
    assert r.status_code == 200
    data = r.json()
    rules = data if isinstance(data, list) else data.get("rules") or data.get("templates") or []
    names = {(r.get("name") or r.get("template_name") or r.get("key")) for r in rules}
    # Approved templates
    expected = {"reclamo_oficina_whatsaap", "oficina_7_dias", "no__oficina__"}
    assert expected <= names, f"Missing templates. Got: {names}"
