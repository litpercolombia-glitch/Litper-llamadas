"""HTTP-level tests for /api/dropi/* endpoints (preview → import → prompt-vars)."""
from __future__ import annotations

import io
import os
import time

import pandas as pd
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    "https://litper-hub.preview.emergentagent.com"
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"
H = {"X-API-Key": API_KEY}


def _rows(tid_suffix: str):
    """Return the 4-row combo+single fixture with a unique ID/guia namespace."""
    a = f"T{tid_suffix}1"
    b = f"T{tid_suffix}2"
    ga = f"TSG-{tid_suffix}-A"
    gb = f"TIR-{tid_suffix}-B"
    common = dict(
        NOMBRE_CLIENTE_="",
        # placeholders — real cols below
    )
    del common
    return pd.DataFrame([
        {"ID": a, "NÚMERO GUIA": ga,
         "NOMBRE CLIENTE": "María Pérez", "TELÉFONO": "+573001234567",
         "CIUDAD DESTINO": "Medellín", "DIRECCION": "Cra 50 #10-20",
         "TRANSPORTADORA": "SERVIENTREGA", "ESTATUS": "RECLAME EN OFICINA",
         "TIPO DE ENVIO": "CON RECAUDO", "VENDEDOR": "V1", "TIENDA": "Litper",
         "FECHA": "2026-02-01", "FECHA GUIA GENERADA": "2026-02-02",
         "PRODUCTO": "Protector Antifluido", "VARIACION": "Verde/Doble",
         "SKU": "PA-V", "PRODUCTO ID": 111, "VARIACION ID": 1111,
         "CANTIDAD": 1, "TOTAL DE LA ORDEN": 150000,
         "PRECIO PROVEEDOR": 45000},
        {"ID": a, "NÚMERO GUIA": ga,
         "NOMBRE CLIENTE": "María Pérez", "TELÉFONO": "+573001234567",
         "CIUDAD DESTINO": "Medellín", "DIRECCION": "Cra 50 #10-20",
         "TRANSPORTADORA": "SERVIENTREGA", "ESTATUS": "RECLAME EN OFICINA",
         "TIPO DE ENVIO": "CON RECAUDO", "VENDEDOR": "V1", "TIENDA": "Litper",
         "FECHA": "2026-02-01", "FECHA GUIA GENERADA": "2026-02-02",
         "PRODUCTO": "Protector Antifluido", "VARIACION": "Lila/Semi",
         "SKU": "PA-L", "PRODUCTO ID": 111, "VARIACION ID": 1112,
         "CANTIDAD": 1, "TOTAL DE LA ORDEN": 150000,
         "PRECIO PROVEEDOR": 45000},
        {"ID": a, "NÚMERO GUIA": ga,
         "NOMBRE CLIENTE": "María Pérez", "TELÉFONO": "+573001234567",
         "CIUDAD DESTINO": "Medellín", "DIRECCION": "Cra 50 #10-20",
         "TRANSPORTADORA": "SERVIENTREGA", "ESTATUS": "RECLAME EN OFICINA",
         "TIPO DE ENVIO": "CON RECAUDO", "VENDEDOR": "V1", "TIENDA": "Litper",
         "FECHA": "2026-02-01", "FECHA GUIA GENERADA": "2026-02-02",
         "PRODUCTO": "Bono Regalo", "VARIACION": "20k",
         "SKU": "BR-20", "PRODUCTO ID": 222, "VARIACION ID": 2221,
         "CANTIDAD": 1, "TOTAL DE LA ORDEN": 150000,
         "PRECIO PROVEEDOR": 5000},
        {"ID": b, "NÚMERO GUIA": gb,
         "NOMBRE CLIENTE": "Juan Ríos", "TELÉFONO": "+573109999999",
         "CIUDAD DESTINO": "Bogotá", "DIRECCION": "Calle 100 #10-10",
         "TRANSPORTADORA": "INTERRAPIDISIMO", "ESTATUS": "RECLAME EN OFICINA",
         "TIPO DE ENVIO": "CON RECAUDO", "VENDEDOR": "V2", "TIENDA": "Litper",
         "FECHA": "2026-02-01", "FECHA GUIA GENERADA": "2026-02-02",
         "PRODUCTO": "Botella Térmica", "VARIACION": "Negra/500ml",
         "SKU": "BT-N500", "PRODUCTO ID": 333, "VARIACION ID": 3331,
         "CANTIDAD": 1, "TOTAL DE LA ORDEN": 85000,
         "PRECIO PROVEEDOR": 30000}])


def _xlsx_bytes(df: pd.DataFrame, sheets: dict[str, pd.DataFrame] | None = None) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Reclamos")
        if sheets:
            for name, sdf in sheets.items():
                sdf.to_excel(w, index=False, sheet_name=name)
    return buf.getvalue()


# session-wide identifiers so we can chain preview → import → prompt-vars → dedup
TID = str(int(time.time()))


@pytest.fixture(scope="module")
def preview():
    df = _rows(TID)
    data = _xlsx_bytes(df, {"Otra": pd.DataFrame([{"x": 1}])})

    # /dropi/sheets returns all sheets
    r = requests.post(f"{BASE_URL}/api/dropi/sheets", headers=H,
                      files={"file": ("d.xlsx", data,
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    assert set(r.json()["sheets"]) >= {"Reclamos", "Otra"}

    # /dropi/preview
    r = requests.post(f"{BASE_URL}/api/dropi/preview", headers=H,
                      files={"file": ("d.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                      data={"sheet": "Reclamos"})
    assert r.status_code == 200, r.text
    return r.json()


def test_preview_metrics(preview):
    assert preview["raw_row_count"] == 4
    assert preview["consolidated_count"] == 2
    assert preview["combo_orders"] == 1
    assert preview["total_recaudo"] == 235000
    assert preview["naive_sum_recaudo"] == 535000
    joined = " ".join(preview.get("warnings", []))
    assert ("múltiples filas" in joined) or ("combos" in joined)


def test_preview_consolidated_combo_shape(preview):
    combo = next(e for e in preview["consolidated"] if e["items_count"] == 3)
    assert combo["is_combo"] is True
    assert combo["total_amount"] == 150000
    assert combo["products_display"].count("+") == 2
    skus = sorted(i["sku"] for i in combo["items"])
    assert skus == ["BR-20", "PA-L", "PA-V"]


def test_import_and_dedup(preview):
    # First import
    r = requests.post(f"{BASE_URL}/api/dropi/import", headers=H,
                      json={"preview_id": preview["id"], "country": "CO"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["imported_count"] == 2, d
    assert d["error_count"] == 0

    combo = next(i for i in d["imported"] if i["is_combo"])
    assert combo["recaudo"] == 150000
    assert combo["products_display"].count("+") == 2

    # Re-import → deduped
    r2 = requests.post(f"{BASE_URL}/api/dropi/import", headers=H,
                       json={"preview_id": preview["id"], "country": "CO"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["skipped_count"] == 2, d2
    assert d2["imported_count"] == 0

    # Persist order id for prompt-vars test
    pytest.combo_order_id = combo["order_id"]


def test_order_persisted(preview):
    oid = getattr(pytest, "combo_order_id", None)
    assert oid, "combo order id not captured"
    r = requests.get(f"{BASE_URL}/api/orders/{oid}", headers=H)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["total_amount"] == 150000
    assert o["is_combo"] is True
    assert len(o["items"]) == 3
    assert o["products_display"].count("+") == 2


def test_prompt_vars_combo():
    oid = getattr(pytest, "combo_order_id", None)
    r = requests.get(f"{BASE_URL}/api/orders/{oid}/prompt-vars", headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["items_count"] == 3
    assert d["is_combo"] is True
    assert "+" in d["product_name"]
    # references is comma-separated SKUs
    refs = [s.strip() for s in d["references"].split(",")]
    assert sorted(refs) == ["BR-20", "PA-L", "PA-V"]


def test_no_id_column_grouped_by_guia():
    df = _rows(TID + "N").drop(columns=["ID"])
    data = _xlsx_bytes(df)
    r = requests.post(f"{BASE_URL}/api/dropi/preview", headers=H,
                      files={"file": ("noid.xlsx", data,
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["consolidated_count"] == 2
    combo = next(e for e in d["consolidated"] if e["items_count"] == 3)
    assert combo["total_amount"] == 150000
    assert combo["tracking_number"].startswith("TSG-")
