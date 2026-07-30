"""Iteration 20 backend tests: branding, profile CRUD, feedback, zero-demo, intact APIs."""
import os
import base64
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://litper-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

EMAIL = "qa2@litper.co"
PASSWORD = "Litper!2026"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


# ---------- AUTH INTACT ----------
def test_auth_login_me_logout():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert "litper_session" in s.cookies
    me = s.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == EMAIL
    lo = s.post(f"{API}/auth/logout")
    assert lo.status_code == 200


# ---------- BACKEND INTACT ----------
def test_agents_still_5(session):
    r = session.get(f"{API}/agents")
    assert r.status_code == 200
    data = r.json()
    agents = data if isinstance(data, list) else data.get("agents", data.get("items", []))
    assert len(agents) == 5, f"Expected 5 agents, got {len(agents)}"


def test_whatsapp_rules_3_templates(session):
    r = session.get(f"{API}/whatsapp/rules")
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("rules", data.get("items", data.get("templates", [])))
    assert len(items) >= 3, f"Expected 3 templates, got {len(items)}: {data}"


def test_config_providers_has_dropi_shopify(session):
    r = session.get(f"{API}/config/providers")
    assert r.status_code == 200
    text = r.text.lower()
    assert "dropi" in text
    assert "shopify" in text


def test_agents_cascade_empty_db(session):
    r = session.post(f"{API}/agents/cascade", json={"segment": "all", "limit": 10})
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert data.get("processed") == 0


# ---------- PROFILE CRUD ----------
def test_profile_get_org(session):
    r = session.get(f"{API}/auth/org")
    assert r.status_code == 200
    assert "org" in r.json()


def test_profile_update_nombre(session):
    r = session.put(f"{API}/auth/profile", json={"nombre": "QA Two Updated"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body["user"]["nombre"] == "QA Two Updated"
    # restore
    session.put(f"{API}/auth/profile", json={"nombre": "QA Two"})


def test_password_wrong_current(session):
    r = session.put(f"{API}/auth/password",
                    json={"current_password": "WRONG_pw_xyz", "new_password": "Litper!2026x"})
    assert r.status_code == 401


def test_password_change_and_revert(session):
    r = session.put(f"{API}/auth/password",
                    json={"current_password": PASSWORD, "new_password": "Litper!2026x"})
    assert r.status_code == 200, r.text
    # Revert
    r2 = session.put(f"{API}/auth/password",
                     json={"current_password": "Litper!2026x", "new_password": PASSWORD})
    assert r2.status_code == 200, f"Revert failed: {r2.text}"


def test_avatar_upload_delete(session):
    # Tiny valid webp header base64 (not a real image but matches our regex)
    tiny = base64.b64encode(b"RIFF\x00\x00\x00\x00WEBP").decode()
    data_url = f"data:image/webp;base64,{tiny}"
    r = session.post(f"{API}/auth/avatar", json={"data_url": data_url})
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    d = session.delete(f"{API}/auth/avatar")
    assert d.status_code == 200
    assert d.json().get("ok") is True


# ---------- FEEDBACK ----------
def test_feedback_bad_payload():
    r = requests.post(f"{API}/feedback", json={"title": "", "description": "x"})
    assert r.status_code == 422


def test_feedback_submit_and_count(session):
    c1 = session.get(f"{API}/feedback/count").json()["total"]
    r = session.post(f"{API}/feedback", json={
        "title": "TEST_iter20_suggestion",
        "description": "TEST feedback body",
        "email": "test@example.com",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert len(body["id"]) == 12
    assert body["emailed"] is False
    assert "Recibimos" in body["message"]
    c2 = session.get(f"{API}/feedback/count").json()["total"]
    assert c2 == c1 + 1

    # cleanup — best effort via direct mongo
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "litper_hub")
    MongoClient(mongo_url)[db_name].feedback.delete_many({"title": "TEST_iter20_suggestion"})


# ---------- ZERO-DEMO ----------
def test_zero_demo_collections():
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "litper_hub")
    db = MongoClient(mongo_url)[db_name]
    to_check = [
        "catalog_products", "orders", "call_queue", "customer_tasks",
        "chat_threads", "chat_messages", "message_log",
        "vip_leads", "ceo_reports",
    ]
    counts = {c: db[c].count_documents({}) for c in to_check}
    non_empty = {k: v for k, v in counts.items() if v != 0}
    assert not non_empty, f"Non-empty demo collections: {non_empty}"


def test_no_products_seed_in_server():
    with open("/app/backend/server.py") as f:
        src = f.read()
    assert "PRODUCTS_SEED" not in src


# ---------- BRANDING ----------
def test_favicon_and_lyan_assets():
    for path in ["/favicon.webp", "/lyan.webp"]:
        r = requests.get(f"{BASE_URL}{path}", timeout=10)
        assert r.status_code == 200, f"{path} → {r.status_code}"


def test_index_title_and_icons():
    r = requests.get(f"{BASE_URL}/", timeout=10)
    assert r.status_code == 200
    html = r.text
    assert "<title>Zynex OS</title>" in html or "Zynex OS" in html
    assert "favicon.webp" in html
    assert "apple-touch-icon" in html
    assert "lyan.webp" in html
