"""Traer mi operación: lectura del archivo de Dropi, periodo y envío por lotes (sin red)."""
import io, os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from datetime import date, timedelta
import pandas as pd
import pytest
from fastapi import HTTPException
from routes import zynex_importar as zi

def run(c): return asyncio.run(c)

class Req:
    headers = {}; cookies = {}

class Archivo:
    def __init__(self, data, nombre="ordenes.xlsx"): self._d = data; self.filename = nombre
    async def read(self): return self._d

def _excel(filas):
    buf = io.BytesIO(); pd.DataFrame(filas).to_excel(buf, index=False); return buf.getvalue()

def _fila(i, dias_atras, estado="ENTREGADO"):
    return {"ID": 9000 + i, "ESTATUS": estado, "NOMBRE CLIENTE": f"Cliente {i}", "TELÉFONO": "3001234567",
            "CIUDAD DESTINO": "CALI", "TRANSPORTADORA": "ENVIA", "NÚMERO GUIA": f"G{i}",
            "FECHA": (date.today() - timedelta(days=dias_atras)).strftime("%d-%m-%Y"), "TOTAL DE LA ORDEN": 149900,
            "PRODUCTO": "Sábana", "CANTIDAD": 1}

def _patch(monkeypatch, ll, resp=None):
    monkeypatch.setattr(zi, "get_org", lambda r: "org-i")
    async def rpc(fn, args):
        ll.append((fn, args)); return resp or {"ok": True, "guardados": len(args["p_filas"])}
    monkeypatch.setattr(zi.zynex_motor, "rpc", rpc)

def test_filas_de_filtra_periodo_y_datos():
    hoy = date(2026, 11, 25)
    cons = [{"external_ref": "101", "status_raw": "ENTREGADO", "order_date": "2026-11-20", "total_amount": 149900.4, "customer_phone": "300"},
            {"external_ref": "102", "status_raw": "NOVEDAD", "order_date": "2026-08-01", "total_amount": 1},
            {"external_ref": "", "status_raw": "X"}, {"external_ref": "103", "status_raw": "DEVOLUCION", "order_date": "", "total_amount": 0}]
    filas, d = zi.filas_de(cons, 30, hoy)
    assert [f["pedido"] for f in filas] == ["101", "103"] and d == {"sin_dato": 1, "fuera_de_periodo": 1}
    assert filas[0]["valor"] == "149900" and filas[0]["creado"] == "2026-11-20" and filas[1]["valor"] is None and filas[1]["creado"] is None

def test_importar_archivo_real(monkeypatch):
    ll = []; _patch(monkeypatch, ll)
    data = _excel([_fila(1, 5), _fila(2, 40), _fila(3, 100, "DEVOLUCION")])
    r = run(zi.importar(Req(), Archivo(data), dias=60))
    assert r["ok"] and r["guardados"] == 2 and r["fuera_de_periodo"] == 1
    fn, args = ll[-1]
    assert fn == "zc_api_pedidos_importar" and args["p_org"] == "org-i" and args["p_fuente"] == "archivo_dropi"
    assert {f["pedido"] for f in args["p_filas"]} == {"9001", "9002"} and args["p_filas"][0]["nombre"].startswith("Cliente")

def test_importar_rechaza(monkeypatch):
    ll = []; _patch(monkeypatch, ll)
    with pytest.raises(HTTPException): run(zi.importar(Req(), Archivo(b"x"), dias=45))
    with pytest.raises(HTTPException): run(zi.importar(Req(), Archivo(b""), dias=30))
    with pytest.raises(HTTPException): run(zi.importar(Req(), Archivo(b"no es un excel", "a.xlsx"), dias=30))
    with pytest.raises(HTTPException): run(zi.importar(Req(), Archivo(_excel([_fila(1, 100)])), dias=30))
    assert ll == []
    _patch(monkeypatch, ll, {"ok": False, "error": "espacio no vinculado"})
    with pytest.raises(HTTPException) as e: run(zi.importar(Req(), Archivo(_excel([_fila(1, 2)])), dias=30))
    assert "Activa tu espacio" in e.value.detail


def test_pedir_y_solicitudes(monkeypatch):
    ll = []; _patch(monkeypatch, ll, {"ok": True, "id": 7})
    with pytest.raises(HTTPException): run(zi.pedir(zi.PedirIn(dias=45), Req()))
    r = run(zi.pedir(zi.PedirIn(dias=60), Req()))
    assert r["ok"] and r["id"] == 7 and ll[-1] == ("zc_api_solicitud_crear", {"p_org": "org-i", "p_tipo": "traer_operacion", "p_params": {"dias": 60}, "p_origen": "app"})
    _patch(monkeypatch, ll, {"solicitudes": [{"solicitud_id": 7}]})
    assert run(zi.solicitudes(Req()))["solicitudes"][0]["solicitud_id"] == 7 and ll[-1][1]["p_generar"] is False

def test_mcp_logistica_ida_y_vuelta(monkeypatch):
    from routes import zynex_mcp as zm
    ll = []
    async def rpc(fn, args):
        ll.append((fn, args))
        return {"zc_api_solicitudes": {"solicitudes": [{"solicitud_id": 3, "tipo": "traer_operacion"}]},
                "zc_api_entregar": {"ok": True, "guardados": 1},
                "zc_api_panel": {"vinculado": True, "modo": "sombra", "por_estado": [{"titulo": "NOVEDAD", "n": 4}]},
                "zc_api_metricas": {"kpis": [{"titulo": "Tasa de entrega", "valor": 88}], "transportadoras": []},
                "zc_api_clientes": {"resumen": {"atencion": 2}}}[fn]
    async def evento(org, tipo, datos): ll.append(("evento", tipo))
    monkeypatch.setattr(zm.zynex_motor, "rpc", rpc); monkeypatch.setattr(zm.zc, "evento", evento)
    import json
    sol = json.loads(run(zm._call("org-m", "zynex_logistica_solicitudes", {}))["content"][0]["text"])
    assert sol["solicitudes"][0]["solicitud_id"] == 3 and ll[-1][1] == {"p_org": "org-m", "p_generar": True}
    run(zm._call("org-m", "zynex_logistica_entregar", {"pedidos": [{"pedido": 55, "estado": "NOVEDAD", "otro": "x"}], "solicitud_id": 3, "final": True}))
    fn, args = [x for x in ll if x[0] == "zc_api_entregar"][-1]
    assert args["p_org"] == "org-m" and args["p_solicitud"] == 3 and args["p_final"] is True
    assert args["p_filas"][0]["pedido"] == "55" and "otro" not in args["p_filas"][0]
    for malo in [{}, {"pedidos": "x"}, {"pedidos": [{"pedido": "1", "estado": "X"}] * 501}]:
        with pytest.raises(ValueError): run(zm._call("org-m", "zynex_logistica_entregar", malo))
    res = json.loads(run(zm._call("org-m", "zynex_logistica_resumen", {"dias": 999}))["content"][0]["text"])
    assert res["pedidos_por_estado"] == {"NOVEDAD": 4} and res["metricas"]["Tasa de entrega"] == 88 and res["clientes"]["atencion"] == 2
    assert {t["name"] for t in zm.TOOLS} >= {"zynex_logistica_solicitudes", "zynex_logistica_entregar", "zynex_logistica_resumen"}
