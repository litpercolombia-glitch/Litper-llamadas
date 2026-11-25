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


def test_clientes_filtro_y_telefono(monkeypatch):
    ll = []
    _patch(monkeypatch, {"zc_api_clientes": {"vinculado": True, "filas": []}, "zc_api_cliente": None,
                         "zc_api_cliente_nota": True, "zc_api_cliente_caso": True}, ll)
    monkeypatch.setattr(zm, "_autor", lambda r: "Ana")
    with pytest.raises(HTTPException): run(zm.clientes(Req(), filtro="otro"))
    run(zm.clientes(Req(), q="  neiva  ", filtro="riesgo", limite=9999))
    assert ll[-1][1] == {"p_org": ORG, "p_q": "neiva", "p_filtro": "riesgo", "p_limite": 300}
    for malo in ["123", "abc", "30012345"]:
        with pytest.raises(HTTPException) as e: run(zm.cliente(malo, Req()))
        assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e: run(zm.cliente("+57 300 123 4567", Req()))
    assert e.value.status_code == 404 and ll[-1][1]["p_tel"] == "3001234567"
    assert run(zm.cliente_nota("3001234567", zm.NotaIn(texto=" llamar en la tarde "), Req()))["ok"]
    assert ll[-1][1] == {"p_org": ORG, "p_tel": "3001234567", "p_texto": "llamar en la tarde", "p_autor": "Ana"}
    assert "persona" in run(zm.cliente_caso("3001234567", zm.CasoIn(estado="abierto", motivo="reclamo"), Req()))["mensaje"]
    with pytest.raises(Exception): zm.CasoIn(estado="borrar")

def test_metricas_y_lista(monkeypatch):
    ll = []
    _patch(monkeypatch, {"zc_api_metricas": {"kpis": []}, "zc_api_metrica_lista": [{"pedido": 1, "cliente": "Luz Marina"}]}, ll)
    run(zm.metricas(Req(), dias=999)); assert ll[-1][1]["p_dias"] == 90
    for malo in ["", "estado:NOVEDAD", "m:x';--", "m:" + "a" * 40]:
        with pytest.raises(HTTPException): run(zm.metricas_lista(malo, Req()))
    d = run(zm.metricas_lista("m:oficina4", Req()))
    assert d["filas"][0]["cliente"] == "Luz" and ll[-1][1]["p_org"] == ORG


def test_espacio_automatico_solo_en_funciones_de_la_app(monkeypatch):
    import asyncio as _a
    monkeypatch.setattr(zm, "configurado", lambda: True)
    zm._CON_ESPACIO.clear()
    llamadas = []
    class R:
        def __init__(self, d, c=200): self._d = d; self.status_code = c
        def json(self): return self._d
    async def post(fn, args):
        llamadas.append(fn); return R({"ok": True} if fn == "zc_ws_asegurar" else {"x": 1})
    monkeypatch.setattr(zm, "_post", post)
    run(zm.rpc("zc_api_panel", {"p_org": "org-nueva"}))
    run(zm.rpc("zc_api_clientes", {"p_org": "org-nueva"}))
    assert llamadas == ["zc_ws_asegurar", "zc_api_panel", "zc_api_clientes"]
    run(zm.rpc("zc_form_resultados", {"p_org": "org-otra"}))
    assert "zc_ws_asegurar" not in llamadas[3:]
