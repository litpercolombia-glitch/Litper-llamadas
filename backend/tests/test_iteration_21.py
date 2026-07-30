"""Iteration 21 backend tests — custom-agents CRUD + regressions."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
BASE_URL = BASE_URL.rstrip("/")
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
EMAIL = "qa2@litper.co"
PASSWORD = "Litper!2026"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "X-API-Key": API_KEY})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return s


# ---------- Custom-Agents static endpoints ----------
def test_templates(session):
    r = session.get(f"{BASE_URL}/api/custom-agents/templates")
    assert r.status_code == 200
    keys = {t["key"] for t in r.json()["templates"]}
    assert keys == {"rescate_oficina", "confirmacion_cod", "citas", "cobranza", "personalizado"}


def test_tools(session):
    r = session.get(f"{BASE_URL}/api/custom-agents/tools")
    assert r.status_code == 200
    tools = r.json()["tools"]
    assert len(tools) == 6


def test_voices(session):
    r = session.get(f"{BASE_URL}/api/custom-agents/voices")
    assert r.status_code == 200
    voices = r.json()["voices"]
    assert len(voices) == 4


# ---------- Custom-Agents CRUD ----------
def test_crud_flow(session):
    # list starts empty (best-effort)
    r = session.get(f"{BASE_URL}/api/custom-agents")
    assert r.status_code == 200
    initial = len(r.json().get("agents", []))

    # create
    payload = {
        "nombre": "TEST_iter21", "proposito": "rescate_oficina",
        "prompt": "Eres una operadora de prueba iter21.",
        "voz_id": "EXAVITQu4vr4xnSDxMaL",
        "tools": ["confirmar_pedido", "reagendar"],
    }
    r = session.post(f"{BASE_URL}/api/custom-agents", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    agent = body["agent"]
    agent_id = agent["id"]
    assert agent["nombre"] == "TEST_iter21"

    # patch
    r = session.patch(f"{BASE_URL}/api/custom-agents/{agent_id}", json={"nombre": "TEST_iter21_upd"})
    assert r.status_code == 200
    assert r.json()["agent"]["nombre"] == "TEST_iter21_upd"

    # list contains
    r = session.get(f"{BASE_URL}/api/custom-agents")
    assert any(a["id"] == agent_id for a in r.json()["agents"])

    # test-call BETA
    r = session.post(f"{BASE_URL}/api/custom-agents/{agent_id}/test-call", json={"numero": "+573001234567"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["beta"] is True
    assert body["dialed"] is False
    assert "Beta" in body["detail"]

    # delete
    r = session.delete(f"{BASE_URL}/api/custom-agents/{agent_id}")
    assert r.status_code == 200
    # verify gone
    r = session.get(f"{BASE_URL}/api/custom-agents")
    assert not any(a["id"] == agent_id for a in r.json()["agents"])


def test_invalid_tool(session):
    payload = {
        "nombre": "TEST_bad", "proposito": "personalizado",
        "prompt": "x", "tools": ["nope_invalid"],
    }
    r = session.post(f"{BASE_URL}/api/custom-agents", json=payload)
    assert r.status_code == 400


def test_missing_prompt(session):
    payload = {"nombre": "TEST_bad2", "proposito": "personalizado"}
    r = session.post(f"{BASE_URL}/api/custom-agents", json=payload)
    assert r.status_code == 422


# ---------- Regressions ----------
def test_agents_regression(session):
    r = session.get(f"{BASE_URL}/api/agents")
    assert r.status_code == 200
    data = r.json()
    agents = data.get("agents", data) if isinstance(data, dict) else data
    assert len(agents) == 5


def test_wa_rules(session):
    r = session.get(f"{BASE_URL}/api/whatsapp/rules")
    assert r.status_code == 200
    data = r.json()
    rules = data.get("rules", data) if isinstance(data, dict) else data
    assert len(rules) == 3


def test_config_providers(session):
    r = session.get(f"{BASE_URL}/api/config/providers")
    assert r.status_code == 200
    body = r.json()
    text = str(body).lower()
    assert "dropi" in text and "shopify" in text


def test_auth_me(session):
    r = session.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == EMAIL
