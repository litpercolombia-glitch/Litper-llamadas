"""Banco de pruebas del parche OpenRouter + BYOK (objetivo #40).
DB en memoria; HTTP simulado con respx. No toca nada real."""
import os, sys, json, asyncio, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["ENCRYPTION_KEY"] = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode()
for k in ["OPENROUTER_API_KEY","GROQ_API_KEY","GEMINI_API_KEY","MISTRAL_API_KEY","CEREBRAS_API_KEY","ANTHROPIC_API_KEY","EMERGENT_LLM_KEY"]:
    os.environ.pop(k, None)

import pytest, respx, httpx

# ---------- DB falsa (subconjunto motor) ----------
class Cur:
    def __init__(s, docs): s.docs = docs
    def __aiter__(s):
        s._i = iter(s.docs); return s
    async def __anext__(s):
        try: return next(s._i)
        except StopIteration: raise StopAsyncIteration
class Coll:
    def __init__(s): s.docs = []
    def _m(s, d, q): return all(d.get(k) == v for k, v in q.items())
    async def find_one(s, q, proj=None):
        for d in s.docs:
            if s._m(d, q): return dict(d)
    def find(s, q, proj=None): return Cur([dict(d) for d in s.docs if s._m(d, q)])
    async def update_one(s, q, upd, upsert=False):
        for d in s.docs:
            if s._m(d, q): d.update(upd["$set"]); return
        if upsert: s.docs.append({**q, **upd["$set"]})
    async def insert_one(s, d): s.docs.append(dict(d))
    async def delete_one(s, q): s.docs = [d for d in s.docs if not s._m(d, q)]
class DB:
    def __init__(s): s.c = {}
    def __getattr__(s, n):
        if n == "c": raise AttributeError
        return s.c.setdefault(n, Coll())
FAKE = DB()
import db as dbmod
dbmod.get_db = lambda: FAKE

import org_credentials as oc
oc.get_db = lambda: FAKE
from agent import router

OR_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
def ok(text, model="x/y"): return httpx.Response(200, json={"model": model, "choices":[{"message":{"content":text}}], "usage":{"total_tokens":7}})

@pytest.fixture(autouse=True)
def reset(monkeypatch):
    FAKE.c.clear()
    monkeypatch.setenv("PLATFORM_KEYS_ORGS", "*")
    for k in ["OPENROUTER_API_KEY","GROQ_API_KEY"]: monkeypatch.delenv(k, raising=False)

def run(c): return asyncio.get_event_loop().run_until_complete(c) if False else asyncio.run(c)

# 1. La llave BYOK guardada del cliente se usa en OpenRouter, con fallback de modelos y headers.
@respx.mock
def test_byok_openrouter_usa_llave_del_cliente():
    run(oc.set_credentials("openrouter", {"api_key": "sk-or-CLIENTE-A"}, "org-a"))
    route = respx.post(OR_URL).mock(return_value=ok("hola desde OR", "google/gemini-2.5-flash"))
    text, prov = run(router.call("sys", [{"role":"user","content":"hola"}], org_id="org-a"))
    assert (text, prov) == ("hola desde OR", "openrouter")
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer sk-or-CLIENTE-A"
    body = json.loads(req.content)
    assert "route" not in body and len(body["models"]) >= 2 and body["messages"][0]["role"] == "system"
    assert req.headers["x-title"] == "Zynex OS"
    assert FAKE.llm_calls.docs[-1]["ok"] is True and FAKE.llm_calls.docs[-1]["org_id"] == "org-a"

# 2. Aislamiento: el cliente B NO usa la llave del cliente A.
@respx.mock
def test_aislamiento_entre_clientes():
    run(oc.set_credentials("openrouter", {"api_key": "sk-or-CLIENTE-A"}, "org-a"))
    with pytest.raises(RuntimeError, match="No hay IA conectada"):
        run(router.call("sys", [{"role":"user","content":"hola"}], org_id="org-b"))

# 3. Sin permiso de plataforma, un cliente sin llave no consume la llave del servidor.
@respx.mock
def test_sin_permiso_no_usa_llave_plataforma(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-PLATAFORMA")
    monkeypatch.setenv("PLATFORM_KEYS_ORGS", "org-trial")
    with pytest.raises(RuntimeError, match="No hay IA conectada"):
        run(router.call("sys", [{"role":"user","content":"x"}], org_id="org-pago"))
    # el de trial sí puede
    respx.post(GROQ_URL).mock(return_value=ok("trial ok"))
    text, prov = run(router.call("sys", [{"role":"user","content":"x"}], org_id="org-trial"))
    assert prov == "groq" and text == "trial ok"

# 4. Si OpenRouter falla, cae a Groq y deja log del error.
@respx.mock
def test_fallback_openrouter_a_groq(monkeypatch):
    run(oc.set_credentials("openrouter", {"api_key": "sk-or-A"}, "org-a"))
    run(oc.set_credentials("groq", {"api_key": "gsk-A"}, "org-a"))
    respx.post(OR_URL).mock(return_value=httpx.Response(402, json={"error":{"message":"sin saldo"}}))
    respx.post(GROQ_URL).mock(return_value=ok("groq salva"))
    text, prov = run(router.call("s", [{"role":"user","content":"x"}], org_id="org-a"))
    assert prov == "groq" and text == "groq salva"
    oks = [d["ok"] for d in FAKE.llm_calls.docs]
    assert oks == [False, True]

# 5. ping honesto: si la llave de OpenRouter falla, NO marca ok aunque otro proveedor responda.
@respx.mock
def test_ping_honesto():
    run(oc.set_credentials("openrouter", {"api_key": "sk-or-mala"}, "org-a"))
    run(oc.set_credentials("groq", {"api_key": "gsk-A"}, "org-a"))
    respx.post(OR_URL).mock(return_value=httpx.Response(401, json={"error":{"message":"bad key"}}))
    respx.post(GROQ_URL).mock(return_value=ok("pong"))
    g = respx.routes[-1]
    r = run(router.ping("openrouter", "org-a"))
    assert r["ok"] is False and "401" in r["error"]
    assert not g.called, "ping no debe caer a otro proveedor"
    respx.post(OR_URL).mock(return_value=ok("pong"))
    assert run(router.ping("openrouter", "org-a"))["ok"] is True

# 6. tenant: el cliente sale del JWT de la sesión, no del default.
def test_tenant_desde_jwt():
    from routes.auth import COOKIE_NAME, JWT_SECRET, JWT_ALG
    import jwt
    from tenant import org_from_request
    tok = jwt.encode({"sub":"u1","org":"litper-colombia-ab12"}, JWT_SECRET, algorithm=JWT_ALG)
    req = types.SimpleNamespace(cookies={COOKIE_NAME: tok}, headers={})
    assert org_from_request(req) == "litper-colombia-ab12"
    assert org_from_request(types.SimpleNamespace(cookies={}, headers={})) == "default"

# 7. El modelo elegido por el cliente en su tarjeta se respeta.
@respx.mock
def test_modelo_del_cliente():
    run(oc.set_credentials("openrouter", {"api_key": "sk-or-A", "model": "openai/gpt-4o-mini"}, "org-a"))
    route = respx.post(OR_URL).mock(return_value=ok("ok"))
    run(router.call("s", [{"role":"user","content":"x"}], org_id="org-a"))
    assert json.loads(route.calls.last.request.content)["models"][0] == "openai/gpt-4o-mini"


# 8. CRÍTICO: un usuario con JWT (Bearer) NO puede elegir otro cliente con X-Org-Id.
def test_no_suplantacion_por_header(monkeypatch):
    from routes.auth import JWT_SECRET, JWT_ALG
    import jwt
    from tenant import org_from_request
    monkeypatch.setenv("PUBLIC_API_KEY", "plat-key")
    tok = jwt.encode({"sub":"u1","org":"org-a"}, JWT_SECRET, algorithm=JWT_ALG)
    req = types.SimpleNamespace(cookies={}, headers={"authorization": f"Bearer {tok}", "X-Org-Id": "org-victima"})
    assert org_from_request(req) == "org-a"
    # sin JWT y sin API key de plataforma, el header no sirve
    req2 = types.SimpleNamespace(cookies={}, headers={"X-Org-Id": "org-victima", "X-API-Key": "mala"})
    assert org_from_request(req2) == "default"
    # con la API key de plataforma (servidor-a-servidor) sí puede indicar el cliente
    req3 = types.SimpleNamespace(cookies={}, headers={"X-Org-Id": "org-x", "X-API-Key": "plat-key"})
    assert org_from_request(req3) == "org-x"

# 9. ALTO: la llave de Gemini nunca aparece en errores ni logs.
@respx.mock
def test_gemini_no_filtra_llave():
    run(oc.set_credentials("gemini", {"api_key": "AIzaSECRETO1234567890"}, "org-a"))
    respx.post(url__startswith="https://generativelanguage.googleapis.com").mock(return_value=httpx.Response(429, text="quota"))
    with pytest.raises(RuntimeError) as ei:
        run(router.call("s", [{"role":"user","content":"x"}], org_id="org-a"))
    assert "AIzaSECRETO" not in str(ei.value)
    assert all("AIzaSECRETO" not in d["error"] for d in FAKE.llm_calls.docs)
    r = run(router.ping("gemini", "org-a"))
    assert "AIzaSECRETO" not in r["error"]
    req = respx.calls.last.request
    assert "key=" not in str(req.url) and req.headers["x-goog-api-key"] == "AIzaSECRETO1234567890"

# 10. ALTO: guardar solo el modelo NO habilita la llave de plataforma si no tiene permiso.
@respx.mock
def test_solo_modelo_no_usa_plataforma(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-PLATAFORMA")
    monkeypatch.setenv("PLATFORM_KEYS_ORGS", "litper")
    run(oc.set_credentials("openrouter", {"model": "openai/gpt-4o-mini"}, "org-pago"))
    with pytest.raises(RuntimeError, match="No hay IA conectada"):
        run(router.call("s", [{"role":"user","content":"x"}], org_id="org-pago"))

# 11. ALTO: si falla el descifrado, no se cae a la llave de plataforma.
@respx.mock
def test_descifrado_roto_no_usa_plataforma(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-PLATAFORMA")
    monkeypatch.setenv("PLATFORM_KEYS_ORGS", "litper")
    run(oc.set_credentials("openrouter", {"api_key": "sk-or-A"}, "org-pago"))
    monkeypatch.delenv("ENCRYPTION_KEY")
    with pytest.raises(RuntimeError, match="No hay IA conectada"):
        run(router.call("s", [{"role":"user","content":"x"}], org_id="org-pago"))

# 12. El estado de credenciales no muestra pistas de llaves de plataforma a clientes sin permiso.
def test_status_no_muestra_llave_plataforma(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-PLATAFORMA-9999")
    monkeypatch.setenv("PLATFORM_KEYS_ORGS", "litper")
    st = {p["provider"]: p for p in run(oc.status("org-pago"))}
    assert st["openrouter"]["configured"] is False and st["openrouter"]["hint"] == ""
    st2 = {p["provider"]: p for p in run(oc.status("litper"))}
    assert st2["openrouter"]["configured"] is True

# 13. La pista de la llave de plataforma no se muestra NI con permiso "*".
def test_status_nunca_pista_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-PLATAFORMA-9999")
    monkeypatch.setenv("PLATFORM_KEYS_ORGS", "*")
    st = {p["provider"]: p for p in run(oc.status("org-nuevo"))}
    assert st["openrouter"]["origin"] == "env" and st["openrouter"]["hint"] == ""
    run(oc.set_credentials("openrouter", {"api_key": "sk-or-PROPIA-1234"}, "org-nuevo"))
    st = {p["provider"]: p for p in run(oc.status("org-nuevo"))}
    assert st["openrouter"]["origin"] == "org" and st["openrouter"]["hint"].endswith("1234")

# 14. JWT sin org -> 401; cookie vencida + Bearer válido -> org del Bearer.
def test_jwt_sin_org_y_bearer_respaldo():
    from routes.auth import COOKIE_NAME, JWT_SECRET, JWT_ALG
    import jwt
    from fastapi import HTTPException
    from tenant import org_from_request
    sin_org = jwt.encode({"sub":"u1"}, JWT_SECRET, algorithm=JWT_ALG)
    with pytest.raises(HTTPException):
        org_from_request(types.SimpleNamespace(cookies={COOKIE_NAME: sin_org}, headers={}))
    valido = jwt.encode({"sub":"u1","org":"org-b"}, JWT_SECRET, algorithm=JWT_ALG)
    req = types.SimpleNamespace(cookies={COOKIE_NAME: "vencida.invalida.x"}, headers={"authorization": f"Bearer {valido}"})
    assert org_from_request(req) == "org-b"

# 15. Guardar solo el modelo NO marca la IA como conectada.
def test_solo_modelo_no_es_conectado(monkeypatch):
    monkeypatch.setenv("PLATFORM_KEYS_ORGS", "litper")
    run(oc.set_credentials("openrouter", {"model": "openai/gpt-4o-mini"}, "org-pago"))
    st = {p["provider"]: p for p in run(oc.status("org-pago"))}
    assert st["openrouter"]["configured"] is False
