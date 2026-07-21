"""Litper Connect Hub v1.5 — DIDWW SIP trunk backend tests.

Covers 4 new SIP endpoints + regressions.
Prereqs: DIDWW_*, CALLER_ID_NUMBER, ELEVENLABS_AGENT_ID env vars are blank (preview default).
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") \
    else "https://litper-hub.preview.emergentagent.com"
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
H = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo():
    # Read Mongo URL from backend .env
    mongo_url = None
    db_name = None
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("MONGO_URL="):
                mongo_url = line.strip().split("=", 1)[1].strip('"').strip("'")
            elif line.startswith("DB_NAME="):
                db_name = line.strip().split("=", 1)[1].strip('"').strip("'")
    client = MongoClient(mongo_url)
    yield client[db_name]
    client.close()


# --- 1. GET /api/numbers/sip/config: schema + no secret leak ---------------
class TestSipConfig:
    def test_requires_api_key(self):
        r = requests.get(f"{BASE_URL}/api/numbers/sip/config")
        assert r.status_code == 401, r.text

    def test_config_shape_and_no_leak(self):
        r = requests.get(f"{BASE_URL}/api/numbers/sip/config", headers=H)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["provider", "sip_domain", "sip_username_set", "sip_password_set",
                  "outbound_trunk_id", "caller_id_number", "elevenlabs_agent_id"]:
            assert k in data, f"missing key {k}"
        assert isinstance(data["sip_username_set"], bool)
        assert isinstance(data["sip_password_set"], bool)
        # Secrets must not appear as raw values
        assert "sip_username" not in data
        assert "sip_password" not in data
        assert "DIDWW_SIP_PASSWORD" not in str(data)


# --- 2. POST /api/numbers/sip/test -----------------------------------------
class TestSipTest:
    def test_requires_api_key(self):
        r = requests.post(f"{BASE_URL}/api/numbers/sip/test")
        assert r.status_code == 401, r.text

    def test_reports_all_missing_env(self):
        r = requests.post(f"{BASE_URL}/api/numbers/sip/test", headers=H)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is False
        assert "config" in data and "issues" in data
        issues = data["issues"]
        for expected in ["DIDWW_SIP_DOMAIN vacío", "DIDWW_SIP_USERNAME vacío",
                         "DIDWW_SIP_PASSWORD vacío", "CALLER_ID_NUMBER vacío",
                         "ELEVENLABS_AGENT_ID vacío"]:
            assert expected in issues, f"expected issue missing: {expected} — got {issues}"


# --- 3. POST /api/numbers/sip/register -------------------------------------
class TestSipRegister:
    def test_no_body_no_env_returns_400(self):
        r = requests.post(f"{BASE_URL}/api/numbers/sip/register", headers=H, json=None)
        assert r.status_code == 400, r.text
        assert "SIP credentials incompletas" in r.json().get("detail", "")

    def test_body_with_fake_creds_returns_502(self):
        body = {
            "sip_username": "fake_user",
            "sip_password": "fake_pw",
            "sip_domain": "sip.fake.example.com",
            "caller_id_number": "+573001234567",
            "friendly_name": "TEST_didww"
        }
        # Hit backend directly (ingress rewrites 5xx bodies to HTML error page).
        r = requests.post("http://localhost:8001/api/numbers/sip/register",
                          headers=H, json=body, timeout=30)
        assert r.status_code == 502, f"expected 502, got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail")
        assert detail is not None
        # detail should be the ElevenLabs error dict/obj
        assert isinstance(detail, (dict, str))
        # Also verify public URL returns 502 (body masked by ingress but code is right).
        r2 = requests.post(f"{BASE_URL}/api/numbers/sip/register",
                           headers=H, json=body, timeout=30)
        assert r2.status_code == 502


# --- 4. POST /api/numbers/call/test ----------------------------------------
class TestCallTest:
    def test_no_sip_registered_returns_400(self, mongo):
        # Ensure clean state — no didww_sip entries
        mongo.connected_numbers.delete_many({"provider": "didww_sip"})
        r = requests.post(f"{BASE_URL}/api/numbers/call/test", headers=H,
                          json={"queue_id": "test", "to_number": "+573001234567"})
        assert r.status_code == 400, r.text
        assert "No hay número SIP registrado en ElevenLabs. Regístralo primero." \
            in r.json().get("detail", "")

    def test_agent_id_missing_after_insert(self, mongo):
        # Insert a fake registered SIP number directly in Mongo
        from datetime import datetime, timezone
        import uuid
        doc = {
            "id": str(uuid.uuid4()),
            "phone_number": "+573001234567",
            "friendly_name": "TEST_didww_fake",
            "country": "CO",
            "provider": "didww_sip",
            "status": "sip_registered",
            "elevenlabs_phone_number_id": "fake",
            "sip_domain": "sip.fake.example.com",
            "caller_id_number": "+573001234567",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        mongo.connected_numbers.insert_one(dict(doc))
        try:
            r = requests.post(f"{BASE_URL}/api/numbers/call/test", headers=H,
                              json={"queue_id": "test", "to_number": "+573001234567"})
            assert r.status_code == 400, r.text
            assert "ELEVENLABS_AGENT_ID" in r.json().get("detail", "")
        finally:
            mongo.connected_numbers.delete_many({"provider": "didww_sip",
                                                 "friendly_name": "TEST_didww_fake"})


# --- 5. GET /api/numbers includes didww_sip entries ------------------------
class TestListNumbers:
    def test_list_includes_didww_sip(self, mongo):
        from datetime import datetime, timezone
        import uuid
        doc_id = str(uuid.uuid4())
        mongo.connected_numbers.insert_one({
            "id": doc_id,
            "phone_number": "+573009999999",
            "friendly_name": "TEST_list_didww",
            "country": "CO",
            "provider": "didww_sip",
            "status": "sip_registered",
            "elevenlabs_phone_number_id": "fake",
            "sip_domain": "sip.fake.example.com",
            "caller_id_number": "+573009999999",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            r = requests.get(f"{BASE_URL}/api/numbers", headers=H)
            assert r.status_code == 200, r.text
            nums = r.json()
            found = [n for n in nums if n.get("friendly_name") == "TEST_list_didww"]
            assert found, "didww_sip entry not returned"
            assert found[0]["provider"] == "didww_sip"
        finally:
            mongo.connected_numbers.delete_one({"id": doc_id})


# --- 6. Regressions --------------------------------------------------------
class TestRegressions:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health")
        assert r.status_code == 200

    def test_queue(self):
        r = requests.get(f"{BASE_URL}/api/queue", headers=H)
        assert r.status_code == 200

    def test_voices_still_six(self):
        r = requests.get(f"{BASE_URL}/api/voices", headers=H)
        assert r.status_code == 200
        voices = r.json()
        assert len(voices) == 6, f"expected 6 voices, got {len(voices)}"

    def test_metrics(self):
        r = requests.get(f"{BASE_URL}/api/metrics", headers=H)
        assert r.status_code == 200

    def test_webhooks_events(self):
        r = requests.get(f"{BASE_URL}/api/webhooks/events", headers=H)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
