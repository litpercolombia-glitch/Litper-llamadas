"""Formulario de descubrimiento: validación, trampa de bots, límite y permisos (sin red)."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
import ratelimit
from routes import zynex_encuesta as ze

def run(c): return asyncio.run(c)

class Req:
    def __init__(self, ip="1.2.3.4"):
        self.headers = {"x-forwarded-for": ip}; self.cookies = {}; self.client = None

BASE = dict(pedidos_dia="20_100", pais="Colombia", dolores=["oficina", "oficina", "novedades"], quien="una_persona")

def _rpc(monkeypatch, resp, ll):
    async def rpc(fn, args):
        ll.append((fn, args)); return resp
    monkeypatch.setattr(ze, "rpc", rpc)

def test_valida_campos():
    with pytest.raises(ValidationError): ze.EncuestaIn(**{**BASE, "pedidos_dia": "mil"})
    with pytest.raises(ValidationError): ze.EncuestaIn(**{**BASE, "dolores": []})
    with pytest.raises(ValidationError): ze.EncuestaIn(**{**BASE, "dolores": ["hackear"]})

def test_guarda_sin_whatsapp_si_no_acepta(monkeypatch):
    ll = []; _rpc(monkeypatch, 1, ll); ratelimit._hits.clear()
    r = run(ze.responder(ze.EncuestaIn(**BASE, whatsapp="3000000000", acepta_contacto=False), Req("9.9.9.1")))
    assert r["ok"]
    fn, args = ll[-1]
    assert fn == "zc_form_guardar" and args["p"]["whatsapp"] is None
    assert args["p"]["dolores"] == ["oficina", "novedades"]  # sin repetidos
    assert len(args["p_ip_hash"]) == 32 and "9.9.9.1" not in args["p_ip_hash"]

def test_trampa_de_bots_no_guarda(monkeypatch):
    ll = []; _rpc(monkeypatch, 1, ll)
    assert run(ze.responder(ze.EncuestaIn(**BASE, sitio_web="http://spam"), Req()))["ok"]
    assert ll == []

def test_limite_por_conexion(monkeypatch):
    ll = []; _rpc(monkeypatch, 1, ll); ratelimit._hits.clear()
    for _ in range(ze.MAX_POR_HORA):
        run(ze.responder(ze.EncuestaIn(**BASE), Req("7.7.7.7")))
    with pytest.raises(HTTPException) as e: run(ze.responder(ze.EncuestaIn(**BASE), Req("7.7.7.7")))
    assert e.value.status_code == 429

def test_resultados_solo_equipo(monkeypatch):
    monkeypatch.setattr(ze, "get_org", lambda r: "org-x")
    ll = []; _rpc(monkeypatch, None, ll)
    with pytest.raises(HTTPException) as e: run(ze.resultados(Req()))
    assert e.value.status_code == 403
    _rpc(monkeypatch, {"total": 3}, ll)
    assert run(ze.resultados(Req()))["total"] == 3
