"""Routes: /products — catalog of Litper products with promotion matching.

Promotions have `sku_pattern` matched against an order's SKUs / product name
so calls & WhatsApp render the pretty offer name (e.g. "Protector Antifluido
Premium + 2 Fundas") and price, not the technical SKU.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import get_db
from deps import require_api_key
from models import ProductCatalog, ProductIn, ProductUpdate, Promotion

router = APIRouter(prefix="/products", tags=["products"],
                   dependencies=[Depends(require_api_key)])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").upper()).strip()


def _promo_matches(pattern: str, haystack: str) -> bool:
    p = _norm(pattern)
    h = _norm(haystack)
    if not p or not h:
        return False
    # Multi-token AND matching (order-independent)
    tokens = [t for t in re.split(r"[\s,+/&|]+", p) if len(t) > 2]
    if tokens:
        return all(t in h for t in tokens)
    return p in h


@router.get("", response_model=list[ProductCatalog],
            summary="List catalog products.")
async def list_products():
    return await get_db().catalog_products.find({}, {"_id": 0}) \
        .sort("created_at", -1).to_list(500)


@router.post("", response_model=ProductCatalog, status_code=201,
             summary="Create a catalog product with optional promotions.")
async def create_product(p: ProductIn):
    doc = ProductCatalog(**p.model_dump())
    await get_db().catalog_products.insert_one(doc.model_dump())
    return doc


@router.get("/{product_id}", response_model=ProductCatalog)
async def get_product(product_id: str):
    doc = await get_db().catalog_products.find_one({"id": product_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Product not found")
    return doc


@router.patch("/{product_id}", response_model=ProductCatalog,
              summary="Update a product / its promotions.")
async def update_product(product_id: str, patch: ProductUpdate):
    db = get_db()
    doc = await db.catalog_products.find_one({"id": product_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Product not found")
    upd = {k: v for k, v in patch.model_dump().items() if v is not None}
    upd["updated_at"] = _iso()
    if "promotions" in upd:
        upd["promotions"] = [Promotion(**pr).model_dump() for pr in upd["promotions"]]
    await db.catalog_products.update_one({"id": product_id}, {"$set": upd})
    doc = await db.catalog_products.find_one({"id": product_id}, {"_id": 0})
    return doc


@router.delete("/{product_id}", summary="Delete a product.")
async def delete_product(product_id: str):
    r = await get_db().catalog_products.delete_one({"id": product_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Product not found")
    return {"ok": True}


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
class MatchIn(BaseModel):
    sku: Optional[str] = None
    product_name: Optional[str] = None
    items: list[dict] = []


@router.post("/match", summary="Find the promotion that best matches a given SKU / product name / items.")
async def match_promotion(payload: MatchIn):
    db = get_db()
    haystack_parts: list[str] = []
    if payload.sku:
        haystack_parts.append(payload.sku)
    if payload.product_name:
        haystack_parts.append(payload.product_name)
    for it in payload.items or []:
        for k in ("sku", "product", "variation"):
            v = it.get(k)
            if v:
                haystack_parts.append(str(v))
    haystack = " | ".join(haystack_parts)

    best_promo = None
    best_product = None
    async for prod in db.catalog_products.find({"activo": {"$ne": False}}, {"_id": 0}):
        for promo in prod.get("promotions") or []:
            if not promo.get("activa", True):
                continue
            if _promo_matches(promo["sku_pattern"], haystack):
                # Prefer longer/more-specific pattern
                if best_promo is None or len(_norm(promo["sku_pattern"])) > \
                        len(_norm(best_promo["sku_pattern"])):
                    best_promo = promo
                    best_product = prod
    return {
        "matched": bool(best_promo),
        "promotion": best_promo,
        "product":   {"id": best_product["id"], "nombre": best_product["nombre"]}
                     if best_product else None,
        "haystack":  haystack,
    }
