"""Aislamiento entre clientes (org) + generalidad + seguridad de arranque.

Unitarias: sin servidor vivo ni Mongo real. Reutiliza el banco de
test_byok_openrouter.py (misma FAKE, así ambos archivos conviven en una sola
sesión de pytest) ampliado con tests/fake_mongo.py.
Cliente A = "org-a", cliente B = "org-b".
"""
import os, sys, json, asyncio, subprocess, types
from datetime import date, datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, BACKEND)

import pytest
import test_byok_openrouter as banco          # fija db.get_db -> FAKE antes de importar rutas
from fake_mongo import DB as RichDB

banco.FAKE.__class__ = RichDB                 # mismo objeto, con operadores completos
FAKE = banco.FAKE

import jwt
from fastapi import FastAPI, HTTPException
import httpx

import deps, packs, cadence, scheduler
from agent import tools as agent_tools, loop as agent_loop
from models import (OrderIn, TaskIn, TaskUpdate, ProductIn, PromptIn, PromptResolveIn,
                    NumberImport, SendMessageIn, WhatsappRuleIn, SkillIn, VipLeadIn)
from routes import (orders, queue, tasks, products, copilot, prompts, numbers, metrics,
                    whatsapp, skills, vip, connectors, agents, carriers, novedades,
                    calls, webhooks, agent_tools as agent_tools_routes, custom_agents,
                    org_profile, cadence as cadence_routes)
from routes.auth import COOKIE_NAME, JWT_SECRET, JWT_ALG

A, B = "org-a", "org-b"


def run(c): return asyncio.run(c)


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    FAKE.c.clear()
    for k in ("ENV", "ENVIRONMENT", "RENDER", "RETELL_WEBHOOK_SECRET", "CHATEA_PRO_API_KEY"):
        monkeypatch.delenv(k, raising=False)


class Req:
    """Petición mínima: cookie JWT del org + cabeceras + cuerpo JSON."""
    def __init__(self, org=None, headers=None, body=None, user="u1"):
        self.cookies = {COOKIE_NAME: jwt.encode({"sub": user, "org": org}, JWT_SECRET,
                                                algorithm=JWT_ALG)} if org else {}
        self.headers = headers or {}
        self._body = body or {}
    async def json(self): return self._body


def pedido(org, phone="+573001112233", ref="P-1", **kw):
    """Instala el paquete COD en `org` (transportadoras) y crea un pedido."""
    if not FAKE.carriers._find({"org_id": org}):
        run(packs.install_pack(org, "cod_colombia"))
    return run(orders.create_order(OrderIn(
        customer_name="Ana", customer_phone=phone, carrier_slug="servientrega",
        external_ref=ref, total_amount=100000, **kw), org))


def no_encontrado(coro):
    with pytest.raises(HTTPException) as e:
        run(coro)
    assert e.value.status_code == 404


# ───────────────────────── 1. AISLAMIENTO EN RUTAS ─────────────────────────
def test_pedidos_b_no_ve_los_de_a():
    o = pedido(A)
    assert [x["id"] for x in run(orders.list_orders(0, 50, None, None, A))] == [o.id]
    assert run(orders.list_orders(0, 50, None, None, B)) == []
    no_encontrado(orders.get_order(o.id, B))
    no_encontrado(orders.order_prompt_vars(o.id, B))
    assert FAKE.orders.docs[0]["org_id"] == A and FAKE.call_queue.docs[0]["org_id"] == A


def test_cola_b_no_ve_la_de_a():
    pedido(A)
    cola_a = run(queue.list_queue(None, None, None, 200, A))
    assert len(cola_a) == 1 and cola_a[0]["customer_name"] == "Ana"
    assert run(queue.list_queue(None, None, None, 200, B)) == []
    no_encontrado(queue.get_queue_item(cola_a[0]["id"], B))


def test_tareas_b_no_ve_ni_modifica_las_de_a():
    t = run(tasks.create_task(TaskIn(description="llamar a Ana"), A))
    assert run(tasks.list_tasks(None, None, 100, B)) == []
    no_encontrado(tasks.get_task(t.id, B))
    no_encontrado(tasks.update_task(t.id, TaskUpdate(status="closed"), B))
    no_encontrado(tasks.delete_task(t.id, B))
    assert run(tasks.get_task(t.id, A))["status"] == "open"


def test_productos_b_no_ve_ni_usa_las_promos_de_a():
    p = run(products.create_product(ProductIn(nombre="Kit A", promotions=[
        {"sku_pattern": "KIT-A", "nombre_comercial": "Kit A Promo", "precio_promo": 99}]), A))
    assert run(products.list_products(B)) == []
    no_encontrado(products.get_product(p.id, B))
    no_encontrado(products.delete_product(p.id, B))
    assert run(products.match_promotion(products.MatchIn(sku="KIT-A"), A))["matched"] is True
    assert run(products.match_promotion(products.MatchIn(sku="KIT-A"), B))["matched"] is False


def test_hilos_listar_renombrar_borrar_y_leer_solo_los_del_org():
    t = run(copilot.create_thread(None, A))
    FAKE.chat_messages.docs.append({"id": "m1", "thread_id": t.id, "org_id": A, "role": "user",
                                    "content": "secreto de A", "created_at": "2026-01-01"})
    assert run(copilot.list_threads(100, B)) == []
    no_encontrado(copilot.rename_thread(t.id, copilot.ThreadRename(title="hack"), B))
    no_encontrado(copilot.delete_thread(t.id, B))
    assert run(copilot.list_messages(t.id, B)) == []
    assert len(FAKE.chat_messages.docs) == 1, "B no pudo borrar los mensajes de A"
    assert [m["content"] for m in run(copilot.list_messages(t.id, A))] == ["secreto de A"]


def test_agent_run_no_escribe_en_el_hilo_de_otro_cliente(monkeypatch):
    # Ronda 2: un hilo ajeno se trata IGUAL que uno inexistente (no se revela
    # que existe): se abre un hilo nuevo de B y el de A queda intacto.
    async def falso_run_agent(**kw):
        return {"final_text": "ok", "steps": [], "provider": "x"}
    monkeypatch.setattr(copilot, "run_agent", falso_run_agent)
    t = run(copilot.create_thread(None, A))
    r = run(copilot.run(SendMessageIn(thread_id=t.id, text="hola"), Req(B)))
    assert r["thread_id"] != t.id
    assert {d["org_id"] for d in FAKE.chat_messages.docs} == {B}
    assert all(d["thread_id"] != t.id for d in FAKE.chat_messages.docs)
    assert [d["org_id"] for d in FAKE.chat_threads.docs if d["id"] == t.id] == [A]


def test_agent_run_pasa_el_org_de_la_sesion_al_agente(monkeypatch):
    visto = {}
    async def falso_run_agent(**kw):
        visto.update(kw); return {"final_text": "ok", "steps": [], "provider": "x"}
    monkeypatch.setattr(copilot, "run_agent", falso_run_agent)
    r = run(copilot.run(SendMessageIn(text="hola"), Req(B, headers={"X-Org-Id": A}, user="u-b")))
    assert visto["org_id"] == B and visto["user_id"] == "u-b"
    assert {d["org_id"] for d in FAKE.chat_messages.docs} == {B}
    assert FAKE.chat_threads.docs[0]["org_id"] == B and r["final_text"] == "ok"


def test_prompts_b_no_ve_ni_resuelve_los_de_a():
    p = run(prompts.create_prompt(PromptIn(name="Guion A", system_prompt="soy de A"), A))
    assert run(prompts.list_prompts(None, None, B)) == []
    no_encontrado(prompts.get_prompt(p.id, B))
    no_encontrado(prompts.delete_prompt(p.id, B))
    no_encontrado(prompts.resolve_prompt(PromptResolveIn(), B))
    assert run(prompts.resolve_prompt(PromptResolveIn(), A))["prompt"]["id"] == p.id


def test_numeros_aislados_y_mismo_telefono_en_dos_clientes():
    n = run(numbers.import_number(NumberImport(phone_number="+573009998877"), A))
    assert run(numbers.list_numbers(B)) == []
    no_encontrado(numbers.delete_number(n.id, B))
    run(numbers.import_number(NumberImport(phone_number="+573009998877"), B))  # no pisa el de A
    assert len(FAKE.connected_numbers.docs) == 2
    assert [x["id"] for x in run(numbers.list_numbers(A))] == [n.id]


def test_metricas_de_b_no_cuentan_datos_de_a():
    pedido(A)
    run(tasks.create_task(TaskIn(description="x"), A))
    FAKE.message_log.docs.append({"org_id": A, "channel": "whatsapp", "direction": "outbound",
                                  "phone": "+57", "body": "hola",
                                  "created_at": datetime.now(timezone.utc).isoformat()})
    ma, mb = run(metrics.compute_metrics(A)), run(metrics.compute_metrics(B))
    assert (ma["queue_total"], ma["orders_total"], ma["tasks_open"], ma["messages_24h"]) == (1, 1, 1, 1)
    assert (mb["queue_total"], mb["orders_total"], mb["tasks_open"], mb["messages_24h"]) == (0, 0, 0, 0)
    assert mb["whatsapp"]["sent"] == 0 and ma["whatsapp"]["sent"] == 1


def test_whatsapp_reglas_contactos_y_bitacora_por_org():
    r = run(whatsapp.create_wa_rule(WhatsappRuleIn(template_name="tpl_a", days_min=0, days_max=3), A))
    run(whatsapp.mark_inbound("+573001", "hola", A))
    FAKE.message_log.docs.append({"org_id": A, "phone": "+573001", "created_at": "2026-01-01"})
    assert run(whatsapp.list_wa_rules(B)) == [] and run(whatsapp.list_contacts(200, B)) == []
    assert run(whatsapp.list_messages(100, None, B)) == []
    assert run(whatsapp.resolve_rule_for_days_left(1, B)) is None
    assert run(whatsapp.resolve_rule_for_days_left(1, A))["id"] == r.id
    assert run(whatsapp.window_open("+573001", A))[0] is True
    assert run(whatsapp.window_open("+573001", B))[0] is False     # misma persona, otra empresa
    no_encontrado(whatsapp.delete_wa_rule(r.id, B))


def test_skills_leads_conectores_lista_negra_y_transportadoras_por_org():
    s = run(skills.create_skill(SkillIn(name="S", trigger="s", instructions="i"), A))
    assert run(skills.list_skills(B)) == []
    no_encontrado(skills.delete_skill(s.id, B))
    FAKE.vip_leads.docs.append({"id": "l1", "org_id": A, "nombre": "Lead A", "whatsapp": "+57",
                                "created_at": "2026-01-01"})
    assert run(vip.list_leads(500, B)) == []
    no_encontrado(vip.delete_lead("l1", B))
    FAKE.integration_connectors.docs.append({"org_id": A, "key": "twilio", "name": "Twilio",
                                             "status": "connected", "metadata": {"verified_count": 3}})
    assert {c["key"]: c["status"] for c in run(connectors.list_connectors(A))}["twilio"] == "connected"
    assert {c["status"] for c in run(connectors.list_connectors(B))} == {"unconfigured"}
    run(agents.blacklist_add(agents.BlacklistIn(phone="+57300", reason="rto"), A))
    assert run(agents.blacklist_list(B)) == []
    assert run(agents._run_riesgo(FAKE, B, "+57300", "", ""))["score"] == 0
    assert run(agents._run_riesgo(FAKE, A, "+57300", "", ""))["score"] >= 60
    run(packs.install_pack(A, "cod_colombia"))
    assert run(carriers.list_carriers(B)) == [] and run(novedades.list_novedades(None, None, 500, B)) == []
    assert len(run(carriers.list_carriers(A))) > 5


def test_cadencia_b_no_puede_programar_ni_cerrar_la_de_a():
    pedido(A)
    qid = FAKE.call_queue.docs[0]["id"]
    from models import ScheduleRequest, AttemptResult
    no_encontrado(cadence_routes.schedule(ScheduleRequest(queue_id=qid), B))
    run(cadence_routes.schedule(ScheduleRequest(queue_id=qid), A))
    assert FAKE.call_schedules.docs[0]["org_id"] == A
    no_encontrado(cadence_routes.get_schedule(qid, B))
    no_encontrado(cadence_routes.attempt_result(
        AttemptResult(queue_id=qid, attempt_number=1, result="rechaza"), B))
    assert FAKE.call_queue.docs[0]["status"] == "pending" and FAKE.customer_tasks.docs == []


def test_el_org_sale_del_jwt_y_no_de_la_cabecera():
    assert deps.get_org(Req(B, headers={"X-Org-Id": A})) == B
    assert deps.get_ctx(Req(B, user="u9")) == {"org_id": B, "user_id": "u9"}
    assert deps.get_org(Req()) == "default"


# ───────────────────────── 2. HERRAMIENTAS DEL AGENTE ─────────────────────────
def test_herramientas_con_ctx_de_b_no_devuelven_datos_de_a():
    pedido(A)
    run(tasks.create_task(TaskIn(description="de A"), A))
    run(numbers.import_number(NumberImport(phone_number="+573009998877"), A))
    ctx_b, ctx_a = {"org_id": B, "user_id": "u"}, {"org_id": A, "user_id": "u"}
    for tool in ("get_orders", "get_queue", "list_tasks", "list_numbers", "list_voices",
                 "get_carriers", "get_carrier_novedades"):
        rb = run(agent_tools.execute(tool, {}, ctx_b))
        assert rb["ok"] and rb["result"]["count"] == 0, tool
        assert run(agent_tools.execute(tool, {}, ctx_a))["result"]["count"] >= 1, tool
    mb = run(agent_tools.execute("get_metrics", {}, ctx_b))["result"]
    assert mb["orders_total"] == 0 and mb["queue_total"] == 0


def test_el_modelo_no_puede_elegir_otro_cliente_en_los_args():
    pedido(A)
    r = run(agent_tools.execute("get_orders", {"org_id": A, "ctx": {"org_id": A}}, {"org_id": B}))
    assert r["ok"] and r["result"]["count"] == 0


def test_herramientas_escriben_con_el_org_del_ctx_y_no_tocan_lo_ajeno():
    pedido(A)
    qid = FAKE.call_queue.docs[0]["id"]
    r = run(agent_tools.execute("schedule_cadence", {"queue_id": qid}, {"org_id": B}))
    assert "not found" in r["result"]["error"] and FAKE.call_schedules.docs == []
    run(agent_tools.execute("create_task", {"description": "de B"}, {"org_id": B}))
    assert [d["org_id"] for d in FAKE.customer_tasks.docs] == [B]
    assert run(agent_tools.execute("list_tasks", {}, {"org_id": A}))["result"]["count"] == 0
    FAKE.uploaded_files.docs.append({"id": "f1", "org_id": A, "filename": "a.csv",
                                     "rows_preview": [{"cliente": "X", "telefono": "1"}]})
    r = run(agent_tools.execute("import_orders_from_file", {"file_id": "f1"}, {"org_id": B}))
    assert "not found" in r["result"]["error"] and len(FAKE.orders.docs) == 1


def test_run_agent_ejecuta_herramientas_con_el_org_recibido(monkeypatch):
    pedido(A)
    respuestas = iter(['```tool\n{"name": "get_orders", "args": {}}\n```', "listo"])
    async def falso_llm(system, conv, **kw):
        assert kw["org_id"] == B
        return next(respuestas), "fake"
    monkeypatch.setattr(agent_loop, "llm_call", falso_llm)
    r = run(agent_loop.run_agent("s1", [], "¿qué pedidos hay?", org_id=B))
    assert r["steps"][0]["tool_calls"][0]["result"]["result"]["count"] == 0
    assert r["final_text"] == "listo"


# ───────────────────────── 3. PAQUETE COD + ARRANQUE ─────────────────────────
def test_paquete_cod_se_instala_solo_en_el_org_pedido_y_es_idempotente():
    r = run(packs.install_pack(A, "cod_colombia"))
    assert r["ok"] and r["org_id"] == A
    sembradas = ("carriers", "carrier_novedades", "copilot_skills", "voice_profiles",
                 "prompts", "whatsapp_rules", "org_packs")
    antes = {c: len(getattr(FAKE, c).docs) for c in sembradas}
    assert all(antes.values())
    for c in sembradas:
        assert {d["org_id"] for d in getattr(FAKE, c).docs} == {A}, c
    assert run(prompts.list_prompts(None, None, B)) == [] and run(packs.installed_packs(B)) == []
    run(packs.install_pack(A, "cod_colombia"))
    assert antes == {c: len(getattr(FAKE, c).docs) for c in sembradas}
    run(packs.install_pack(B, "cod_colombia"))                      # cada cliente, sus propios ids
    ids = [d["id"] for d in FAKE.prompts.docs + FAKE.copilot_skills.docs + FAKE.voice_profiles.docs]
    assert len(ids) == len(set(ids))
    with pytest.raises(ValueError):
        run(packs.install_pack(A, "no_existe"))


def test_el_arranque_no_siembra_datos_de_negocio():
    os.environ.setdefault("MONGO_URL", "mongodb://localhost:1"); os.environ.setdefault("DB_NAME", "x")
    import server
    run(server._ensure_indexes())
    assert not any(c.docs for c in FAKE.c.values()), "el arranque solo crea índices"
    assert not hasattr(server, "_ensure_seed") and server.app.title == "Zynex OS API"
    rutas = {r.path for r in server.app.routes}
    assert {"/api/packs", "/api/packs/{pack}/install", "/api/org/profile"} <= rutas


def test_migracion_pone_org_default_solo_donde_falta_y_es_idempotente():
    sys.path.insert(0, os.path.join(BACKEND, "scripts"))
    import migrar_org_id
    FAKE.orders.docs += [{"id": "viejo"}, {"id": "nulo", "org_id": None}, {"id": "deA", "org_id": A}]
    FAKE.chat_threads.docs.append({"id": "t-viejo"})
    assert run(migrar_org_id.migrate(FAKE, apply=False))["orders"] == 2
    assert "org_id" not in FAKE.orders.docs[0], "la simulación no escribe"
    run(migrar_org_id.migrate(FAKE, apply=True))
    assert [d["org_id"] for d in FAKE.orders.docs] == ["default", "default", A]
    assert FAKE.chat_threads.docs[0]["org_id"] == "default"
    assert sum(run(migrar_org_id.migrate(FAKE, apply=True)).values()) == 0


# ───────────────────────── 4. PERFIL Y GENERALIDAD ─────────────────────────
def test_perfil_se_guarda_por_org_con_defaults_neutros():
    p = run(org_profile.write_profile(org_profile.OrgProfileIn(
        empresa="Clínica Sonrisa", sector="odontología", pais="mx", moneda="mxn",
        zona_horaria="America/Mexico_City", nombre_asistente="Dra. Bot"), A))
    assert (p["empresa"], p["pais"], p["moneda"]) == ("Clínica Sonrisa", "MX", "MXN")
    b = run(org_profile.read_profile(B))
    assert (b["nombre_asistente"], b["zona_horaria"], b["moneda"], b["empresa"]) == \
           ("Lyan", "America/Bogota", "USD", "")
    assert run(org_profile.read_profile(A))["nombre_asistente"] == "Dra. Bot"
    assert len(FAKE.org_profiles.docs) == 1 and FAKE.org_profiles.docs[0]["org_id"] == A
    with pytest.raises(HTTPException):
        run(org_profile.write_profile(org_profile.OrgProfileIn(zona_horaria="Marte/Olympus"), A))


def test_prompt_del_agente_sale_del_perfil_y_sirve_para_cualquier_negocio():
    generico = agent_loop.build_system_prompt(None)
    for palabra in ("Marcus", "Litper", "COD", "Colombia", "semáforo"):
        assert palabra not in generico, palabra
    assert "Eres Lyan" in generico and "get_orders" in generico
    p = agent_loop.build_system_prompt({"empresa": "Clínica Sonrisa", "sector": "odontología",
                                        "pais": "MX", "nombre_asistente": "Dra. Bot", "idioma": "es"})
    assert "Eres Dra. Bot, el asistente operativo de Clínica Sonrisa" in p and "odontología" in p
    run(packs.install_pack(A, "cod_colombia"))                      # lo COD solo con el paquete
    assert "semáforos" in run(packs.agent_prompt_addendum(A))
    assert run(packs.agent_prompt_addendum(B)) == ""


def test_run_agent_usa_el_perfil_del_org(monkeypatch):
    run(org_profile.write_profile(org_profile.OrgProfileIn(empresa="Taller Rayo",
                                                           nombre_asistente="Max"), B))
    visto = {}
    async def falso_llm(system, conv, **kw):
        visto["system"] = system; return "hola", "fake"
    monkeypatch.setattr(agent_loop, "llm_call", falso_llm)
    run(agent_loop.run_agent("s", [], "hola", org_id=B))
    assert "Eres Max, el asistente operativo de Taller Rayo" in visto["system"]


def test_pais_y_moneda_abiertos_y_pedido_toma_los_del_perfil():
    assert OrderIn(customer_name="x", customer_phone="1", carrier_slug="c",
                   country="MX", currency="MXN").country == "MX"
    assert PromptIn(name="n", system_prompt="s", country="ES").country == "ES"
    assert VipLeadIn(nombre="n", whatsapp="+34", pais="ES").pais == "ES"
    run(org_profile.write_profile(org_profile.OrgProfileIn(pais="PE", moneda="PEN"), A))
    o = pedido(A)
    assert (o.country, o.currency) == ("PE", "PEN")
    assert pedido(A, ref="P-2", country="CL", currency="CLP").currency == "CLP"


def test_plantillas_genericas_sin_marca_y_las_cod_solo_con_el_paquete():
    texto = json.dumps(custom_agents.TEMPLATES, ensure_ascii=False).lower()
    assert "antifluido" not in texto and "litper" not in texto
    assert "rescate_oficina" not in run(custom_agents.templates_for(B))
    run(packs.install_pack(A, "cod_colombia"))
    assert {"rescate_oficina", "confirmacion_cod", "citas"} <= set(run(custom_agents.templates_for(A)))


def test_zona_horaria_del_perfil_y_festivos_solo_colombia():
    festivo = date(2026, 12, 25)
    co = cadence.build_plan(country="CO", start_date=festivo, office_claim_max_days=None)
    mx = cadence.build_plan(country="MX", start_date=festivo, office_claim_max_days=None,
                            tz_name="America/Mexico_City")
    assert co[0]["scheduled_at"].startswith("2026-12-26T14:00")     # salta el festivo · 9am Bogotá
    assert mx[0]["scheduled_at"].startswith("2026-12-25T15:00")     # no lo salta · 9am CDMX
    sin_perfil = cadence.build_plan(country="", start_date=date(2026, 3, 3), office_claim_max_days=None)
    assert sin_perfil[0]["scheduled_at"].startswith("2026-03-03T14:00")   # no rompe: Bogotá


# ───────────────────────── 5. SEGURIDAD ─────────────────────────
def test_arranque_falla_sin_jwt_secret_en_produccion(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        deps.check_jwt_secret()
    monkeypatch.setenv("JWT_SECRET", deps.DEFAULT_JWT_SECRET)       # el valor por defecto tampoco
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        deps.check_jwt_secret()
    monkeypatch.delenv("ENV"); monkeypatch.setenv("RENDER", "true")
    with pytest.raises(RuntimeError):
        deps.check_jwt_secret()
    monkeypatch.setenv("JWT_SECRET", "un-secreto-largo-y-real")
    assert deps.check_jwt_secret() == "un-secreto-largo-y-real"
    monkeypatch.delenv("RENDER"); monkeypatch.delenv("JWT_SECRET")
    assert deps.check_jwt_secret() == deps.DEFAULT_JWT_SECRET       # solo porque corre bajo pytest (ver test_ronda2)


@pytest.mark.parametrize("modulo", ["deps", "routes.auth"])
def test_importar_en_produccion_sin_secreto_aborta_el_proceso(modulo):
    env = {k: v for k, v in os.environ.items() if k not in ("JWT_SECRET", "RENDER")}
    env.update(ENVIRONMENT="production", MONGO_URL="mongodb://localhost:1", DB_NAME="x")
    r = subprocess.run([sys.executable, "-c", f"import {modulo}"], cwd=BACKEND, env=env,
                       capture_output=True, text=True)
    assert r.returncode != 0 and "JWT_SECRET" in r.stderr


def _app(*routers):
    app = FastAPI()
    for r in routers:
        app.include_router(r, prefix="/api")
    return app


def _http(app, metodo, url, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://t") as c:
            return await c.request(metodo, url, **kw)
    return run(go())


def test_webhook_events_y_agent_tools_exigen_autenticacion(monkeypatch):
    monkeypatch.setenv("PUBLIC_API_KEY", "plat-key")
    app = _app(webhooks.router, agent_tools_routes.router)
    FAKE.webhook_events.docs += [{"id": "e1", "org_id": A, "provider": "twilio", "created_at": "1"},
                                 {"id": "e2", "org_id": B, "provider": "twilio", "created_at": "2"}]
    assert _http(app, "GET", "/api/webhooks/events").status_code == 401
    assert _http(app, "POST", "/api/agent-tools/proximo_horario_disponible").status_code == 401
    assert _http(app, "POST", "/api/agent-tools/confirmar_pedido",
                 json={"pedido_id": "1"}, headers={"X-API-Key": "mala"}).status_code == 401
    tok = jwt.encode({"sub": "u", "org": B}, JWT_SECRET, algorithm=JWT_ALG)
    r = _http(app, "GET", "/api/webhooks/events", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and [e["id"] for e in r.json()] == ["e2"]
    r = _http(app, "POST", "/api/agent-tools/confirmar_pedido", json={"pedido_id": "1"},
              headers={"X-API-Key": "plat-key", "X-Org-Id": A})
    assert r.status_code == 200 and FAKE.agent_tool_calls.docs[-1]["org_id"] == A


def test_webhook_de_llamadas_no_toma_la_org_del_cuerpo(monkeypatch):
    # Ronda 2: la ruta sin token falla cerrado; con el secreto verificado el
    # dueño sale de lo guardado, nunca de `zynex_org_id` del cuerpo.
    monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "s3creto")
    ok = {calls.WEBHOOK_SECRET_HEADER: "s3creto"}
    FAKE.custom_agents.docs.append({"id": "ag-b", "org_id": B, "retell_agent_id": "ret-b"})
    falsa = {"call_id": "c1", "metadata": {"zynex_org_id": A, "zynex_agent_id": "no-existe"},
             "transcript": "inyectada"}
    r = run(calls.calls_webhook(Req(body=falsa, headers=ok)))
    assert r["org_resolved"] is False and FAKE.calls.docs[0]["org_id"] is None
    assert run(calls.list_calls(Req(A)))["calls"] == []            # A no recibe la llamada falsa
    real = {"call_id": "c2", "agent_id": "ret-b", "metadata": {"zynex_org_id": A}}
    run(calls.calls_webhook(Req(body=real, headers=ok)))
    assert [c["call_id"] for c in run(calls.list_calls(Req(B)))["calls"]] == ["c2"]
    assert run(calls.calls_count(Req(A)))["total"] == 0


def test_webhook_de_llamadas_exige_el_secreto_cuando_esta_definido(monkeypatch):
    monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "s3creto")
    cuerpo = {"call_id": "c1", "agent_id": "x"}
    for headers in ({}, {calls.WEBHOOK_SECRET_HEADER: "otro"}):
        with pytest.raises(HTTPException) as e:
            run(calls.calls_webhook(Req(body=cuerpo, headers=headers)))
        assert e.value.status_code == 401
    assert FAKE.calls.docs == []
    assert run(calls.calls_webhook(Req(body=cuerpo, headers={calls.WEBHOOK_SECRET_HEADER: "s3creto"})))["ok"]


def test_cors_por_defecto_solo_localhost():
    import re, server
    cors = next(m for m in server.app.user_middleware if "CORS" in m.cls.__name__)
    patron = cors.kwargs["allow_origin_regex"] if hasattr(cors, "kwargs") else cors.options["allow_origin_regex"]
    assert re.fullmatch(patron, "http://localhost:3000")
    assert not re.fullmatch(patron, "https://x.preview.emergentagent.com")


# ───────────────────────── 6. SCHEDULER Y WEBHOOKS POR ORG ─────────────────────────
def test_barrido_de_novedades_cuenta_por_cliente():
    pedido(A); pedido(B, phone="+573005550000")
    run(scheduler.novedades_sweep())
    ticks = {t["org_id"]: t["total"] for t in FAKE.novedades_ticks.docs}
    assert ticks == {A: 1, B: 1}
    assert len(run(agents.novedades_ticks(20, A))) == 1


def test_despacho_de_cadencia_no_mezcla_clientes():
    pedido(A, phone="+57AAA"); pedido(B, phone="+57BBB")
    assert run(scheduler._phone_for_queue(FAKE.call_queue.docs[0]["id"], A)) == "+57AAA"
    assert run(scheduler._phone_for_queue(FAKE.call_queue.docs[0]["id"], B)) is None
    for q in list(FAKE.call_queue.docs):
        FAKE.call_schedules.docs.append({
            "id": "s-" + q["org_id"], "org_id": q["org_id"], "queue_id": q["id"],
            "attempts": [{"attempt_number": 1, "channel": "whatsapp", "status": "pending",
                          "scheduled_at": "2000-01-01T00:00:00+00:00"}]})
    run(scheduler.dispatch_due_attempts())
    assert {q["org_id"]: q["status"] for q in FAKE.call_queue.docs} == {A: "in_progress", B: "in_progress"}
    assert all(s["attempts"][0]["status"] == "dispatched" for s in FAKE.call_schedules.docs)


def test_reporte_ceo_por_cliente():
    pedido(A)
    FAKE.orgs.docs += [{"id": A}, {"id": B}]
    # 13:00 UTC = 08:00 en America/Bogota (zona del perfil que deja el paquete COD)
    run(scheduler.daily_ceo_report(datetime(2026, 1, 5, 13, 0, tzinfo=timezone.utc)))
    assert [r["org_id"] for r in FAKE.ceo_reports.docs] == [A]      # B no tiene datos: sin reporte
    assert run(agents.ceo_report(None, B))["available"] is False
    assert run(agents.ceo_report(None, A))["report"]["orders_total"] == 1
    run(agents.ceo_target_set(agents.CeoTargetIn(target="+57111"), A))
    assert run(agents.ceo_target_get(B))["target"] == ""


def test_respuesta_de_whatsapp_se_asigna_al_cliente_que_escribio():
    pedido(A, phone="+573001112233"); pedido(B, phone="+573001112233")   # mismo comprador
    FAKE.message_log.docs.append({"org_id": B, "phone": "+573001112233", "direction": "outbound",
                                  "provider_message_id": "pm1", "created_at": "2026-01-01"})
    for q in FAKE.call_queue.docs:
        FAKE.call_schedules.docs.append({"id": "s-" + q["org_id"], "org_id": q["org_id"],
                                         "queue_id": q["id"],
                                         "attempts": [{"attempt_number": 1, "status": "pending"}]})
    app = _app(webhooks.router)
    # Ronda 2: el cliente sale del TOKEN de la URL (no del "último saliente").
    import webhook_tokens
    url_b = "/api/webhooks/chatea/" + run(webhook_tokens.token_for(B))
    r = _http(app, "POST", url_b,
              json={"event": "message", "phone": "+573001112233", "text": "stop"})
    assert r.status_code == 200 and "opt_out_applied" in r.json()["processed"]
    assert {o["org_id"]: o.get("opt_out", False) for o in FAKE.orders.docs} == {A: False, B: True}
    assert {q["org_id"]: q["status"] for q in FAKE.call_queue.docs} == {A: "pending", B: "detenido"}
    assert {s["org_id"]: s["attempts"][0]["status"] for s in FAKE.call_schedules.docs} == \
           {A: "pending", B: "skipped"}
    # sin token y sin secreto configurado: rechazado (falla cerrado)
    r = _http(app, "POST", "/api/webhooks/chatea",
              json={"event": "message", "phone": "+573001112233", "text": "stop"})
    assert r.status_code == 503
    assert {o["org_id"]: o.get("opt_out", False) for o in FAKE.orders.docs} == {A: False, B: True}
