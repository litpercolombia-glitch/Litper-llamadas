"""Routes: /orders — import and read COD orders."""
from datetime import datetime, timezone, date
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from db import get_db
from deps import require_api_key
from models import Order, OrderIn, OrderBulkIn, QueueItem
from supabase_sync import upsert as supabase_upsert

router = APIRouter(prefix="/orders", tags=["orders"],
                   dependencies=[Depends(require_api_key)])


def _today_iso() -> str:
    return date.today().isoformat()


async def _create_one(order_in: OrderIn) -> Order:
    db = get_db()
    carrier = await db.carriers.find_one({"slug": order_in.carrier_slug}, {"_id": 0})
    if not carrier:
        raise HTTPException(400, f"Unknown carrier_slug: {order_in.carrier_slug}")

    order = Order(**order_in.model_dump(), status="in_queue")
    await db.orders.insert_one(order.model_dump())

    arrival = order_in.office_arrival_date or _today_iso()
    q = QueueItem(
        order_id=order.id,
        carrier_slug=order.carrier_slug,
        office_arrival_date=arrival,
        office_claim_max_days=carrier.get("office_claim_max_days"),
        country=order.country,
    )
    await db.call_queue.insert_one(q.model_dump())

    # Fire-and-forget mirror to Supabase.
    await supabase_upsert("orders", {**order.model_dump(),
                                     "org_id": None,
                                     "external_id": order.external_ref})
    return order


@router.post("", response_model=Order, status_code=201,
             summary="Create a single order and auto-enqueue it into the call queue.")
async def create_order(order_in: OrderIn):
    return await _create_one(order_in)


@router.post("/bulk", response_model=List[Order],
             summary="Bulk-create up to 500 orders.")
async def create_bulk(payload: OrderBulkIn):
    if len(payload.orders) > 500:
        raise HTTPException(400, "Max 500 orders per bulk call.")
    return [await _create_one(o) for o in payload.orders]


@router.get("", response_model=List[Order],
            summary="List orders (paginated).")
async def list_orders(skip: int = 0, limit: int = Query(50, le=200),
                      status: Optional[str] = None,
                      carrier_slug: Optional[str] = None):
    q = {}
    if status:
        q["status"] = status
    if carrier_slug:
        q["carrier_slug"] = carrier_slug
    docs = await get_db().orders.find(q, {"_id": 0}) \
        .sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return docs


@router.get("/{order_id}", response_model=Order,
            summary="Get a single order.")
async def get_order(order_id: str):
    doc = await get_db().orders.find_one({"id": order_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Order not found")
    return doc


@router.get("/{order_id}/prompt-vars",
            summary="Return the variables used to render Sofía's outbound call script "
                    "for this order (combo-aware + promo-matched).")
async def order_prompt_vars(order_id: str):
    db = get_db()
    doc = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Order not found")
    items = doc.get("items") or []
    references = ", ".join(
        [i.get("sku") for i in items if i.get("sku")]) or ""
    product_name = (doc.get("products_display")
                    or (items[0].get("product", "") if items else "")
                    or "tu pedido")

    # Promo matching: combine every sku/product/variation into a haystack and
    # find the best (most specific) active promotion.
    from routes.products import _promo_matches, _norm
    haystack_parts: list[str] = []
    for it in items:
        for k in ("sku", "product", "variation"):
            v = it.get(k)
            if v:
                haystack_parts.append(str(v))
    haystack = " | ".join(haystack_parts)

    best_promo = None
    async for prod in db.catalog_products.find({"activo": {"$ne": False}}, {"_id": 0}):
        for promo in prod.get("promotions") or []:
            if not promo.get("activa", True):
                continue
            if _promo_matches(promo["sku_pattern"], haystack):
                if best_promo is None or len(_norm(promo["sku_pattern"])) > \
                        len(_norm(best_promo["sku_pattern"])):
                    best_promo = promo

    promo_name = (best_promo or {}).get("nombre_comercial", "") if best_promo else ""
    promo_price = (best_promo or {}).get("precio_promo", 0) if best_promo else 0
    promo_bonuses = ", ".join((best_promo or {}).get("bonos", []) or []) if best_promo else ""

    return {
        "customer_name":  doc.get("customer_name", ""),
        "customer_phone": doc.get("customer_phone", ""),
        "tracking":       doc.get("tracking_number", ""),
        "carrier":        doc.get("carrier_slug", ""),
        "city":           doc.get("city", ""),
        "address":        doc.get("address", ""),
        "product_name":   product_name,
        "items_count":    len(items),
        "references":     references,
        "is_combo":       doc.get("is_combo", False),
        "total_amount":   doc.get("total_amount", 0),
        "currency":       doc.get("currency", "COP"),
        # Promotion match (empty strings/0 if no promo matched)
        "promo_name":     promo_name,
        "promo_price":    promo_price,
        "promo_bonuses":  promo_bonuses,
        "promo_matched":  bool(best_promo),
    }
