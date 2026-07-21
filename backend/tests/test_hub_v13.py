"""Litper Connect Hub v1.3 — voices/TTS/metrics/agent tests."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://litper-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
H = {"X-API-Key": KEY, "Content-Type": "application/json"}


# ---- Regression: health + auth ----
def test_health_public_no_key():
    r = requests.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True

@pytest.mark.parametrize("path", ["/carriers", "/queue", "/orders", "/metrics"])
def test_auth_guard(path):
    assert requests.get(f"{API}{path}").status_code == 401
    assert requests.get(f"{API}{path}", headers=H).status_code == 200


# ---- Voices seeded (exactly 6) ----
EXPECTED_VOICES = {
    "scn1gPWkdVd8FhODJoei": {"name": "Sofía CO", "country": "CO", "is_default": True},
    "wmXH34EF7LAsKTjOZWWt": {"name": "Sofía EC", "country": "EC", "is_default": True},
    "MqSrMUk8EHh32HBKytrG": {"name": "Voz 3"},
    "57D8YIbQSuE3REDPO6Vm": {"name": "Voz 4"},
    "86V9x9hrQds83qf7zaGn": {"name": "Voz 5"},
    "VmejBeYhbrcTPwDniox7": {"name": "Voz 6"},
}

def test_voices_seed_exactly_6():
    r = requests.get(f"{API}/voices", headers=H)
    assert r.status_code == 200, r.text
    voices = r.json()
    assert isinstance(voices, list) and len(voices) == 6, f"got {len(voices)}"
    by_id = {v.get("elevenlabs_voice_id") or v.get("voice_id"): v for v in voices}
    for vid, expected in EXPECTED_VOICES.items():
        assert vid in by_id, f"missing {vid}"
        v = by_id[vid]
        assert v["name"] == expected["name"]
        if "country" in expected:
            assert v.get("country") == expected["country"]
        if "is_default" in expected:
            assert v.get("is_default") is True


def test_voices_default_co():
    r = requests.get(f"{API}/voices/default/CO", headers=H)
    assert r.status_code == 200
    assert r.json()["name"] == "Sofía CO"

def test_voices_default_ec():
    r = requests.get(f"{API}/voices/default/EC", headers=H)
    assert r.status_code == 200
    assert r.json()["name"] == "Sofía EC"


# ---- ElevenLabs available ----
def test_elevenlabs_available():
    r = requests.get(f"{API}/voices/elevenlabs/available", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert isinstance(d.get("voices"), list) and len(d["voices"]) > 0


# ---- TTS preview ----
def test_tts_preview_success():
    r = requests.post(f"{API}/voices/preview", headers=H,
                      json={"voice_id": "scn1gPWkdVd8FhODJoei", "text": "Hola"}, timeout=60)
    assert r.status_code == 200, r.text[:500]
    ct = r.headers.get("content-type", "")
    assert "audio/mpeg" in ct, f"content-type: {ct}"
    assert len(r.content) > 1024, f"body size: {len(r.content)}"


def test_tts_preview_invalid_voice_returns_502():
    r = requests.post(f"{API}/voices/preview", headers=H,
                      json={"voice_id": "INVALID_XYZ_000", "text": "Hola"}, timeout=60)
    assert r.status_code == 502, f"got {r.status_code}: {r.text[:300]}"


# ---- Metrics new schema ----
@pytest.fixture(scope="module")
def metrics():
    r = requests.get(f"{API}/metrics", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def test_metrics_top_keys(metrics):
    for k in ("norte", "funnel", "whatsapp", "operacion", "costos", "trend", "filters",
              "queue_by_status"):  # legacy still present
        assert k in metrics, f"missing top-level key {k}"


def test_metrics_norte(metrics):
    n = metrics["norte"]
    for k in ("recovery_rate", "rto_reduction", "cpr_cop", "roi_cop"):
        assert k in n, f"missing norte.{k}"
        item = n[k]
        assert "value" in item and "status" in item
        # target OR targetMax variants
        target_keys = {"target", "targetMax", "target_max", "targetMin", "target_min", "baseline"}
        # roi_cop is a pure computed value; no target expected
        if k != "roi_cop":
            assert target_keys & set(item.keys()), f"norte.{k} missing target: {item.keys()}"


def test_metrics_funnel(metrics):
    f = metrics["funnel"]
    stages = f["stages"]
    assert len(stages) == 5
    names = [s["name"] for s in stages]
    assert names == ["Programados", "Marcados", "Contactados", "Confirmados", "Recogidos"]
    for s in stages:
        assert "count" in s
    for k in ("connect_rate", "right_party", "confirmation_rate", "avg_attempts_to_contact",
             "no_answer_pct", "wrong_number_pct"):
        assert k in f, f"missing funnel.{k}"


def test_metrics_whatsapp(metrics):
    w = metrics["whatsapp"]
    for k in ("sent", "delivered", "received"):
        assert isinstance(w.get(k), int), f"whatsapp.{k} not int: {w.get(k)}"
    for k in ("read_rate", "response_rate", "conversion_to_confirmation", "avg_response_min"):
        assert k in w and "value" in w[k] and "status" in w[k]


def test_metrics_operacion(metrics):
    o = metrics["operacion"]
    bs = o["by_semaphore"]
    assert isinstance(bs, list)
    names = {i["name"] for i in bs}
    assert {"rojo", "amarillo", "verde", "gris"} <= names
    assert isinstance(o.get("vencen_hoy"), list)
    assert isinstance(o.get("vencen_manana"), list)
    er = o["escalation_rate"]
    assert "value" in er and "status" in er
    assert isinstance(o.get("tasks_by_type"), list)


def test_metrics_costos(metrics):
    c = metrics["costos"]
    days = c["days"]
    assert isinstance(days, list) and len(days) > 0
    d0 = days[0]
    for k in ("twilio_cop", "elevenlabs_cop", "whatsapp_cop", "llm_cop", "total_cop"):
        assert k in d0, f"missing costos.days[0].{k}"
    assert isinstance(c.get("totals"), dict)
    assert isinstance(c.get("config"), dict)


def test_metrics_trend(metrics):
    t = metrics["trend"]
    for k in ("recovery_rate_14d", "cpr_14d"):
        arr = t[k]
        assert isinstance(arr, list) and len(arr) == 14, f"{k} len={len(arr)}"
        for item in arr:
            assert "date" in item and "value" in item


def test_metrics_filters_country():
    r = requests.get(f"{API}/metrics", headers=H,
                     params={"country": "CO", "date_from": "2026-01-01", "date_to": "2026-12-31"})
    assert r.status_code == 200
    assert r.json()["filters"].get("country") == "CO"


def test_metrics_filters_carrier():
    r = requests.get(f"{API}/metrics", headers=H, params={"carrier_slug": "envia"})
    assert r.status_code == 200


# ---- Chatea /me ----
def test_chatea_pro_test():
    r = requests.post(f"{API}/connectors/chatea_pro/test", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    assert d.get("workspace_name")


# ---- Agent ----
def test_agent_run_get_queue():
    r = requests.post(f"{API}/agent/run", headers=H,
                      json={"text": "¿cuántos pedidos en rojo tengo?"}, timeout=90)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d.get("final_text")
    tool_calls = d.get("tool_calls", []) or []
    for step in d.get("steps", []) or []:
        tool_calls.extend(step.get("tool_calls", []) or [])
    assert any(tc.get("name") == "get_queue" or tc.get("tool") == "get_queue" for tc in tool_calls), tool_calls


# ---- Regression seeds ----
def test_novedades_18():
    r = requests.get(f"{API}/carriers/novedades", headers=H)
    assert r.status_code == 200
    assert len(r.json()) == 18

def test_skills_4():
    r = requests.get(f"{API}/skills", headers=H)
    assert r.status_code == 200
    assert len(r.json()) == 4
