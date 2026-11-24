"""Configuración automática de Zynex Call: número verificado, agentes y webhook (sin red)."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import test_byok_openrouter as banco
from fake_mongo import DB as RichDB
banco.FAKE.__class__ = RichDB
import httpx, respx
from fastapi import HTTPException
from routes import zynex_call as zc, zynex_auto as za

ORG = "org-auto"
def run(c): return asyncio.run(c)

class Req:  # petición mínima para get_org/public_base
    def __init__(self): self.headers = {}; self.cookies = {}
    url = type("U", (), {"scheme": "https", "netloc": "api.zynexapp.com"})()

def _patch(monkeypatch, el):
    monkeypatch.setattr(za, "get_org", lambda r: ORG)
    async def llave(org, prov, campo="api_key"): return "k"
    monkeypatch.setattr(zc, "_llave", llave)
    monkeypatch.setattr(zc, "_el", el)

def test_plantillas_completas():
    assert [t["agente"] for t in za.PLANTILLAS] == ["confirmacion", "novedad", "oficina", "reparto", "devolucion"]
    b = za.cuerpo_agente(za.PLANTILLAS[0], "Litper", "voz1")
    assert "Litper" in b["conversation_config"]["agent"]["first_message"]
    assert "{{cliente}}" in b["conversation_config"]["agent"]["first_message"]
    assert "resultado" in b["platform_settings"]["data_collection"]
    for t in za.PLANTILLAS:  # todos los resultados de cada plantilla los entiende el webhook
        for r in t["resultados"].split(","):
            assert zc.norm_resultado(r.strip()), r

def test_crear_agentes_con_respaldo_de_voz(monkeypatch):
    llamadas = []
    async def el(org, method, path, **kw):
        llamadas.append(kw["json"].get("conversation_config", {}).get("tts"))
        if kw["json"]["conversation_config"].get("tts"): return 422, {}
        return 200, {"agent_id": f"agent_x{len(llamadas)}"}
    _patch(monkeypatch, el)
    r = run(za.crear_agentes(za.AgentesIn(negocio="Litper", voice_id="no-existe"), Req()))
    assert len(r["creados"]) == 5 and not r["errores"]
    ag = run(banco.FAKE.zc_agentes.find_one({"org_id": ORG, "agente": "novedad"}))
    assert ag["elevenlabs_agent_id"].startswith("agent_x")
    r2 = run(za.crear_agentes(za.AgentesIn(negocio="Litper"), Req()))  # no duplica
    assert r2["creados"] == []

@respx.mock
def test_numero_verificado_con_subcuenta(monkeypatch):
    monkeypatch.setenv("ZYNEX_TWILIO_MASTER_SID", "ACmaster"); monkeypatch.setenv("ZYNEX_TWILIO_MASTER_TOKEN", "tok")
    respx.post(f"{za.TW}/Accounts.json").mock(return_value=httpx.Response(201, json={"sid": "ACsub1", "auth_token": "subtok"}))
    respx.post(f"{za.TW}/Accounts/ACsub1/OutgoingCallerIds.json").mock(
        return_value=httpx.Response(201, json={"validation_code": "123456"}))
    respx.get(f"{za.TW}/Accounts/ACsub1/OutgoingCallerIds.json").mock(
        return_value=httpx.Response(200, json={"outgoing_caller_ids": [{"phone_number": "+573144644054"}]}))
    enviado = {}
    async def el(org, method, path, **kw):
        enviado.update(kw["json"]); return 200, {"phone_number_id": "phnum_1"}
    _patch(monkeypatch, el)
    r = run(za.verificar(za.VerificarIn(numero="314 464 4054"), Req()))
    assert r["codigo"] == "123456"
    r = run(za.confirmar(Req()))
    assert r["ok"] and enviado["sid"] == "ACsub1" and enviado["phone_number"] == "+573144644054"
    cfg = run(banco.FAKE.zc_config.find_one({"org_id": ORG}))
    assert cfg["phone_number_id"] == "phnum_1" and "subtok" not in str(cfg)  # token cifrado

def test_sin_telefonia_da_mensaje_claro(monkeypatch):
    monkeypatch.delenv("ZYNEX_TWILIO_MASTER_SID", raising=False)
    monkeypatch.setattr(za, "get_org", lambda r: "org-sin")
    try:
        run(za.cuenta_twilio("org-sin")); assert False
    except HTTPException as e:
        assert "314 464 4054" in e.detail
