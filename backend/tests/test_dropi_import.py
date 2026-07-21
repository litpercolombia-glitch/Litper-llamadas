"""
Tests for the Dropi Excel importer.

Verifies the CRITICAL rule: a Dropi export with combos/promos writes
ONE ORDER as MULTIPLE ROWS. The importer must:
  * group by ID (or NUMERO GUIA)
  * take TOTAL DE LA ORDEN ONCE per group (never sum across rows)
  * concatenate product+variation lines into items[] and products_display
  * mark is_combo=True when items > 1
  * NEVER use PRECIO PROVEEDOR for the recaudo
"""
from __future__ import annotations

import io
import pandas as pd
import pytest

from dropi_import import parse_sheet, detect_column_map, normalize_carrier


def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Reclamos")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixture: a combo order of 2 products + a single-product order.
#          Each product/variation is its own row per Dropi convention.
# ---------------------------------------------------------------------------
COMBO_ORDER_ROWS = pd.DataFrame([
    {
        "ID": 1001, "NÚMERO GUIA": "SGT-987",
        "NOMBRE CLIENTE": "María Pérez", "TELÉFONO": "+573001234567",
        "CIUDAD DESTINO": "Medellín", "DEPARTAMENTO DESTINO": "Antioquia",
        "DIRECCION": "Cra 50 #10-20", "NOTAS": "",
        "TRANSPORTADORA": "SERVIENTREGA", "ESTATUS": "RECLAME EN OFICINA",
        "TIPO DE ENVIO": "CON RECAUDO", "VENDEDOR": "V1", "TIENDA": "Litper",
        "FECHA": "2026-02-01", "FECHA GUIA GENERADA": "2026-02-02",
        "NOVEDAD": "",
        "PRODUCTO": "Protector Antifluido", "VARIACION": "Verde Menta/Doble",
        "SKU": "PA-VMD", "PRODUCTO ID": 111, "VARIACION ID": 1111,
        "CANTIDAD": 1,
        "TOTAL DE LA ORDEN": 150000,      # ← identical on every row of the order
        "PRECIO PROVEEDOR": 45000,        # ← must NOT be summed
        "PRECIO PROVEEDOR X CAN": 45000,
    },
    {
        "ID": 1001, "NÚMERO GUIA": "SGT-987",
        "NOMBRE CLIENTE": "María Pérez", "TELÉFONO": "+573001234567",
        "CIUDAD DESTINO": "Medellín", "DEPARTAMENTO DESTINO": "Antioquia",
        "DIRECCION": "Cra 50 #10-20", "NOTAS": "",
        "TRANSPORTADORA": "SERVIENTREGA", "ESTATUS": "RECLAME EN OFICINA",
        "TIPO DE ENVIO": "CON RECAUDO", "VENDEDOR": "V1", "TIENDA": "Litper",
        "FECHA": "2026-02-01", "FECHA GUIA GENERADA": "2026-02-02",
        "NOVEDAD": "",
        "PRODUCTO": "Protector Antifluido", "VARIACION": "Lila/Semi",
        "SKU": "PA-LS", "PRODUCTO ID": 111, "VARIACION ID": 1112,
        "CANTIDAD": 1,
        "TOTAL DE LA ORDEN": 150000,
        "PRECIO PROVEEDOR": 45000,
        "PRECIO PROVEEDOR X CAN": 45000,
    },
    {
        "ID": 1001, "NÚMERO GUIA": "SGT-987",
        "NOMBRE CLIENTE": "María Pérez", "TELÉFONO": "+573001234567",
        "CIUDAD DESTINO": "Medellín", "DEPARTAMENTO DESTINO": "Antioquia",
        "DIRECCION": "Cra 50 #10-20", "NOTAS": "",
        "TRANSPORTADORA": "SERVIENTREGA", "ESTATUS": "RECLAME EN OFICINA",
        "TIPO DE ENVIO": "CON RECAUDO", "VENDEDOR": "V1", "TIENDA": "Litper",
        "FECHA": "2026-02-01", "FECHA GUIA GENERADA": "2026-02-02",
        "NOVEDAD": "",
        "PRODUCTO": "Bono Regalo", "VARIACION": "20k",
        "SKU": "BR-20", "PRODUCTO ID": 222, "VARIACION ID": 2221,
        "CANTIDAD": 1,
        "TOTAL DE LA ORDEN": 150000,
        "PRECIO PROVEEDOR": 5000,
        "PRECIO PROVEEDOR X CAN": 5000,
    },
    # Single-product order (control)
    {
        "ID": 2002, "NÚMERO GUIA": "IR-555",
        "NOMBRE CLIENTE": "Juan Ríos", "TELÉFONO": "+573109999999",
        "CIUDAD DESTINO": "Bogotá", "DEPARTAMENTO DESTINO": "Bogotá",
        "DIRECCION": "Calle 100 #10-10", "NOTAS": "",
        "TRANSPORTADORA": "INTERRAPIDISIMO", "ESTATUS": "RECLAME EN OFICINA",
        "TIPO DE ENVIO": "CON RECAUDO", "VENDEDOR": "V2", "TIENDA": "Litper",
        "FECHA": "2026-02-01", "FECHA GUIA GENERADA": "2026-02-02",
        "NOVEDAD": "",
        "PRODUCTO": "Botella Térmica", "VARIACION": "Negra/500ml",
        "SKU": "BT-N500", "PRODUCTO ID": 333, "VARIACION ID": 3331,
        "CANTIDAD": 1,
        "TOTAL DE LA ORDEN": 85000,
        "PRECIO PROVEEDOR": 30000,
        "PRECIO PROVEEDOR X CAN": 30000,
    },
])


def test_detect_column_map():
    m = detect_column_map(COMBO_ORDER_ROWS.columns)
    assert m["ID"] == "order_id"
    assert m["NÚMERO GUIA"] == "guia"
    assert m["TOTAL DE LA ORDEN"] == "total_order"
    assert m["PRODUCTO"] == "product"
    assert m["VARIACION"] == "variation"
    # These are mapped but must NEVER feed recaudo
    assert m["PRECIO PROVEEDOR"] == "supplier_price"


def test_carrier_normalization():
    assert normalize_carrier("SERVIENTREGA") == "servientrega"
    assert normalize_carrier("Interrapidisimo") == "interrapidisimo"
    assert normalize_carrier("ENVÍA") == "envia"
    assert normalize_carrier("TCC") == "tcc"
    assert normalize_carrier("") is None
    assert normalize_carrier(None) is None


def test_combo_consolidation_and_recaudo_rule():
    data = _xlsx_bytes(COMBO_ORDER_ROWS)
    r = parse_sheet(data, "reclamos.xlsx", "Reclamos")

    # 4 raw rows → 2 orders
    assert r.raw_row_count == 4
    assert r.consolidated_count == 2

    combo = next(e for e in r.consolidated if e["order_key"] == "1001")
    single = next(e for e in r.consolidated if e["order_key"] == "2002")

    # Combo: 3 items, is_combo True, recaudo taken ONCE (150,000 not 450,000)
    assert combo["is_combo"] is True
    assert combo["items_count"] == 3
    assert combo["total_amount"] == 150000
    assert "Protector Antifluido (Verde Menta/Doble)" in combo["products_display"]
    assert "Protector Antifluido (Lila/Semi)" in combo["products_display"]
    assert "Bono Regalo (20k)" in combo["products_display"]
    assert combo["products_display"].count("+") == 2
    assert combo["carrier_slug"] == "servientrega"
    assert combo["customer_name"] == "María Pérez"
    assert combo["tracking_number"] == "SGT-987"

    # Single: 1 item, not combo, recaudo 85,000
    assert single["is_combo"] is False
    assert single["items_count"] == 1
    assert single["total_amount"] == 85000
    assert single["carrier_slug"] == "interrapidisimo"

    # Global recaudo aggregate is 150k + 85k = 235k, NOT 3*150k + 85k = 535k
    assert r.total_recaudo == 235000
    # Naive summing would yield 535k — surfaced to the user as a warning
    assert r.total_recaudo_if_summed_naively == 535000

    # Warning must mention the multi-row consolidation
    joined = " | ".join(r.warnings)
    assert "múltiples filas" in joined or "combos" in joined


def test_group_by_guia_when_no_id():
    df = COMBO_ORDER_ROWS.drop(columns=["ID"])
    r = parse_sheet(_xlsx_bytes(df), "no_id.xlsx", "Reclamos")
    # Two guias
    assert r.consolidated_count == 2
    combo = next(e for e in r.consolidated if e["order_key"] == "SGT-987")
    assert combo["items_count"] == 3
    assert combo["total_amount"] == 150000


def test_csv_supported(tmp_path):
    csv_path = tmp_path / "d.csv"
    COMBO_ORDER_ROWS.to_csv(csv_path, index=False)
    r = parse_sheet(csv_path.read_bytes(), "d.csv", None)
    assert r.consolidated_count == 2
    assert r.total_recaudo == 235000
