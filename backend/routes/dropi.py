"""
Routes: /dropi — smart Excel/CSV importer for Dropi "Reclamos en Oficina"
exports. Handles the multi-row-per-order pattern (combos/promos) correctly.

Flow:
  1. POST /dropi/preview   (multipart file)  → sheets, column map, consolidated preview
  2. POST /dropi/import    (JSON: preview_id + list of order_keys to import)

The preview is cached in Mongo (`dropi_previews` collection) so the user can
edit carrier mappings before committing without re-uploading the file.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, date, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from pydantic import BaseModel

from db import get_db
from deps import require_api_key
from dropi_import import (
    parse_sheet,
    read_workbook_info,
    normalize_carrier,
)
from models import Order, OrderIn, OrderItem, QueueItem

router = APIRouter(prefix="/dropi", tags=["dropi"],
                   dependencies=[Depends(require_api_key)])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------
class DropiImportIn(BaseModel):
    preview_id: str
    order_keys: Optional[list[str]] = None  # None → import all
    carrier_overrides: dict[str, str] = {}  # order_key -> carrier_slug
    default_carrier_slug: Optional[str] = None
    country: str = "CO"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/sheets", summary="List sheet names in an uploaded workbook (no parse).")
async def dropi_sheets(file: UploadFile = File(...)):
    data = await file.read()
    try:
        info = read_workbook_info(data, file.filename or "")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"No se pudo leer el archivo: {e}")
    return {"filename": file.filename, **info}


@router.post("/preview",
             summary="Parse a Dropi Excel/CSV export, group rows per order (combo-safe), "
                     "and return a consolidated preview + heuristic warnings.")
async def dropi_preview(file: UploadFile = File(...),
                        sheet: Optional[str] = Form(None)):
    data = await file.read()
    try:
        result = parse_sheet(data, file.filename or "", sheet)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"No se pudo analizar el archivo: {e}")

    preview_id = str(uuid.uuid4())
    doc = {
        "id":                 preview_id,
        "filename":           file.filename or "",
        "sheet_used":         result.sheet_used,
        "created_at":         _now_iso(),
        "column_map":         result.column_map,
        "unmatched_columns":  result.unmatched_columns,
        "raw_row_count":      result.raw_row_count,
        "consolidated_count": result.consolidated_count,
        "multi_row_orders":   result.multi_row_orders,
        "combo_orders":       result.combo_orders,
        "total_recaudo":      result.total_recaudo,
        "naive_sum_recaudo":  result.total_recaudo_if_summed_naively,
        "warnings":           result.warnings,
        "consolidated":       result.consolidated,
    }
    await get_db().dropi_previews.insert_one(doc)
    # Strip the mongo _id before returning
    doc.pop("_id", None)
    return doc


@router.get("/preview/{preview_id}",
            summary="Fetch a stored preview (for re-review before import).")
async def dropi_preview_get(preview_id: str):
    doc = await get_db().dropi_previews.find_one({"id": preview_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Preview no encontrado.")
    return doc


@router.post("/import",
             summary="Commit selected orders from a preview into the DB + queue. "
                     "Deduplicates by external_ref/tracking_number.")
async def dropi_import(payload: DropiImportIn):
    db = get_db()
    preview = await db.dropi_previews.find_one({"id": payload.preview_id}, {"_id": 0})
    if not preview:
        raise HTTPException(404, "Preview no encontrado. Sube el archivo de nuevo.")

    entries = preview.get("consolidated", [])
    if payload.order_keys is not None:
        keyset = set(payload.order_keys)
        entries = [e for e in entries if e.get("order_key") in keyset]
    if not entries:
        raise HTTPException(400, "No hay órdenes seleccionadas para importar.")

    # Load carriers slug set for validation
    carriers = await db.carriers.find({}, {"_id": 0, "slug": 1,
                                            "office_claim_max_days": 1}).to_list(500)
    carrier_by_slug = {c["slug"]: c for c in carriers}

    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for e in entries:
        key = e.get("order_key")
        slug = payload.carrier_overrides.get(key) or e.get("carrier_slug") \
            or payload.default_carrier_slug
        if not slug or slug not in carrier_by_slug:
            errors.append({"order_key": key,
                           "error": f"carrier no válido ({e.get('carrier_raw')}). "
                                    f"Asígnalo manualmente."})
            continue

        # Dedup: match by external_ref OR tracking_number
        dedup_q = {"$or": []}
        if e.get("external_ref"):
            dedup_q["$or"].append({"external_ref": e["external_ref"]})
        if e.get("tracking_number"):
            dedup_q["$or"].append({"tracking_number": e["tracking_number"]})
        existing = None
        if dedup_q["$or"]:
            existing = await db.orders.find_one(dedup_q, {"_id": 0, "id": 1})
        if existing:
            skipped.append({"order_key": key, "order_id": existing["id"],
                            "reason": "ya existe"})
            continue

        items = [OrderItem(**i) for i in (e.get("items") or [])]

        try:
            order_in = OrderIn(
                external_ref=e.get("external_ref"),
                customer_name=e.get("customer_name") or "Sin nombre",
                customer_phone=(e.get("customer_phone") or "").strip() or "+000000000",
                address=e.get("address") or "",
                city=e.get("city") or "",
                country=payload.country,  # type: ignore[arg-type]
                total_amount=float(e.get("total_amount") or 0),
                currency=e.get("currency") or "COP",
                carrier_slug=slug,
                tracking_number=e.get("tracking_number"),
                products=[],
                items=items,
                items_count=len(items),
                is_combo=bool(e.get("is_combo")),
                products_display=e.get("products_display") or "",
                office_arrival_date=e.get("office_arrival_date") or None,
                metadata={
                    "source":       "dropi_import",
                    "preview_id":   payload.preview_id,
                    "carrier_raw":  e.get("carrier_raw"),
                    "status_raw":   e.get("status_raw"),
                    "novedad":      e.get("novedad"),
                    "seller":       e.get("seller"),
                    "store":        e.get("store"),
                    "department":   e.get("department"),
                    "payment_type": e.get("payment_type"),
                    "order_date":   e.get("order_date"),
                },
            )
        except Exception as ex:  # noqa: BLE001
            errors.append({"order_key": key, "error": f"validación: {ex}"})
            continue

        order = Order(**order_in.model_dump(), status="in_queue")
        await db.orders.insert_one(order.model_dump())

        arrival = order_in.office_arrival_date or _today()
        q = QueueItem(
            order_id=order.id,
            carrier_slug=order.carrier_slug,
            office_arrival_date=arrival,
            office_claim_max_days=carrier_by_slug[slug].get("office_claim_max_days"),
            country=order.country,
        )
        await db.call_queue.insert_one(q.model_dump())
        imported.append({"order_key": key, "order_id": order.id,
                         "tracking": order.tracking_number,
                         "recaudo": order.total_amount,
                         "is_combo": order.is_combo,
                         "products_display": order.products_display})

    return {
        "ok": True,
        "preview_id": payload.preview_id,
        "imported_count": len(imported),
        "skipped_count":  len(skipped),
        "error_count":    len(errors),
        "imported": imported,
        "skipped":  skipped,
        "errors":   errors,
    }
