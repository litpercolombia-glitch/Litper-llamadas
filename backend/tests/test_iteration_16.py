"""Iteration 16: dual auth (JWT cookie OR X-API-Key), /agents/cascade,
CEO report + novedades ticks scheduler endpoints, and regression on
prior auth + 5-agent orchestrator behavior.
"""
import os
import requests
import pytest
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: parse from /app/frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
assert BASE_URL, "REACT_APP_BACKEND_URL missing"

API = f"{BASE_URL}/api"
EMAIL = "qa2@litper.co"
PASSWORD = "Litper!2026"
LEGACY_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def cookie_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert s.cookies.get("litper_session"), "cookie not set"
    return s


@pytest.fixture(scope="session")
def key_session():
    s = requests.Session()
    s.headers.update({"X-API-Key": LEGACY_KEY})
    return s


# ---------- AUTH MIGRATION ----------
class TestAuthMigration:
    def test_queue_with_cookie_only(self, cookie_session):
        r = cookie_session.get(f"{API}/queue?limit=1", timeout=15)
        assert r.status_code == 200, r.text

    def test_queue_without_anything(self):
        r = requests.get(f"{API}/queue?limit=1", timeout=15)
        assert r.status_code == 401

    def test_queue_with_legacy_key(self, key_session):
        r = key_session.get(f"{API}/queue?limit=1", timeout=15)
        assert r.status_code == 200

    def test_orders_with_cookie(self, cookie_session):
        r = cookie_session.get(f"{API}/orders?limit=1", timeout=15)
        assert r.status_code == 200

    def test_orders_without_anything(self):
        r = requests.get(f"{API}/orders?limit=1", timeout=15)
        assert r.status_code == 401

    def test_orchestrate_with_cookie(self, cookie_session):
        r = cookie_session.post(f"{API}/agents/orchestrate", json={}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "chain" in data
        for k in ["riesgo_rto", "confirmacion_cod", "novedades",
                  "rescate_oficina", "analitica_operativa"]:
            assert k in data["chain"], f"missing {k}"

    def test_orchestrate_without_anything(self):
        r = requests.post(f"{API}/agents/orchestrate", json={}, timeout=15)
        assert r.status_code == 401


# ---------- CASCADE ----------
class TestCascade:
    def test_red_this_week(self, cookie_session):
        r = cookie_session.post(f"{API}/agents/cascade",
                                json={"segment": "red_this_week", "limit": 5},
                                timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("processed"), int)
        assert isinstance(d.get("results"), list) and len(d["results"]) <= 5
        assert isinstance(d.get("hitl_required"), list)
        s = d.get("summary") or {}
        assert "kpis" in s and "high_risk" in s and "rescate_planned" in s

    def test_new_today(self, cookie_session):
        r = cookie_session.post(f"{API}/agents/cascade",
                                json={"segment": "new_today", "limit": 3},
                                timeout=30)
        assert r.status_code == 200
        assert "results" in r.json()

    def test_office_all(self, cookie_session):
        r = cookie_session.post(f"{API}/agents/cascade",
                                json={"segment": "office_all", "limit": 3},
                                timeout=30)
        assert r.status_code == 200

    def test_bogus_segment(self, cookie_session):
        r = cookie_session.post(f"{API}/agents/cascade",
                                json={"segment": "bogus", "limit": 5},
                                timeout=30)
        # per spec, must NOT 500. May return processed=0 or process fallback (empty q).
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("processed"), int)


# ---------- SCHEDULER ENDPOINTS ----------
class TestScheduler:
    def test_ceo_report_run_now_and_get(self, cookie_session):
        r = cookie_session.post(f"{API}/agents/ceo-report/run-now", timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        r2 = cookie_session.get(f"{API}/agents/ceo-report", timeout=15)
        assert r2.status_code == 200
        d = r2.json()
        assert d.get("available") is True, d
        report = d.get("report") or {}
        today = datetime.now(timezone.utc).date().isoformat()
        assert report.get("date") == today, f"date mismatch: {report.get('date')} vs {today}"

    def test_novedades_ticks(self, cookie_session):
        # Trigger the sweep by hitting endpoint after enough time — but we can
        # only verify the endpoint returns. Cron interval=15min with
        # next_run_time=now → should already have populated at least one tick.
        r = cookie_session.get(f"{API}/agents/novedades-ticks?limit=1", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list)
        if d:
            assert "buckets" in d[0]
            assert "total" in d[0]


# ---------- REGRESSION ----------
class TestRegression:
    def test_login_and_me(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"email": EMAIL, "password": PASSWORD}, timeout=15)
        assert r.status_code == 200
        me = s.get(f"{API}/auth/me", timeout=15)
        assert me.status_code == 200
        body = me.json()
        email = body.get("email") or (body.get("user") or {}).get("email")
        assert email == EMAIL

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": EMAIL, "password": "wrong"}, timeout=15)
        assert r.status_code in (400, 401)

    def test_google_session_bogus(self):
        r = requests.post(f"{API}/auth/google/session",
                          headers={"X-Session-ID": "bogus"}, timeout=15)
        assert r.status_code in (400, 401, 500), r.status_code

    def test_agents_list(self, cookie_session):
        r = cookie_session.get(f"{API}/agents", timeout=15)
        assert r.status_code == 200
        agents = r.json().get("agents", [])
        assert len(agents) == 5
