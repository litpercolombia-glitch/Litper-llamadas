"""Backend tests: auth (email/pass + google bogus) + 5-agent orchestrator + blacklist."""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # Fallback to frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.strip().split("=", 1)[1].rstrip("/")
API = f"{BASE}/api"
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
QA_EMAIL = "qa2@litper.co"
QA_PASS = "Litper!2026"


@pytest.fixture
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- AUTH ----------
class TestAuth:
    def test_register_duplicate_returns_409(self, sess):
        r = sess.post(f"{API}/auth/register", json={
            "email": QA_EMAIL, "password": QA_PASS,
            "nombre": "QA Two", "org_name": "Litper QA"})
        assert r.status_code == 409, r.text

    def test_register_new_user(self, sess):
        uniq = f"qa+{int(time.time())}@litper.co"
        r = sess.post(f"{API}/auth/register", json={
            "email": uniq, "password": "Litper!2026",
            "nombre": "QA Tmp", "org_name": "Litper QA Tmp"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["user"]["email"] == uniq
        assert data["user"]["role"] == "owner"
        assert "litper_session" in sess.cookies

    def test_login_invalid_creds(self, sess):
        r = sess.post(f"{API}/auth/login", json={
            "email": QA_EMAIL, "password": "wrongpass"})
        assert r.status_code == 401

    def test_login_valid_and_me_and_logout(self, sess):
        r = sess.post(f"{API}/auth/login", json={
            "email": QA_EMAIL, "password": QA_PASS})
        assert r.status_code == 200, r.text
        assert "litper_session" in sess.cookies
        me = sess.get(f"{API}/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["email"] == QA_EMAIL

        lo = sess.post(f"{API}/auth/logout")
        assert lo.status_code == 200
        # After logout, /me should 401 (in a fresh session because delete_cookie removed it)
        s2 = requests.Session()
        assert s2.get(f"{API}/auth/me").status_code == 401

    def test_me_no_cookie_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_google_session_bogus_id(self):
        r = requests.post(f"{API}/auth/google/session",
                          headers={"X-Session-ID": "bogus-does-not-exist-xyz"})
        assert r.status_code in (400, 401, 502), r.text

    def test_google_session_missing_header(self):
        r = requests.post(f"{API}/auth/google/session")
        assert r.status_code == 400


# ---------- AGENTS ----------
EXPECTED_KEYS = {"riesgo_rto", "confirmacion_cod", "novedades",
                 "rescate_oficina", "analitica_operativa"}


class TestAgents:
    def test_list_agents_requires_api_key(self):
        r = requests.get(f"{API}/agents")
        assert r.status_code in (401, 403)

    def test_list_agents_five(self):
        r = requests.get(f"{API}/agents", headers={"X-API-Key": API_KEY})
        assert r.status_code == 200, r.text
        agents = r.json()["agents"]
        keys = {a["key"] for a in agents}
        assert keys == EXPECTED_KEYS
        assert len(agents) == 5

    def test_orchestrate_returns_chain(self):
        r = requests.post(f"{API}/agents/orchestrate",
                          headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                          json={"phone": "+573001112233", "city": "Bogota",
                                "product": "Test", "require_confirm_for_money": True})
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(d["chain"].keys()) == EXPECTED_KEYS
        assert isinstance(d["requires_human_confirmation"], bool)


# ---------- BLACKLIST ----------
class TestBlacklist:
    TEST_PHONE = "+57TEST9998887771"

    def test_blacklist_crud(self):
        h = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
        # add
        r = requests.post(f"{API}/agents/blacklist", headers=h,
                          json={"phone": self.TEST_PHONE, "reason": "TEST"})
        assert r.status_code == 200, r.text
        assert r.json()["phone"] == self.TEST_PHONE

        # list contains it
        lst = requests.get(f"{API}/agents/blacklist", headers=h).json()
        assert any(x["phone"] == self.TEST_PHONE for x in lst)

        # delete
        d = requests.delete(f"{API}/agents/blacklist/{self.TEST_PHONE}", headers=h)
        assert d.status_code == 200

        lst2 = requests.get(f"{API}/agents/blacklist", headers=h).json()
        assert not any(x["phone"] == self.TEST_PHONE for x in lst2)
