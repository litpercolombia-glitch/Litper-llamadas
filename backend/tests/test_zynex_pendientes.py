"""Pendientes de Chatea: validación de columnas y parámetros (sin red)."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from routes import zynex_pendientes as zp

def run(c): return asyncio.run(c)

class Req:
    headers = {}; cookies = {}

def _patch(monkeypatch, resp, ll):
    monkeypatch.setattr(zp, "get_org", lambda r: "org-p")
    async def rpc(fn, args):
        ll.append((fn, args)); return resp
    monkeypatch.setattr(zp.zynex_motor, "rpc", rpc)

def test_guardar_limpia_columnas_y_parametros(monkeypatch):
    ll = []; _patch(monkeypatch, True, ll)
    r = run(zp.guardar("oficina", zp.PendienteIn(activo=True, columnas=[" karen ", "KAREN", "", "Datos completados"], adelanto=20000, llamar=True), Req()))
    assert r["ok"]
    assert ll[-1] == ("zc_api_pendiente_guardar", {"p_org": "org-p", "p_clase": "oficina", "p_activo": True,
                      "p_columnas": ["KAREN", "DATOS COMPLETADOS"], "p_params": {"adelanto": 20000, "llamar": True}})

def test_rechaza_invalidos(monkeypatch):
    ll = []; _patch(monkeypatch, True, ll)
    with pytest.raises(HTTPException): run(zp.guardar("otra", zp.PendienteIn(), Req()))
    with pytest.raises(HTTPException): run(zp.guardar("diario", zp.PendienteIn(columnas=["x';drop"]), Req()))
    for malo in [dict(adelanto=-1), dict(adelanto=900000), dict(dias_sin_respuesta=0), dict(plantillas=4), dict(columnas=["a"] * 11)]:
        with pytest.raises(ValidationError): zp.PendienteIn(**malo)
    assert ll == []

def test_base_rechaza(monkeypatch):
    ll = []; _patch(monkeypatch, False, ll)
    with pytest.raises(HTTPException): run(zp.guardar("final", zp.PendienteIn(dias_sin_respuesta=2, plantillas=3), Req()))

def test_lista(monkeypatch):
    ll = []; _patch(monkeypatch, [{"clase": "diario"}], ll)
    assert run(zp.pendientes(Req()))["reglas"][0]["clase"] == "diario"
