"""Ronda 3 de arreglos — una prueba por cada punto del auditor (backend).

Unitarias: sin servidor vivo ni Mongo real (misma base en memoria que
test_aislamiento_org.py). Cliente A = "org-a", cliente B = "org-b".

  1. test-call sin telefonía → ok:false          2. Google tras compuerta de servidor
  3. formulario público de interesados apagado   4. métricas con claves neutras
  5. límite de intentos en login/registro        6. WhatsApp de voz solo al cliente;
                                                    tarjeta pendiente sin org_id
  7. webhooks (rotar, notas), reporte por zona, restos de nombres antiguos
"""
import os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BACKEND)

import pytest
import respx, httpx
import test_aislamiento_org as base           # fija la base en memoria y trae utilidades
from test_aislamiento_org import FAKE, Req, run, pedido, _app, _http, A, B

import ratelimit, scheduler, translation, webhook_tokens
import org_credentials as oc
from agent import loop as agent_loop
from routes import (auth, vip, metrics, custom_agents, org_profile, calls,
                    agent_tools as voz)

WA = "https://chateapro.app/api"


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    FAKE.c.clear()
    ratelimit.reset_all()
    for k in ("ENV", "ENVIRONMENT", "RENDER", "GOOGLE_LOGIN", "GOOGLE_SESSION_URL",
              "VIP_LEADS_PUBLIC", "VIP_LEADS_ORG", "VIP_GROUP_URL", "RETELL_API_KEY",
              "CHATEA_PRO_API_KEY", "PLATFORM_KEYS_ORGS", "PUBLIC_BASE_URL", "USD_TO_MXN",
              "TRUSTED_PROXY_HOPS", "DAILY_REPORT_HOUR"):
        monkeypatch.delenv(k, raising=False)


# ═════════════════ 1. LLAMADA DE PRUEBA SIN TELEFONÍA ═════════════════
def test_1_test_call_sin_telefonia_no_dice_ok():
    FAKE.custom_agents.docs.append({"id": "ag1", "org_id": A, "nombre": "Recepción",
                                    "prompt": "Saluda.", "voz_id": "v1"})
    r = run(custom_agents.test_call("ag1", custom_agents.TestCallIn(numero="+573001112233"), Req(A)))
    assert r["ok"] is False and r["dialed"] is False and r["beta"] is True
    assert r["error"] and "No se marcó" in r["error"] and r["detail"] == r["error"]
    assert "validada correctamente" not in r["error"]


# ═════════════════ 2. GOOGLE TRAS COMPUERTA DE SERVIDOR ═════════════════
@respx.mock
def test_2_google_session_apagado_404_y_sin_url_en_el_codigo(monkeypatch):
    app = _app(auth.router)
    cab = {"X-Session-ID": "s-1"}
    assert _http(app, "POST", "/api/auth/google/session", headers=cab).status_code == 404   # por defecto
    monkeypatch.setenv("GOOGLE_LOGIN", "1")                                                # falta la URL
    assert _http(app, "POST", "/api/auth/google/session", headers=cab).status_code == 404
    monkeypatch.delenv("GOOGLE_LOGIN")
    monkeypatch.setenv("GOOGLE_SESSION_URL", "https://sso.ejemplo.com/session")            # falta el interruptor
    assert _http(app, "POST", "/api/auth/google/session", headers=cab).status_code == 404
    assert FAKE.users.docs == []
    # encendido: se consulta SOLO la URL configurada
    monkeypatch.setenv("GOOGLE_LOGIN", "1")
    ruta = respx.get("https://sso.ejemplo.com/session").mock(
        return_value=httpx.Response(200, json={"email": "Ana@Ejemplo.com", "name": "Ana"}))
    r = _http(app, "POST", "/api/auth/google/session", headers=cab)
    assert r.status_code == 200 and ruta.called and r.json()["user"]["email"] == "ana@ejemplo.com"
    assert _http(app, "POST", "/api/auth/google/session").status_code == 400               # sin X-Session-ID
    fuente = open(os.path.join(BACKEND, "routes", "auth.py"), encoding="utf-8").read().lower()
    assert "emergent" not in fuente and "https://" not in fuente.replace('startswith("https://")', "")


# ═════════════════ 3. FORMULARIO PÚBLICO DE INTERESADOS ═════════════════
@respx.mock
def test_3_vip_leads_publico_apagado_limitado_y_sin_whatsapp(monkeypatch):
    app = _app(vip.public_router)
    lead = {"nombre": "Luis Pérez", "whatsapp": "+573009998877"}
    assert _http(app, "POST", "/api/vip-leads", json=lead).status_code == 404              # apagado por defecto
    assert _http(app, "GET", "/api/vip-leads/config").status_code == 404
    assert FAKE.vip_leads.docs == []
    monkeypatch.setenv("VIP_LEADS_PUBLIC", "1")
    run(oc.set_credentials("chatea_pro", {"api_key": "wa-key"}, "default"))                # hay WhatsApp conectado…
    envio = respx.post(f"{WA}/subscriber/send-text").mock(return_value=httpx.Response(200, json={"id": "m"}))
    info = respx.get(f"{WA}/subscriber/get-info").mock(return_value=httpx.Response(200, json={"id": 1}))
    ip1 = {"X-Forwarded-For": "203.0.113.7"}
    for _ in range(vip.PUBLIC_MAX_PER_HOUR):
        r = _http(app, "POST", "/api/vip-leads", json=lead, headers=ip1)
        assert r.status_code == 200 and r.json()["welcome_sent"] is False
    assert _http(app, "POST", "/api/vip-leads", json=lead, headers=ip1).status_code == 429  # el 6.º
    assert _http(app, "POST", "/api/vip-leads", json=lead,
                 headers={"X-Forwarded-For": "203.0.113.8"}).status_code == 200            # otra IP sí
    # …pero NO se escribe a un número sin verificar: solo se guarda el lead
    assert not envio.called and not info.called and FAKE.message_log.docs == []
    assert len(FAKE.vip_leads.docs) == vip.PUBLIC_MAX_PER_HOUR + 1
    assert all(d["org_id"] == "default" and d["welcome_sent"] is False for d in FAKE.vip_leads.docs)
    fuente = open(os.path.join(BACKEND, "routes", "vip.py"), encoding="utf-8").read().lower()
    assert "represados" not in fuente and "devoluciones" not in fuente and "send_message" not in fuente


# ═════════════════ 4. MÉTRICAS CON CLAVES NEUTRAS ═════════════════
def test_4_metricas_claves_neutras_y_alias_antiguos(monkeypatch):
    run(org_profile.save_profile(A, org_profile.OrgProfileIn(moneda="MXN")))
    monkeypatch.setenv("USD_TO_MXN", "18")
    o = pedido(A)
    q = FAKE.call_queue.docs[0]
    q["status"] = "confirmado"
    FAKE.call_schedules.docs.append({"org_id": A, "queue_id": q["id"], "attempts": [
        {"status": "done", "channel": "call", "result": "confirmado", "attempt_number": 1,
         "executed_at": datetime.now(timezone.utc).isoformat()}]})
    m = run(metrics.compute_metrics(A))
    n, t = m["norte"], m["costos"]["totals"]
    assert n["cpr"]["value"] > 0 and n["cpr"]["unit"] == "MXN"
    assert n["roi"]["total_cost"] > 0 and n["roi"]["recovered_value"] == o.total_amount
    # las antiguas siguen ahí como alias con el MISMO valor
    assert n["cpr_cop"] == n["cpr"] and n["roi_cop"] == n["roi"]
    assert n["roi"]["total_cost_cop"] == n["roi"]["total_cost"]
    assert n["roi"]["recovered_value_cop"] == n["roi"]["recovered_value"]
    for nueva, vieja in metrics.COST_ALIASES.items():
        assert t[nueva] == t[vieja]
        assert all(d[nueva] == d[vieja] for d in m["costos"]["days"])
    assert t["llamadas"] == round(t["telefonia"] + t["voz"], 2) > 0
    assert round(t["llamadas"] + t["whatsapp"] + t["ia"], 1) == round(t["total"], 1)
    assert m["costos"]["son_estimaciones"] is True
    # `supuestos` trae exactamente lo que la interfaz mapea campo por campo
    s = m["supuestos"]
    assert {"moneda", "moneda_perfil", "tipo_cambio_usd", "tipo_cambio_definido", "margen_pct",
            "tasa_base_pct", "minutos_por_llamada", "costos_unitarios_usd", "nota"} <= set(s)
    assert set(s["costos_unitarios_usd"]) == {"telefonia_por_min", "voz_ia_por_min",
                                              "whatsapp_por_msg", "llm_por_1k_tokens"}


# ═════════════════ 5. LÍMITE DE INTENTOS ═════════════════
def test_5_login_y_registro_10_fallos_por_ip_y_correo_dan_429():
    app = _app(auth.router)
    ip = {"X-Forwarded-For": "198.51.100.4"}
    alta = {"email": "ana@ejemplo.com", "password": "clave-buena-1", "nombre": "Ana", "org_name": "Sol"}
    assert _http(app, "POST", "/api/auth/register", json=alta, headers=ip).status_code == 200
    mal = {"email": "ana@ejemplo.com", "password": "incorrecta"}
    bien = {"email": "ana@ejemplo.com", "password": "clave-buena-1"}
    for _ in range(auth.AUTH_MAX_FAILS):
        assert _http(app, "POST", "/api/auth/login", json=mal, headers=ip).status_code == 401
    r = _http(app, "POST", "/api/auth/login", json=bien, headers=ip)                       # ni la buena pasa
    assert r.status_code == 429 and r.headers["retry-after"] == str(auth.AUTH_WINDOW_S)
    # otra IP, u otro correo desde la misma IP, no quedan bloqueados
    assert _http(app, "POST", "/api/auth/login", json=bien,
                 headers={"X-Forwarded-For": "198.51.100.5"}).status_code == 200
    assert _http(app, "POST", "/api/auth/login", json={"email": "otro@ejemplo.com", "password": "x"},
                 headers=ip).status_code == 401
    # un acierto borra la cuenta de fallos; pasada la ventana se desbloquea
    ip2 = {"X-Forwarded-For": "198.51.100.9"}
    for _ in range(auth.AUTH_MAX_FAILS - 1):
        _http(app, "POST", "/api/auth/login", json=mal, headers=ip2)
    assert _http(app, "POST", "/api/auth/login", json=bien, headers=ip2).status_code == 200
    assert _http(app, "POST", "/api/auth/login", json=mal, headers=ip2).status_code == 401
    clave = "auth:login:198.51.100.4:ana@ejemplo.com"
    assert ratelimit.count(clave, auth.AUTH_WINDOW_S) == auth.AUTH_MAX_FAILS
    import time
    assert ratelimit.count(clave, auth.AUTH_WINDOW_S, now=time.time() + auth.AUTH_WINDOW_S + 1) == 0
    # registro: 10 intentos fallidos (correo ya registrado) → 429
    for _ in range(auth.AUTH_MAX_FAILS):
        assert _http(app, "POST", "/api/auth/register", json=alta, headers=ip).status_code == 409
    assert _http(app, "POST", "/api/auth/register", json=alta, headers=ip).status_code == 429
    assert len(FAKE.users.docs) == 1


def test_5_ip_del_cliente_no_se_puede_falsear_con_la_cabecera():
    class R:
        def __init__(self, xff=None): self.headers = {"x-forwarded-for": xff} if xff else {}; self.client = type("C", (), {"host": "10.0.0.1"})()
    assert ratelimit.client_ip(R()) == "10.0.0.1"
    # el cliente antepone una IP inventada; cuenta la que añadió NUESTRO proxy (la última)
    assert ratelimit.client_ip(R("1.2.3.4, 203.0.113.7")) == "203.0.113.7"


# ═════════════════ 6. WHATSAPP DE VOZ SOLO AL CLIENTE · TARJETA SIN org_id ═════════════════
def _agente(org=A, tok="tok-agente-" + "b" * 30):
    FAKE.custom_agents.docs.append({"id": "ag-" + org, "org_id": org, "tools": ["enviar_whatsapp"],
                                    "tool_token": tok})
    return {"X-Agent-Token": tok}


@respx.mock
def test_6_enviar_whatsapp_solo_al_numero_del_cliente_de_la_llamada_o_pedido(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_KEY", "plat-key")
    app = _app(voz.router)
    cab = _agente(A)
    pedido(A, ref="P-1", phone="+573001112233")
    pedido(B, ref="P-9", phone="+573005550000")                    # pedido de OTRO cliente
    run(oc.set_credentials("chatea_pro", {"api_key": "wa-key-A"}, A))
    respx.get(f"{WA}/subscriber/get-info").mock(return_value=httpx.Response(200, json={"id": 7}))
    envio = respx.post(f"{WA}/subscriber/send-text").mock(return_value=httpx.Response(200, json={"id": "m1"}))
    post = lambda j, h=cab: _http(app, "POST", "/api/agent-tools/enviar_whatsapp", json=j, headers=h).json()
    # 1) número libre dictado por el modelo, sin llamada ni pedido → no se envía
    r = post({"telefono": "+573019999999", "mensaje": "hola"})
    assert r["ok"] is False and "número del cliente" in r["error"]
    # 2) pedido correcto pero el modelo pide OTRO número → no se envía
    r = post({"telefono": "+573019999999", "pedido_id": "P-1", "mensaje": "hola"})
    assert r["ok"] is False and r["error"] == voz.SOLO_AL_CLIENTE
    # 3) pedido de otro cliente → no existe para este agente
    assert post({"pedido_id": "P-9", "mensaje": "hola"})["ok"] is False
    # 4) el sobre de Retell no vale con llave de plataforma (el cuerpo no es de fiar)
    sobre = {"name": "enviar_whatsapp", "args": {"mensaje": "hola"},
             "call": {"call_id": "c-1", "to_number": "+573001112233"}}
    assert post(sobre, {"X-API-Key": "plat-key", "X-Org-Id": A})["ok"] is False
    assert not envio.called and FAKE.message_log.docs == []
    # 5) con el pedido: va al número guardado (el modelo ni siquiera lo dicta)
    r = post({"pedido_id": "P-1", "mensaje": "Te esperamos"})
    assert r["ok"] is True and FAKE.message_log.docs[-1]["phone"] == "+573001112233"
    # 6) con el sobre de Retell y token del agente: va al número de ESA llamada,
    #    aunque dentro de args el modelo ponga otro
    r = post(sobre)
    assert r["ok"] is True and FAKE.message_log.docs[-1]["phone"] == "+573001112233"
    r = post({**sobre, "args": {"mensaje": "hola", "telefono": "+573019999999"}})
    assert r["ok"] is False and r["error"] == voz.SOLO_AL_CLIENTE
    # 7) mismo número escrito sin prefijo de país → coincide
    assert post({"pedido_id": "P-1", "telefono": "3001112233", "mensaje": "ok"})["ok"] is True
    # 8) llamada ya registrada de este negocio (call_id) → su número
    FAKE.calls.docs.append({"call_id": "c-7", "org_id": A, "telefono": "+573004440000"})
    FAKE.calls.docs.append({"call_id": "c-8", "org_id": B, "telefono": "+573005550000"})
    assert post({"call_id": "c-7", "mensaje": "ok"})["ok"] is True
    assert FAKE.message_log.docs[-1]["phone"] == "+573004440000"
    assert post({"call_id": "c-8", "mensaje": "ok"})["ok"] is False                 # llamada de otro cliente
    assert len(envio.calls) == 4 and all(m["org_id"] == A for m in FAKE.message_log.docs)
    assert "telefono" not in retell_required()


def retell_required():
    import retell_service
    return retell_service.CALL_TOOL_SPECS["enviar_whatsapp"]["parameters"].get("required", [])


def test_6_la_accion_pendiente_no_guarda_ni_muestra_org_id():
    ctx = {"org_id": A, "user_id": "u1"}
    llamada = {"name": "send_whatsapp", "args": {"phone": "+573001112233", "text": "hola",
                                                 "org_id": B, "ctx": {"org_id": B}, "user_id": "x"}}
    doc = run(agent_loop._create_pending(ctx, "hilo-1", llamada, {}))
    guardado = FAKE.pending_actions.docs[0]
    assert guardado["org_id"] == A                                  # el dueño sale de la sesión
    assert guardado["args"] == {"phone": "+573001112233", "text": "hola"}
    publica = agent_loop._public_action(doc)
    assert set(publica) == {"id", "tool", "resumen", "args"} and "org_id" not in publica["args"]
    # una acción antigua guardada con org_id tampoco lo enseña
    assert "org_id" not in agent_loop._public_action({"id": "x", "tool": "t", "resumen": "r",
                                                      "args": {"org_id": A, "a": 1}})["args"]


# ═════════════════ 7. WEBHOOKS, REPORTE POR ZONA Y NOMBRES ANTIGUOS ═════════════════
def test_7_rotar_direcciones_invalida_las_anteriores_y_trae_notas(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://api.ejemplo.com")
    antes = run(org_profile.webhook_urls(Req(A), A))
    assert set(antes["urls"]) == {"chatea", "twilio", "elevenlabs", "retell"}
    assert set(antes["notas"]) == set(antes["urls"])                # una nota por dirección
    viejo = antes["token"]
    otro = run(org_profile.webhook_urls(Req(B), B))["token"]
    despues = run(org_profile.rotate_webhook_urls(Req(A), A))
    assert despues["token"] != viejo and despues["rotated"] is True and despues["notas"] == antes["notas"]
    assert despues["urls"]["chatea"] == f"https://api.ejemplo.com/api/webhooks/chatea/{despues['token']}"
    assert run(webhook_tokens.org_for_token(viejo)) is None        # la dirección vieja ya no sirve
    assert run(webhook_tokens.org_for_token(despues["token"])) == A
    assert run(webhook_tokens.org_for_token(otro)) == B            # la de otro cliente no cambia


def test_7_reporte_diario_a_la_hora_local_de_cada_perfil():
    run(org_profile.save_profile(A, org_profile.OrgProfileIn(zona_horaria="America/Bogota")))
    run(org_profile.save_profile(B, org_profile.OrgProfileIn(zona_horaria="Europe/Madrid")))
    FAKE.orgs.docs += [{"id": A}, {"id": B}]
    a_las = lambda h: datetime(2026, 1, 15, h, 5, tzinfo=timezone.utc)
    toca = lambda h: {o: dia for o, dia in run(scheduler._orgs_due(a_las(h))) if o in (A, B)}
    assert toca(13) == {A: "2026-01-15"}                            # 08:05 en Bogotá
    assert toca(7) == {B: "2026-01-15"}                             # 08:05 en Madrid
    assert toca(20) == {}
    assert "Bogot" not in (scheduler.__doc__ or "")


def test_7_sin_restos_de_nombres_antiguos():
    assert "emergent" not in translation.LLMProvider.name.lower()
    for f in ("models.py", "translation.py"):
        txt = open(os.path.join(BACKEND, f), encoding="utf-8").read().lower()
        assert "antifluido" not in txt and "emergent" not in txt
