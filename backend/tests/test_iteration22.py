"""Iteration 22 — Retell/Telnyx/BETA custom agents, tools, calls webhook."""
import os, re, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0]
BASE = BASE.rstrip("/")
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
EMAIL, PWD = "qa2@litper.co", "Litper!2026"
ORG_ID = "litper-qa-0712bf"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers["X-API-Key"] = API_KEY
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PWD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


# ---------- TEMPLATES ----------
def test_templates_exact(sess):
    r = sess.get(f"{BASE}/api/custom-agents/templates")
    assert r.status_code == 200
    tpls = {t["key"]: t for t in r.json()["templates"]}
    for k in ["rescate_oficina", "confirmacion_cod", "citas", "cobranza", "personalizado"]:
        assert k in tpls, f"missing {k}"
    assert len(tpls) == 5

    resc = tpls["rescate_oficina"]["prompt"]
    assert "Sofía, asesora de {{empresa}}" in resc
    assert "ANTIFLUIDO, nunca impermeable" in resc
    assert "Máx 2 frases por turno" in resc

    conf = tpls["confirmacion_cod"]["prompt"]
    assert "confirmar_pedido(direccion, franja)" in conf
    assert "antifluido" in conf.lower()

    cit = tpls["citas"]["prompt"]
    assert "NUNCA calcules fechas" in cit
    assert "consultar_disponibilidad" in cit

    cob = tpls["cobranza"]["prompt"]
    assert "DISCLOSURE OBLIGATORIO" in cob
    assert "enviar_link_pago" in cob
    assert "registrar_promesa_pago" in cob

    # No 'impermeable' anywhere
    for k, t in tpls.items():
        assert "impermeable" not in t["prompt"].lower() or "nunca impermeable" in t["prompt"].lower(), \
            f"'impermeable' found in {k}"


# ---------- TOOLS ----------
def test_tools_7(sess):
    r = sess.get(f"{BASE}/api/custom-agents/tools")
    assert r.status_code == 200
    tools = r.json()["tools"]
    keys = [t["key"] for t in tools]
    expected = ["reagendar_entrega","confirmar_pedido","consultar_disponibilidad",
                "enviar_whatsapp","transferir_a_humano",
                "registrar_promesa_pago","enviar_link_pago"]
    assert keys == expected
    for t in tools:
        should_money = t["key"] in {"registrar_promesa_pago","enviar_link_pago"}
        assert t["money"] == should_money


# ---------- DATE HELPERS ----------
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}-05:00$")

def test_consultar_disponibilidad(sess):
    r = sess.post(f"{BASE}/api/agent-tools/consultar_disponibilidad",
                  json={"n": 3, "duracion_min": 30})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert len(d["slots"]) == 3
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    for s in d["slots"]:
        assert ISO_RE.match(s["iso"]), f"bad iso {s['iso']}"
        assert s["zona"] == "America/Bogota"
        dt = datetime.fromisoformat(s["iso"])
        assert dt > now_utc, f"slot not in future: {s['iso']}"
        # Mon-Sat 08-18 Bogota
        assert dt.weekday() != 6
        assert 8 <= dt.hour < 18


def test_proximo_horario(sess):
    r = sess.post(f"{BASE}/api/agent-tools/proximo_horario_disponible", json={})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    slot = d["slot"]
    assert ISO_RE.match(slot["iso"])
    assert slot["zona"] == "America/Bogota"


# ---------- MONEY GUARDRAIL ----------
def test_money_guardrail(sess):
    r = sess.post(f"{BASE}/api/agent-tools/registrar_promesa_pago",
                  json={"pedido_id": "TEST_p1", "fecha_iso": "2026-08-01T10:00:00-05:00"})
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is False and j["requires_human_confirmation"] is True

    r = sess.post(f"{BASE}/api/agent-tools/enviar_link_pago",
                  json={"telefono":"+573001112233","pedido_id":"TEST_p2","monto":100000})
    j = r.json()
    assert j["ok"] is False and j["requires_human_confirmation"] is True

    r = sess.post(f"{BASE}/api/agent-tools/registrar_promesa_pago",
                  json={"pedido_id":"TEST_p1","fecha_iso":"2026-08-01T10:00:00-05:00",
                        "human_confirmed": True})
    assert r.json()["ok"] is True

    r = sess.post(f"{BASE}/api/agent-tools/enviar_link_pago",
                  json={"telefono":"+573001112233","pedido_id":"TEST_p2","monto":100000,
                        "human_confirmed": True})
    assert r.json()["ok"] is True


def test_non_money_tools(sess):
    r = sess.post(f"{BASE}/api/agent-tools/reagendar_entrega",
                  json={"pedido_id":"TEST_x","nueva_fecha_iso":"2026-08-01T10:00:00-05:00"})
    assert r.json()["ok"] is True
    r = sess.post(f"{BASE}/api/agent-tools/confirmar_pedido",
                  json={"pedido_id":"TEST_x"})
    assert r.json()["ok"] is True
    r = sess.post(f"{BASE}/api/agent-tools/enviar_whatsapp",
                  json={"telefono":"+573001112233","mensaje":"hi"})
    assert r.json()["ok"] is True
    r = sess.post(f"{BASE}/api/agent-tools/transferir_a_humano",
                  json={"telefono":"+573001112233"})
    assert r.json()["ok"] is True


# ---------- CALLS WEBHOOK ----------
def test_calls_webhook(sess):
    # Unauthenticated request
    anon = requests.Session()
    body = {
        "event": "call_ended",
        "call": {
            "call_id": "TEST_call_it22_001",
            "agent_id": "retell_test_1",
            "to_number": "+573001112233",
            "call_length": 73,
            "transcript": "hola prueba",
            "recording_url": "https://example.com/rec.mp3",
            "metadata": {"zynex_org_id": ORG_ID, "zynex_agent_id": "AGT_TEST"},
        }
    }
    r = anon.post(f"{BASE}/api/calls/webhook", json=body, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True and j["stored"] == "TEST_call_it22_001"

    # UPSERT
    r2 = anon.post(f"{BASE}/api/calls/webhook", json=body, timeout=15)
    assert r2.status_code == 200

    # Bad payload
    r3 = anon.post(f"{BASE}/api/calls/webhook", json={"foo":"bar"}, timeout=15)
    assert r3.status_code == 400


def test_calls_list_auth(sess):
    r = sess.get(f"{BASE}/api/calls")
    assert r.status_code == 200
    calls = r.json()["calls"]
    ids = [c.get("call_id") for c in calls]
    # our webhook row should appear (single, not duplicated)
    assert ids.count("TEST_call_it22_001") == 1

    r = sess.get(f"{BASE}/api/calls?agent_id=AGT_TEST")
    assert r.status_code == 200
    for c in r.json()["calls"]:
        assert c["agent_id"] == "AGT_TEST"


# ---------- RETELL BETA CREATE + TEST-CALL ----------
CREATED_ID = {"id": None}

def test_create_agent_beta(sess):
    payload = {
        "nombre": "TEST_it22_agent",
        "proposito": "rescate_oficina",
        "prompt": "prompt de prueba",
        "voz_id": "EXAVITQu4vr4xnSDxMaL",
        "tools": ["reagendar_entrega","confirmar_pedido"],
        "estado": "en_vivo",
    }
    r = sess.post(f"{BASE}/api/custom-agents", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    ag = j["agent"]
    assert ag.get("retell_agent_id") is None
    CREATED_ID["id"] = ag["id"]


def test_patch_agent(sess):
    aid = CREATED_ID["id"]
    assert aid
    r = sess.patch(f"{BASE}/api/custom-agents/{aid}",
                   json={"prompt": "nuevo prompt actualizado"})
    assert r.status_code == 200, r.text
    assert r.json()["agent"]["prompt"] == "nuevo prompt actualizado"


def test_test_call_beta(sess):
    aid = CREATED_ID["id"]
    r = sess.post(f"{BASE}/api/custom-agents/{aid}/test-call",
                  json={"numero": "+573001112233"})
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["beta"] is True
    assert j["dialed"] is False
    assert "Beta —" in j["detail"]
    assert j["checks"] == {"retell": False, "telnyx": False, "elevenlabs": False}


def test_legacy_tools_allowed(sess):
    payload = {
        "nombre": "TEST_legacy_tools",
        "proposito": "personalizado",
        "prompt": "x",
        "tools": ["reagendar","terminar_llamada","registrar_pago"],
    }
    r = sess.post(f"{BASE}/api/custom-agents", json=payload)
    assert r.status_code == 200, r.text
    # cleanup
    sess.delete(f"{BASE}/api/custom-agents/{r.json()['agent']['id']}")


# ---------- REGRESSION ----------
def test_regression_agents_and_rules(sess):
    r = sess.get(f"{BASE}/api/agents")
    assert r.status_code == 200
    ags = r.json()
    if isinstance(ags, dict): ags = ags.get("agents") or ags.get("data") or []
    assert len(ags) == 5

    r = sess.get(f"{BASE}/api/whatsapp/rules")
    assert r.status_code == 200
    rules = r.json()
    if isinstance(rules, dict): rules = rules.get("rules") or rules.get("templates") or rules
    # Might return dict with 'templates'
    if isinstance(rules, list):
        assert len(rules) == 3


# ---------- CLEANUP ----------
def test_cleanup(sess):
    aid = CREATED_ID["id"]
    if aid:
        sess.delete(f"{BASE}/api/custom-agents/{aid}")
    # cleanup call rows
    # Best effort — mongo direct not available here. Leave for future cleanup.
