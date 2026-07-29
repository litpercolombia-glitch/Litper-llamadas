"""Iteration 18 — verify backend untouched, no seed data, empty responses."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.strip().split("=", 1)[1].rstrip("/")

EMAIL = "qa2@litper.co"
PASSWORD = "Litper!2026"
OPERATOR_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "X-API-Key": OPERATOR_KEY})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return s


# --- Auth ---
def test_auth_me(session):
    r = session.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == EMAIL


# --- Agents (5 operational) ---
def test_agents_five(session):
    r = session.get(f"{BASE_URL}/api/agents")
    assert r.status_code == 200
    data = r.json()
    if isinstance(data, dict):
        data = data.get("agents", [])
    keys = {a.get("key") or a.get("id") or a.get("slug") for a in data}
    expected = {"riesgo_rto", "confirmacion_cod", "novedades", "rescate_oficina", "analitica_operativa"}
    assert expected.issubset(keys), f"missing agents: {expected - keys}, got {keys}"


# --- No demo data ---
def test_queue_empty(session):
    r = session.get(f"{BASE_URL}/api/queue")
    assert r.status_code == 200
    assert r.json() == []


def test_orders_empty(session):
    r = session.get(f"{BASE_URL}/api/orders")
    assert r.status_code == 200
    assert r.json() == []


def test_metrics_zero(session):
    r = session.get(f"{BASE_URL}/api/metrics")
    assert r.status_code == 200
    d = r.json()
    assert d.get("orders_total", 0) == 0
    assert d.get("queue_total", 0) == 0


# --- Cascade returns processed:0 with no data ---
def test_cascade_empty(session):
    r = session.post(f"{BASE_URL}/api/agents/cascade",
                     json={"segment": "red_this_week", "limit": 25,
                           "require_confirm_for_money": True})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("processed", -1) == 0
    assert d.get("hitl_required") == [] or d.get("hitl_required") is None


# --- WhatsApp rules: 3 approved templates ---
def test_whatsapp_templates(session):
    r = session.get(f"{BASE_URL}/api/whatsapp/rules")
    assert r.status_code == 200, r.text
    data = r.json()
    if isinstance(data, dict):
        data = data.get("rules", data.get("items", []))
    names = {x.get("template_name") or x.get("template") or x.get("name") for x in data}
    expected = {"reclamo_oficina_whatsaap", "oficina_7_dias", "no__oficina__"}
    assert expected.issubset(names), f"missing templates. got {names}"


# --- BYOK connectors endpoint responds ---
def test_connectors_endpoint(session):
    r = session.get(f"{BASE_URL}/api/connectors")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    keys = {c.get("key") for c in data}
    # at least 4 required for the connectors tab
    for k in ("chatea_pro", "dropi", "elevenlabs"):
        assert k in keys, f"missing connector: {k}"
