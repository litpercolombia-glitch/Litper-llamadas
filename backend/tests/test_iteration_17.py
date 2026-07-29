"""Iteration 17 — CEO Report → WhatsApp feature tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to reading /app/frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"
EMAIL = "qa2@litper.co"
PASSWORD = "Litper!2026"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# --- Regression sanity checks (iter 16) ---
def test_auth_me(client):
    r = client.get(f"{API}/auth/me", timeout=10)
    assert r.status_code == 200
    body = r.json()
    email = body.get("email") or (body.get("user") or {}).get("email")
    assert email == EMAIL


def test_agents_list(client):
    r = client.get(f"{API}/agents", timeout=10)
    assert r.status_code == 200
    assert len(r.json().get("agents", [])) == 5


def test_cascade_red(client):
    r = client.post(f"{API}/agents/cascade", json={"segment": "red_this_week", "limit": 5}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("segment") == "red_this_week"
    assert "hitl_required" in d


def test_queue_and_metrics(client):
    for path in ("/queue", "/metrics"):
        r = client.get(f"{API}{path}", timeout=15)
        assert r.status_code == 200, f"{path}: {r.status_code}"


# --- New iter17: CEO WA endpoints ---
def test_target_reset_empty(client):
    # Ensure clean baseline: set to empty
    r = client.put(f"{API}/agents/ceo-report/target", json={"target": ""}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    r2 = client.get(f"{API}/agents/ceo-report/target", timeout=10)
    assert r2.status_code == 200
    assert r2.json() == {"target": ""}


def test_send_wa_400_without_target(client):
    # Guarantee empty
    client.put(f"{API}/agents/ceo-report/target", json={"target": ""}, timeout=10)
    r = client.post(f"{API}/agents/ceo-report/send-wa", timeout=15)
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"


def test_put_and_get_target(client):
    r = client.put(f"{API}/agents/ceo-report/target", json={"target": "+573001112222"}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("target") == "+573001112222"
    r2 = client.get(f"{API}/agents/ceo-report/target", timeout=10)
    assert r2.status_code == 200
    assert r2.json().get("target") == "+573001112222"


def test_send_wa_returns_200_with_target(client):
    # Ensure target is set
    client.put(f"{API}/agents/ceo-report/target", json={"target": "+573001112222"}, timeout=10)
    r = client.post(f"{API}/agents/ceo-report/send-wa", timeout=60)
    assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text}"
    d = r.json()
    assert "ok" in d and isinstance(d["ok"], bool)
    assert d.get("target") == "+573001112222"
    assert "provider_message_id" in d
    assert "error" in d


def test_message_log_ceo_report_kind(client):
    # Trigger a send to ensure there's at least one ceo_report log row
    client.put(f"{API}/agents/ceo-report/target", json={"target": "+573001112222"}, timeout=10)
    client.post(f"{API}/agents/ceo-report/send-wa", timeout=60)

    # Read the log via mongo directly
    import pymongo
    mongo_url = None
    dbname = None
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("MONGO_URL="):
                mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("DB_NAME="):
                dbname = line.split("=", 1)[1].strip().strip('"').strip("'")
    assert mongo_url and dbname
    c = pymongo.MongoClient(mongo_url)
    coll = c[dbname]["message_log"]
    count = coll.count_documents({"kind": "ceo_report"})
    assert count >= 1, "no ceo_report message_log row inserted"


def test_scheduler_has_4_jobs():
    # Read backend log to verify scheduler startup message mentions all jobs
    import subprocess
    out = subprocess.run(
        ["grep", "-h", "APScheduler started", "/var/log/supervisor/backend.err.log",
         "/var/log/supervisor/backend.out.log"],
        capture_output=True, text=True
    )
    text = out.stdout
    # Also fallback to add_job lines
    add_jobs = subprocess.run(
        ["grep", "-rh", "Added job", "/var/log/supervisor/"],
        capture_output=True, text=True
    ).stdout
    combined = text + "\n" + add_jobs
    required = ["dispatch_due_attempts", "novedades_sweep", "daily_ceo_report", "daily_ceo_report_wa"]
    missing = [j for j in required if j not in combined]
    assert not missing, f"missing jobs in logs: {missing}\nlogs:\n{combined[:2000]}"
