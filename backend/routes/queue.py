"""Routes: /queue — the office-claim call queue with semaphore + days_left."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from db import get_db
from deps import require_api_key
from models import QueueItemPublic
from cadence import days_left
from data import semaphore_for

router = APIRouter(prefix="/queue", tags=["queue"],
                   dependencies=[Depends(require_api_key)])


async def _enrich(item: dict) -> dict:
    db = get_db()
    order = await db.orders.find_one({"id": item["order_id"]},
                                     {"_id": 0, "customer_name": 1, "customer_phone": 1,
                                      "address": 1, "city": 1, "total_amount": 1,
                                      "currency": 1, "tracking_number": 1})
    carrier = await db.carriers.find_one({"slug": item["carrier_slug"]},
                                         {"_id": 0, "name": 1, "office_claim_max_days": 1})
    dl = days_left(item["office_arrival_date"], item.get("office_claim_max_days"))
    semaphore = semaphore_for(item.get("office_claim_max_days"), dl)
    return {**item, "days_left": dl, "semaphore": semaphore,
            "customer_name": (order or {}).get("customer_name"),
            "customer_phone": (order or {}).get("customer_phone"),
            "carrier_name": (carrier or {}).get("name"),
            "address": (order or {}).get("address"),
            "city": (order or {}).get("city"),
            "total_amount": (order or {}).get("total_amount"),
            "currency": (order or {}).get("currency"),
            "tracking_number": (order or {}).get("tracking_number")}


@router.get("", response_model=List[QueueItemPublic],
            summary="List queue items with semaphore + days_left.")
async def list_queue(status: Optional[str] = None,
                     semaphore: Optional[str] = None,
                     carrier_slug: Optional[str] = None,
                     limit: int = Query(200, le=500)):
    q = {}
    if status:
        q["status"] = status
    if carrier_slug:
        q["carrier_slug"] = carrier_slug
    docs = await get_db().call_queue.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    enriched = [await _enrich(d) for d in docs]
    if semaphore:
        enriched = [e for e in enriched if e["semaphore"] == semaphore]
    return enriched


@router.get("/{queue_id}", response_model=QueueItemPublic,
            summary="Get a single queue item.")
async def get_queue_item(queue_id: str):
    doc = await get_db().call_queue.find_one({"id": queue_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Queue item not found")
    return await _enrich(doc)
