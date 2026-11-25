"""El asistente con herramientas de Logística y Clientes (sin red)."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import pytest
from agent import tools, tools_logistica as tl

CTX = {"org_id": "org-l"}


def _patch(monkeypatch, resp, ll):
    async def rpc(fn, args):
        ll.append((fn, args)); return resp.get(fn)
    monkeypatch.setattr(tl, "_rpc", rpc)


def test_registradas_y_escritura_con_confirmacion():
    for n in ("logistica_resumen", "logistica_pedidos", "logistica_pedido", "clientes_buscar", "cliente_nota", "cliente_caso"):
        assert n in tools.TOOLS
    assert {"cliente_nota", "cliente_caso"} <= tools.CONFIRM_TOOLS
    assert "logistica_resumen" not in tools.CONFIRM_TOOLS
    assert "logistica_pedido" in tools.UNTRUSTED_NATIVE


def test_resumen_y_pedidos_solo_del_org(monkeypatch):
    ll = []
    _patch(monkeypatch, {"zc_api_panel": {"modo": "sombra", "por_estado": [{"titulo": "NOVEDAD", "n": 3}]},
                         "zc_api_metricas": {"kpis": [{"titulo": "Tasa de entrega", "valor": 89.2}]},
                         "zc_api_clientes": {"resumen": {"atencion": 2}},
                         "zc_api_lista": [{"pedido": 1, "ciudad": "CALI", "dias": 5, "cliente": "X"}]}, ll)
    r = asyncio.run(tl.tool_logistica_resumen(CTX, 30))
    assert r["pedidos_por_estado"] == {"NOVEDAD": 3} and r["metricas"]["Tasa de entrega"] == 89.2
    p = asyncio.run(tl.tool_logistica_pedidos(CTX, "novedad"))
    assert p["total"] == 1 and "cliente" not in p["pedidos"][0]
    assert all(a["p_org"] == "org-l" for _, a in ll)
    assert ("zc_api_lista", {"p_org": "org-l", "p_clave": "estado:NOVEDAD", "p_limite": 30}) in ll


def test_validaciones(monkeypatch):
    ll = []
    _patch(monkeypatch, {"zc_api_pedido": None, "zc_api_cliente_nota": False}, ll)
    for coro in (tl.tool_logistica_pedidos(CTX, "x; drop"), tl.tool_logistica_pedido(CTX, "abc"),
                 tl.tool_logistica_pedido(CTX, "99"), tl.tool_cliente_nota(CTX, "123", "hola"),
                 tl.tool_cliente_nota(CTX, "3001112233", "hola"), tl.tool_cliente_caso(CTX, "3001112233", "otro"),
                 tl.tool_clientes_buscar(CTX, "", "raro")):
        with pytest.raises(tools.ToolError):
            asyncio.run(coro)
