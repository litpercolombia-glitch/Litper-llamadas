"""Litper Connect Hub — end-to-end backend tests."""
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://litper-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
H = {"X-API-Key": KEY, "Content-Type": "application/json"}
BOGOTA = ZoneInfo("America/Bogota")
TODAY = date.today().isoformat()


# ---- health & auth ----
def test_health_public():
    r = requests.get(f"{API}/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["service"] == "litper-connect-hub"


def test_carriers_requires_key():
    r = requests.get(f"{API}/carriers")
    assert r.status_code == 401
    assert "X-API-Key" in r.json().get("detail", "")


def test_carriers_list():
    r = requests.get(f"{API}/carriers", headers=H)
    assert r.status_code == 200
    docs = r.json()
    assert len(docs) == 12
    slugs = {c["slug"]: c for c in docs}
    assert slugs["envia"]["office_claim_max_days"] == 1
    assert slugs["servientrega"]["office_claim_max_days"] == 8


# ---- office-status ----
def test_office_status_envia_rojo():
    r = requests.get(f"{API}/carriers/envia/office-status",
                     headers=H, params={"office_arrival_date": TODAY})
    assert r.status_code == 200
    d = r.json()
    assert d["semaphore"] == "rojo" and d["days_left"] == 1


def test_office_status_servientrega_verde():
    r = requests.get(f"{API}/carriers/servientrega/office-status",
                     headers=H, params={"office_arrival_date": TODAY})
    assert r.status_code == 200
    assert r.json()["semaphore"] == "verde"


def test_office_status_99minutos_gris():
    r = requests.get(f"{API}/carriers/99-minutos/office-status",
                     headers=H, params={"office_arrival_date": TODAY})
    assert r.status_code == 200
    assert r.json()["semaphore"] == "gris"


# ---- orders CRUD ----
def test_orders_create_list_get():
    payload = {"customer_name": "TEST_Order", "customer_phone": "+573009999999",
               "carrier_slug": "envia", "total_amount": 10000, "currency": "COP",
               "products": [{"name": "x", "qty": 1, "price": 10000}],
               "office_arrival_date": TODAY, "external_ref": "TEST-ORD-001"}
    r = requests.post(f"{API}/orders", headers=H, json=payload)
    assert r.status_code == 201, r.text
    oid = r.json()["id"]

    r2 = requests.get(f"{API}/orders/{oid}", headers=H)
    assert r2.status_code == 200 and r2.json()["customer_name"] == "TEST_Order"

    r3 = requests.get(f"{API}/orders", headers=H)
    assert r3.status_code == 200 and any(o["id"] == oid for o in r3.json())


# ---- queue enrichment ----
@pytest.fixture(scope="module")
def queue_items():
    r = requests.get(f"{API}/queue", headers=H, params={"limit": 500})
    assert r.status_code == 200
    return r.json()


def _find_by_name(items, name):
    return next((i for i in items if (i.get("customer_name") or "") == name), None)


def test_queue_enrichment_fields(queue_items):
    assert queue_items, "queue empty"
    q = queue_items[0]
    for k in ("customer_name", "customer_phone", "carrier_name", "city",
              "total_amount", "currency", "tracking_number", "days_left", "semaphore"):
        assert k in q, f"missing {k}"


def test_queue_sandra_rojo(queue_items):
    s = _find_by_name(queue_items, "Sandra Ruiz")
    assert s and s["semaphore"] == "rojo" and s["days_left"] <= 1


def test_queue_carlos_verde(queue_items):
    c = _find_by_name(queue_items, "Carlos Mejía")
    assert c and c["semaphore"] == "verde" and 5 <= c["days_left"] <= 8


def test_queue_maria_gris(queue_items):
    m = _find_by_name(queue_items, "María Torres")
    assert m and m["semaphore"] == "gris"


# ---- cadence ----
def _bogota_date(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(BOGOTA).date().isoformat()


def test_cadence_envia_compressed(queue_items):
    sandra = _find_by_name(queue_items, "Sandra Ruiz")
    r = requests.post(f"{API}/calls/schedule", headers=H,
                      json={"queue_id": sandra["id"]})
    assert r.status_code == 200, r.text
    attempts = r.json()["attempts"]
    assert len(attempts) == 5
    dates = {_bogota_date(a["scheduled_at"]) for a in attempts}
    assert len(dates) == 1, f"expected same day, got {dates}"
    assert [a["channel"] for a in attempts] == ["call"] * 4 + ["whatsapp"]
    windows = [a["window"] for a in attempts]
    for i in range(1, len(windows)):
        assert windows[i] != windows[i-1], f"back-to-back window at {i}"


def test_cadence_servientrega_spread(queue_items):
    carlos = _find_by_name(queue_items, "Carlos Mejía")
    r = requests.post(f"{API}/calls/schedule", headers=H,
                      json={"queue_id": carlos["id"]})
    assert r.status_code == 200
    attempts = r.json()["attempts"]
    dates = {_bogota_date(a["scheduled_at"]) for a in attempts}
    assert 2 <= len(dates) <= 3, f"expected 2-3 dates, got {dates}"
    assert attempts[-1]["channel"] == "whatsapp"
    windows = [a["window"] for a in attempts]
    for i in range(1, len(windows)):
        assert windows[i] != windows[i-1]


def test_cadence_get(queue_items):
    sandra = _find_by_name(queue_items, "Sandra Ruiz")
    r = requests.get(f"{API}/calls/schedule/{sandra['id']}", headers=H)
    assert r.status_code == 200
    assert len(r.json()["attempts"]) == 5


# ---- attempt-result stops ----
def _new_queue(carrier="envia", phone="+5730055500{}"):
    import random
    p = phone.format(random.randint(10, 99))
    payload = {"customer_name": "TEST_AR", "customer_phone": p,
               "carrier_slug": carrier, "total_amount": 1000, "currency": "COP",
               "office_arrival_date": TODAY,
               "external_ref": f"TEST-AR-{random.randint(10000,99999)}"}
    r = requests.post(f"{API}/orders", headers=H, json=payload)
    assert r.status_code == 201
    oid = r.json()["id"]
    # find its queue item
    qs = requests.get(f"{API}/queue", headers=H, params={"limit": 500}).json()
    qi = next(q for q in qs if q["order_id"] == oid)
    requests.post(f"{API}/calls/schedule", headers=H, json={"queue_id": qi["id"]})
    return qi["id"], p, oid


def test_attempt_result_confirmado_stops():
    qid, _phone, _oid = _new_queue()
    r = requests.post(f"{API}/calls/attempt-result", headers=H,
                      json={"queue_id": qid, "attempt_number": 1, "result": "confirmado"})
    assert r.status_code == 200
    sched = requests.get(f"{API}/calls/schedule/{qid}", headers=H).json()
    statuses = [a["status"] for a in sched["attempts"]]
    assert statuses[0] == "done"
    assert all(s == "skipped" for s in statuses[1:])
    qi = requests.get(f"{API}/queue/{qid}", headers=H).json()
    assert qi["status"] == "confirmado"


def test_attempt_result_no_contesta_x3_whatsapp():
    qid, phone, _oid = _new_queue()
    for i in (1, 2, 3):
        r = requests.post(f"{API}/calls/attempt-result", headers=H,
                          json={"queue_id": qid, "attempt_number": i, "result": "no_contesta"})
        assert r.status_code == 200
    msgs = requests.get(f"{API}/whatsapp/messages", headers=H, params={"limit": 200}).json()
    hit = [m for m in msgs if m.get("phone") == phone and m.get("direction") == "outbound"]
    assert hit, f"no outbound WhatsApp for {phone}"


def test_attempt_result_numero_incorrecto_task():
    qid, _phone, _oid = _new_queue()
    r = requests.post(f"{API}/calls/attempt-result", headers=H,
                      json={"queue_id": qid, "attempt_number": 1, "result": "numero_incorrecto"})
    assert r.status_code == 200
    tasks = requests.get(f"{API}/tasks", headers=H, params={"limit": 500}).json()
    hit = [t for t in tasks if t.get("queue_id") == qid
           and t.get("type") == "cambio_direccion" and t.get("source") == "ai"]
    assert hit, "no cambio_direccion/ai task"


# ---- whatsapp send ----
def test_whatsapp_send_never_crashes():
    r = requests.post(f"{API}/whatsapp/send", headers=H,
                      json={"phone": "+573000000000", "text": "TEST_hola"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] in ("sent", "failed")
    assert d["phone"] == "+573000000000"


# ---- tasks CRUD ----
def test_tasks_crud():
    r = requests.post(f"{API}/tasks", headers=H,
                      json={"type": "otro", "description": "TEST_task", "source": "agent"})
    assert r.status_code == 201
    tid = r.json()["id"]
    r2 = requests.get(f"{API}/tasks", headers=H)
    assert r2.status_code == 200 and any(t["id"] == tid for t in r2.json())
    r3 = requests.patch(f"{API}/tasks/{tid}", headers=H, json={"status": "resolved"})
    assert r3.status_code == 200 and r3.json()["status"] == "resolved"
    r4 = requests.delete(f"{API}/tasks/{tid}", headers=H)
    assert r4.status_code == 200
    r5 = requests.get(f"{API}/tasks/{tid}", headers=H)
    assert r5.status_code == 404


# ---- metrics ----
def test_metrics_keys():
    r = requests.get(f"{API}/metrics", headers=H)
    assert r.status_code == 200
    d = r.json()
    for k in ("queue_by_status", "queue_total", "orders_total", "attempts_today",
              "completed_today", "contact_rate_pct", "tasks_open", "messages_24h",
              "generated_at"):
        assert k in d


# ---- translate ----
def test_translate_es_to_en():
    r = requests.post(f"{API}/translate", headers=H,
                      json={"text": "Hola, ¿cómo estás?", "target": "en"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["text"] and d["provider"].startswith("library:")


# ---- webhooks ----
def test_webhook_chatea_no_auth_sets_ya_recogio():
    r = requests.post(f"{API}/webhooks/chatea",
                      json={"from": "+573001112233", "text": "ya lo recogí"})
    assert r.status_code == 200
    # verify Sandra queue changed
    qs = requests.get(f"{API}/queue", headers=H, params={"limit": 500}).json()
    s = _find_by_name(qs, "Sandra Ruiz")
    assert s and s["status"] == "ya_recogio"


def test_webhook_vapi_confirmado():
    qid, _phone, _oid = _new_queue(carrier="servientrega")
    r = requests.post(f"{API}/webhooks/vapi",
                      json={"queue_id": qid, "attempt_number": 1, "result": "confirmado"})
    assert r.status_code == 200
    qi = requests.get(f"{API}/queue/{qid}", headers=H).json()
    assert qi["status"] == "confirmado"


# ---- connectors ----
def test_connectors_list_and_tests():
    r = requests.get(f"{API}/connectors", headers=H)
    assert r.status_code == 200
    conns = r.json()
    keys = {c["key"] for c in conns}
    assert {"chatea_pro", "dropi", "whatsapp_business", "supabase"} <= keys

    r2 = requests.post(f"{API}/connectors/chatea_pro/test", headers=H)
    assert r2.status_code == 200
    assert "ok" in r2.json()

    r3 = requests.post(f"{API}/connectors/supabase/test", headers=H)
    assert r3.status_code == 200
    assert "status" in r3.json()


# ---- docs ----
def test_docs_html():
    for path in ("/docs", "/redoc"):
        r = requests.get(f"{BASE}{path}")
        assert r.status_code == 200 and "html" in r.headers.get("content-type", "").lower()
