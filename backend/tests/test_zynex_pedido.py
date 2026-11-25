"""Ficha del pedido: un clic en cualquier fila abre todo lo del pedido (sin red)."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import pytest
from fastapi import HTTPException
from routes import zynex_motor as zm

ORG = "org-pedido"


class Req:
    headers = {}; cookies = {}


def _patch(monkeypatch, respuesta, llamadas):
    monkeypatch.setattr(zm, "get_org", lambda r: ORG)
    async def rpc(fn, args):
        llamadas.append((fn, args)); return respuesta
    monkeypatch.setattr(zm, "rpc", rpc)


def test_ficha_de_pedido(monkeypatch):
    ll = []
    _patch(monkeypatch, {"pedido": {"pedido": 9, "estado": "NOVEDAD"}, "historial": [{"accion": "humano"}],
                         "cliente": {"pedidos": [{"accion": None}]}}, ll)
    d = asyncio.run(zm.pedido("9", Req()))
    assert ll[-1] == ("zc_api_pedido", {"p_org": ORG, "p_pedido": 9})
    assert d["historial"][0]["accion_txt"] == "Pasa a una persona"
    assert d["cliente"]["pedidos"][0]["accion_txt"] == ""


def test_ficha_valida_numero_y_espacio(monkeypatch):
    ll = []
    _patch(monkeypatch, None, ll)
    with pytest.raises(HTTPException) as e:
        asyncio.run(zm.pedido("9; drop", Req()))
    assert e.value.status_code == 400 and ll == []
    with pytest.raises(HTTPException) as e:
        asyncio.run(zm.pedido("10", Req()))
    assert e.value.status_code == 404
