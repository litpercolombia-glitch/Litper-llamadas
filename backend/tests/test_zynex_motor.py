"""Agente de Logística: panel, lista, casillas y vinculación (sin red)."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import pytest
from fastapi import HTTPException
from routes import zynex_motor as zm

ORG = "org-motor"
def run(c): return asyncio.run(c)

class Req:
    headers = {}; cookies = {}

def _patch(monkeypatch, respuestas, llamadas):
    monkeypatch.setattr(zm, "get_org", lambda r: ORG)
    monkeypatch.setattr(zm, "configurado", lambda: True)
    async def rpc(fn, args):
        llamadas.append((fn, args)); return respuestas[fn]
    monkeypatch.setattr(zm, "rpc", rpc)

def test_panel_sin_conectar(monkeypatch):
    monkeypatch.setattr(zm, "configurado", lambda: False)
    assert run(zm.panel(Req())) == {"conectado": False, "vinculado": False}

def test_panel_traduce_acciones(monkeypatch):
    ll = []
    _patch(monkeypatch, {"zc_api_panel": {"vinculado": True, "tareas": [{"titulo": "esperar_ventana", "n": 3, "clave": "accion:esperar_ventana"}]}}, ll)
    d = run(zm.panel(Req()))
    assert d["conectado"] and d["tareas"][0]["titulo"] == "Espera el horario"
    assert ll[0] == ("zc_api_panel", {"p_org": ORG})  # siempre con la org de la sesión

def test_lista_valida_filtro_y_recorta_nombre(monkeypatch):
    ll = []
    _patch(monkeypatch, {"zc_api_lista": [{"pedido": 1, "cliente": "Ana María Pérez", "accion": "humano"}]}, ll)
    for malo in ["", "estado", "otro:x", "estado:x';drop", "accion:" + "a" * 80]:
        with pytest.raises(HTTPException): run(zm.lista(malo, Req()))
    d = run(zm.lista("estado:RECLAME EN OFICINA", Req(), limite=9999))
    assert d["filas"][0]["cliente"] == "Ana" and d["filas"][0]["accion_txt"] == "Pasa a una persona"
    assert ll[-1][1]["p_limite"] == 500 and ll[-1][1]["p_org"] == ORG

def test_casilla_guardar_y_validar(monkeypatch):
    ll = []
    _patch(monkeypatch, {"zc_api_casilla_guardar": True}, ll)
    assert run(zm.guardar_casilla("oficina_1", zm.CasillaIn(plantilla=" Mi_Plantilla_V2 "), Req()))["ok"]
    assert ll[-1][1] == {"p_org": ORG, "p_slot": "oficina_1", "p_plantilla": "mi_plantilla_v2"}
    assert "vaciada" in run(zm.guardar_casilla("oficina_1", zm.CasillaIn(plantilla=""), Req()))["mensaje"]
    with pytest.raises(HTTPException): run(zm.guardar_casilla("oficina_1", zm.CasillaIn(plantilla="con espacios"), Req()))
    with pytest.raises(HTTPException): run(zm.guardar_casilla("../x", zm.CasillaIn(plantilla="ok"), Req()))

def test_vincular(monkeypatch):
    ll = []
    _patch(monkeypatch, {"zc_api_vincular": False}, ll)
    with pytest.raises(HTTPException): run(zm.vincular(zm.VincularIn(codigo="codigo-malo"), Req()))
    _patch(monkeypatch, {"zc_api_vincular": True}, ll)
    assert run(zm.vincular(zm.VincularIn(codigo=" codigo-bueno "), Req()))["ok"]
    assert ll[-1][1]["p_codigo"] == "codigo-bueno"

def test_rpc_sin_llave_da_503(monkeypatch):
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(HTTPException) as e: run(zm.rpc("zc_api_panel", {}))
    assert e.value.status_code == 503
