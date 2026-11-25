"""Todo el detalle de Dropi llega a la ficha del pedido, y las peticiones a Claude se pueden cerrar (sin red)."""
import io, os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from datetime import date
import pandas as pd
import pytest
from fastapi import HTTPException
from routes import zynex_importar as zi
from routes import zynex_mcp as zm
from dropi_import import parse_sheet


class Req:
    headers = {}; cookies = {}


def test_claude_entrega_el_detalle_completo():
    p = {"pedido": "98150078", "estado": "INTENTO DE ENTREGA", "direccion": "Carrera 65 #103-44",
         "productos": [{"producto": "Cortina", "cantidad": 1, "precio": 50000}], "otros": {"bodega": "Medellín"},
         "vacio": "", "telefono": "3001112233"}
    d = zm.datos_extra(p)
    assert d == {"direccion": "Carrera 65 #103-44", "productos": [{"producto": "Cortina", "cantidad": 1, "precio": 50000}],
                 "otros": {"bodega": "Medellín"}}
    assert "telefono" not in d and "pedido" not in d


def test_detalle_demasiado_grande_se_descarta_sin_romper():
    assert zm.datos_extra({"pedido": "1", "estado": "X", "otros": {f"k{i}": "x" * 400 for i in range(80)}}) == {}
    assert zm._limpio("a" * 900) == "a" * 500


def test_reporte_de_dropi_guarda_todas_las_columnas():
    buf = io.BytesIO()
    pd.DataFrame([{"ID": 77, "ESTATUS": "ENTREGADO", "TELÉFONO": "3001234567", "DIRECCIÓN": "Calle 5",
                   "DEPARTAMENTO DESTINO": "VALLE", "FECHA": date.today().strftime("%d-%m-%Y"),
                   "TOTAL DE LA ORDEN": 99900, "PRODUCTO": "Sábana", "CANTIDAD": 2, "GANANCIA": 30000}]).to_excel(buf, index=False)
    res = parse_sheet(buf.getvalue(), "o.xlsx", None)
    filas, _ = zi.filas_de(res.consolidated, 30, crudo=zi.columnas_por_pedido(buf.getvalue(), "o.xlsx"))
    d = filas[0]["datos"]
    assert d["direccion"] == "Calle 5" and d["departamento"] == "VALLE"
    assert d["productos"][0]["producto"] == "Sábana" and d["productos"][0]["cantidad"] == 2
    assert d["otros"]["GANANCIA"] == "30000"


def test_terminar_peticion(monkeypatch):
    ll = []
    monkeypatch.setattr(zi, "get_org", lambda r: "org-d")
    async def rpc(fn, args):
        ll.append((fn, args)); return {"ok": args["p_id"] == 5, "cerradas": 13}
    monkeypatch.setattr(zi.zynex_motor, "rpc", rpc)
    r = asyncio.run(zi.terminar(5, Req()))
    assert r["cerradas"] == 13 and ll[-1] == ("zc_api_solicitud_cerrar", {"p_org": "org-d", "p_id": 5})
    with pytest.raises(HTTPException):
        asyncio.run(zi.terminar(6, Req()))
