"""
Dropi Excel importer for Litper Connect Hub.

Real Dropi "Reclamos en Oficina" exports use a wide format (~53 columns) where
ONE ORDER = MULTIPLE ROWS: each promo/combo/variation is emitted as its own
row that repeats the customer + tracking + total on every line.

Naive row-by-row import triples the queue count and inflates the recaudo.
This module implements the correct rules:

    1. Group rows by `ID` (order id) or, if absent, by `NÚMERO GUIA`.
    2. RECAUDO ("total to pay by the customer") = column `TOTAL DE LA ORDEN`
       taken ONCE per group. NEVER sum it across rows. Never use PRECIO
       PROVEEDOR — that's the supplier cost.
    3. For each row of the group, build an item = {product, variation, sku,
       product_id, variation_id, qty}. is_combo = len(items) > 1.
    4. products_display = "Prod A (Var A) + Prod B (Var B)".
    5. Fuzzy detect all Dropi column names (spanish accents & spacing vary).
    6. Normalize carrier name → carrier slug (matches /carriers seed).
    7. Return a preview (1 row per order) BEFORE writing to DB, plus a
       heuristic warning when we detect the multi-row/combo pattern.

Public API:
    read_workbook(bytes, filename) -> {sheets: [name, ...]}
    parse_sheet(bytes, filename, sheet_name) -> ParseResult
    ParseResult.consolidated -> list[dict]   (1 per order, ready for import)
    ParseResult.warnings     -> list[str]
    ParseResult.column_map   -> dict          (raw → canonical)
"""
from __future__ import annotations

import io
import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Column mapping — canonical name -> list of Dropi header aliases we accept.
# Comparison is done on a *normalized* (accent-stripped, upper, no space) form.
# ---------------------------------------------------------------------------
COLUMN_ALIASES: dict[str, list[str]] = {
    "order_id":         ["ID", "IDORDEN", "IDPEDIDO", "ORDERID", "ORDER_ID"],
    "guia":             ["NUMEROGUIA", "NUMERO GUIA", "NRO GUIA", "GUIA",
                         "TRACKING", "TRACKINGNUMBER", "TRACKING_NUMBER"],
    "customer_name":    ["NOMBRECLIENTE", "NOMBRE CLIENTE", "CLIENTE",
                         "NOMBRE", "CUSTOMERNAME"],
    "phone":            ["TELEFONO", "TELÉFONO", "CELULAR", "MOVIL", "MÓVIL",
                         "TEL", "PHONE"],
    "city":             ["CIUDADDESTINO", "CIUDAD DESTINO", "CIUDAD", "CITY"],
    "department":       ["DEPARTAMENTODESTINO", "DEPARTAMENTO DESTINO",
                         "DEPARTAMENTO", "DEPTO", "STATE"],
    "address":          ["DIRECCION", "DIRECCIÓN", "ADDRESS"],
    "notes":            ["NOTAS", "NOTA", "OBSERVACIONES", "OBS"],
    "carrier":          ["TRANSPORTADORA", "CARRIER", "TRANSPORTISTA"],
    "status":           ["ESTATUS", "ESTADO", "STATUS"],
    "payment_type":     ["TIPODEENVIO", "TIPO DE ENVIO", "TIPO ENVIO",
                         "TIPO_ENVIO", "SHIPPINGTYPE"],
    "seller":           ["VENDEDOR", "SELLER"],
    "store":            ["TIENDA", "STORE"],
    "order_date":       ["FECHA", "FECHAORDEN", "FECHA ORDEN", "ORDERDATE"],
    "guide_date":       ["FECHAGUIAGENERADA", "FECHA GUIA GENERADA",
                         "FECHA GUIA", "GUIDEDATE"],
    "novedad":          ["NOVEDAD", "ULTIMANOVEDAD", "ULTIMA NOVEDAD"],
    # ---- recaudo (order total the client pays) ----
    "total_order":      ["TOTALDELAORDEN", "TOTAL DE LA ORDEN", "TOTAL ORDEN",
                         "TOTAL", "RECAUDO", "VALORTOTAL", "VALOR TOTAL",
                         "VALORACOBRAR", "VALOR A COBRAR"],
    # ---- product / combo line fields ----
    "product":          ["PRODUCTO", "NOMBREPRODUCTO", "NOMBRE PRODUCTO",
                         "PRODUCT", "PRODUCTNAME"],
    "variation":        ["VARIACION", "VARIACIÓN", "VARIANT", "VARIACION1"],
    "product_id":       ["PRODUCTOID", "PRODUCTO ID", "PRODUCT_ID"],
    "variation_id":     ["VARIACIONID", "VARIACION ID", "VARIACIÓN ID",
                         "VARIATION_ID"],
    "sku":              ["SKU", "REFERENCIA", "REF"],
    "qty":              ["CANTIDAD", "CAN", "CANT", "QTY", "QUANTITY"],
    # ---- explicitly IGNORED for RECAUDO (they are supplier cost) ----
    # We map them so we can WARN the user if they try to use them.
    "supplier_price":       ["PRECIOPROVEEDOR", "PRECIO PROVEEDOR"],
    "supplier_price_x_can": ["PRECIOPROVEEDORXCAN", "PRECIO PROVEEDOR X CAN",
                             "PRECIO PROVEEDOR XCAN"],
}


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", "", s).upper()
    return s


def _build_reverse_alias() -> dict[str, str]:
    rev: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            rev[_norm(a)] = canonical
    return rev


_REV_ALIAS = _build_reverse_alias()


def detect_column_map(columns: Iterable[str]) -> dict[str, str]:
    """Return raw_header -> canonical_name mapping (only for matched columns)."""
    mapping: dict[str, str] = {}
    for raw in columns:
        canonical = _REV_ALIAS.get(_norm(raw))
        if canonical:
            mapping[str(raw)] = canonical
    return mapping


# ---------------------------------------------------------------------------
# Carrier normalization (Dropi label -> /carriers slug).
# ---------------------------------------------------------------------------
CARRIER_SLUG_MAP: dict[str, str] = {
    "INTERRAPIDISIMO": "interrapidisimo",
    "INTER RAPIDISIMO": "interrapidisimo",
    "ENVIA": "envia",
    "ENVÍA": "envia",
    "COORDINADORA": "coordinadora",
    "SERVIENTREGA": "servientrega",
    "TCC": "tcc",
    "DOMINA": "domina",
    "WIILOG": "wiilog",
    "JAMV": "jamv-drive",
    "JAMVDRIVE": "jamv-drive",
    "JAMV DRIVE": "jamv-drive",
    "VELOCES": "veloces",
    "99MINUTOS": "99-minutos",
    "99 MINUTOS": "99-minutos",
    "FLEETEX": "fleetex",
    "DEROCHA": "de-rocha",
    "DE ROCHA": "de-rocha",
}


def normalize_carrier(raw: Any) -> Optional[str]:
    if not raw or (isinstance(raw, float) and math.isnan(raw)):
        return None
    key = _norm(str(raw))
    if key in CARRIER_SLUG_MAP:
        return CARRIER_SLUG_MAP[key]
    # fuzzy: substring
    for k, slug in CARRIER_SLUG_MAP.items():
        if k in key or key in k:
            return slug
    return None


# ---------------------------------------------------------------------------
# Value coercion helpers
# ---------------------------------------------------------------------------
def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()


_MONEY_RE = re.compile(r"[^\d,.\-]")


def _to_number(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return 0.0
        return float(v)
    s = _MONEY_RE.sub("", str(v))
    if not s:
        return 0.0
    # Handle Colombian numeric formats: "1.234.567,00" or "1,234,567.00"
    if "," in s and "." in s:
        # If ',' is after last '.', treat ',' as decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Only comma present -> comma is decimal only if there's a lone group of 2 digits after
        if re.match(r"^-?\d+,\d{1,2}$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _to_int(v: Any, default: int = 1) -> int:
    try:
        n = int(_to_number(v))
        return n if n > 0 else default
    except Exception:
        return default


def _iso_date(v: Any) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, (pd.Timestamp,)):
        return v.date().isoformat()
    s = _clean_str(v)
    if not s:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M",
                "%d/%m/%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s  # let it through as-is


# ---------------------------------------------------------------------------
# Workbook helpers
# ---------------------------------------------------------------------------
def _sheet_names(data: bytes, filename: str) -> list[str]:
    fn = (filename or "").lower()
    if fn.endswith(".csv"):
        return ["CSV"]
    xl = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
    return list(xl.sheet_names)


def _read_sheet_df(data: bytes, filename: str, sheet: Optional[str]) -> pd.DataFrame:
    fn = (filename or "").lower()
    if fn.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(data))
    else:
        df = pd.read_excel(io.BytesIO(data), engine="openpyxl",
                           sheet_name=sheet if sheet else 0)
    # Make sure the header row is strings.
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ParseResult:
    sheets: list[str]
    sheet_used: str
    column_map: dict[str, str]  # raw -> canonical
    consolidated: list[dict[str, Any]]  # 1 dict per order (ready to import)
    raw_row_count: int
    consolidated_count: int
    multi_row_orders: int
    combo_orders: int
    total_recaudo: float
    total_recaudo_if_summed_naively: float  # for warning ratio
    warnings: list[str] = field(default_factory=list)
    unmatched_columns: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core parsing
# ---------------------------------------------------------------------------
def read_workbook_info(data: bytes, filename: str) -> dict[str, Any]:
    return {"sheets": _sheet_names(data, filename)}


def parse_sheet(data: bytes, filename: str,
                sheet_name: Optional[str] = None) -> ParseResult:
    df = _read_sheet_df(data, filename, sheet_name)
    df = df.fillna("")
    columns = list(df.columns)
    col_map = detect_column_map(columns)
    canonical_to_raw: dict[str, str] = {v: k for k, v in col_map.items()}

    raw_count = len(df)
    warnings: list[str] = []

    def col(canonical: str) -> Optional[str]:
        return canonical_to_raw.get(canonical)

    if not col("order_id") and not col("guia"):
        raise ValueError(
            "No se detectó columna de ID de orden (`ID`) ni de guía (`NÚMERO GUIA`). "
            "Este archivo no parece un export de Dropi.")

    if not col("total_order"):
        warnings.append(
            "No se encontró la columna `TOTAL DE LA ORDEN`. Se usará 0 como recaudo. "
            "NO se sumará `PRECIO PROVEEDOR` (eso es costo del proveedor, no recaudo).")

    # ---- Grouping -----------------------------------------------------------
    def _group_key_for_row(row: pd.Series) -> str:
        k = ""
        if col("order_id"):
            k = _clean_str(row[col("order_id")])
        if not k and col("guia"):
            k = _clean_str(row[col("guia")])
        return k

    groups: dict[str, list[pd.Series]] = {}
    order_key_col = col("order_id") or col("guia")
    for _, row in df.iterrows():
        key = _group_key_for_row(row)
        if not key:
            continue
        groups.setdefault(key, []).append(row)

    consolidated: list[dict[str, Any]] = []
    multi_row_orders = 0
    combo_orders = 0
    total_recaudo = 0.0
    naive_sum = 0.0

    for key, rows in groups.items():
        first = rows[0]

        def val(canonical: str) -> Any:
            c = col(canonical)
            return first[c] if c else ""

        items: list[dict[str, Any]] = []
        display_parts: list[str] = []
        for r in rows:
            product = _clean_str(r[col("product")]) if col("product") else ""
            variation = _clean_str(r[col("variation")]) if col("variation") else ""
            if not product and not variation:
                continue
            item = {
                "product":      product,
                "variation":    variation,
                "sku":          _clean_str(r[col("sku")]) if col("sku") else "",
                "product_id":   _clean_str(r[col("product_id")]) if col("product_id") else "",
                "variation_id": _clean_str(r[col("variation_id")]) if col("variation_id") else "",
                "qty":          _to_int(r[col("qty")], 1) if col("qty") else 1,
            }
            items.append(item)
            display_parts.append(
                f"{product} ({variation})" if variation else product)

        products_display = " + ".join(display_parts) if display_parts else ""
        is_combo = len(items) > 1
        if is_combo:
            combo_orders += 1
        if len(rows) > 1:
            multi_row_orders += 1

        # RECAUDO — take ONCE from the first row (Dropi repeats it on every row).
        recaudo_first = _to_number(val("total_order"))
        # Naive sum would be to add every row's total — we compute this only to
        # show the user how off the number would be.
        for r in rows:
            naive_sum += _to_number(r[col("total_order")]) if col("total_order") else 0.0
        total_recaudo += recaudo_first

        carrier_raw = _clean_str(val("carrier"))
        carrier_slug = normalize_carrier(carrier_raw)
        if not carrier_slug and carrier_raw:
            warnings.append(f"Carrier no reconocido: '{carrier_raw}' (orden {key}). "
                            f"Deberás asignarlo manualmente antes de importar.")

        address = _clean_str(val("address")) or _clean_str(val("notes"))

        entry = {
            "order_key":      key,
            "external_ref":   _clean_str(val("order_id")) or None,
            "tracking_number": _clean_str(val("guia")) or None,
            "customer_name":  _clean_str(val("customer_name")),
            "customer_phone": _clean_str(val("phone")),
            "city":           _clean_str(val("city")),
            "department":     _clean_str(val("department")),
            "address":        address,
            "carrier_raw":    carrier_raw,
            "carrier_slug":   carrier_slug,
            "status_raw":     _clean_str(val("status")),
            "payment_type":   _clean_str(val("payment_type")),
            "seller":         _clean_str(val("seller")),
            "store":          _clean_str(val("store")),
            "order_date":     _iso_date(val("order_date")),
            "office_arrival_date": _iso_date(val("guide_date")),
            "novedad":        _clean_str(val("novedad")),
            "total_amount":   recaudo_first,
            "currency":       "COP",
            "items":          items,
            "items_count":    len(items),
            "is_combo":       is_combo,
            "products_display": products_display,
            "row_count":      len(rows),
        }
        consolidated.append(entry)

    # ---- Warnings -----------------------------------------------------------
    if multi_row_orders > 0:
        warnings.insert(0,
            f"Se detectaron {multi_row_orders} órdenes con múltiples filas "
            f"(combos/promos). El importador las consolidó a UNA sola orden por "
            f"grupo. Si sumaras fila por fila el recaudo daría "
            f"${naive_sum:,.0f} en lugar del correcto ${total_recaudo:,.0f}."
        )

    # supplier price columns present but no total_order -> big red warning
    if not col("total_order") and (col("supplier_price") or col("supplier_price_x_can")):
        warnings.append(
            "Se encontraron columnas `PRECIO PROVEEDOR` pero no `TOTAL DE LA ORDEN`. "
            "NO se usará el precio del proveedor como recaudo — pide un export "
            "que incluya la columna TOTAL DE LA ORDEN.")

    unmatched = [c for c in columns if c not in col_map]

    return ParseResult(
        sheets=[sheet_name] if sheet_name else ["Sheet1"],
        sheet_used=sheet_name or "Sheet1",
        column_map=col_map,
        consolidated=consolidated,
        raw_row_count=raw_count,
        consolidated_count=len(consolidated),
        multi_row_orders=multi_row_orders,
        combo_orders=combo_orders,
        total_recaudo=total_recaudo,
        total_recaudo_if_summed_naively=naive_sum,
        warnings=warnings,
        unmatched_columns=unmatched,
    )
