"""Route: /carriers"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from db import get_db
from deps import require_api_key
from models import Carrier
from cadence import days_left as _days_left
from data import semaphore_for

router = APIRouter(prefix="/carriers", tags=["carriers"],
                   dependencies=[Depends(require_api_key)])


@router.get("", response_model=List[Carrier],
            summary="List all carriers with their office-claim rules.")
async def list_carriers():
    docs = await get_db().carriers.find({}, {"_id": 0}).to_list(200)
    return docs


@router.get("/{slug}", response_model=Carrier,
            summary="Get one carrier by slug.")
async def get_carrier(slug: str):
    doc = await get_db().carriers.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Carrier not found: {slug}")
    return doc


@router.get("/{slug}/office-status",
            summary="Compute the office-claim semaphore for a given arrival date + carrier.")
async def office_status(slug: str, office_arrival_date: str):
    doc = await get_db().carriers.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Carrier not found: {slug}")
    dl = _days_left(office_arrival_date, doc.get("office_claim_max_days"))
    return {"carrier": doc["name"], "slug": slug,
            "office_claim_max_days": doc.get("office_claim_max_days"),
            "days_left": dl,
            "semaphore": semaphore_for(doc.get("office_claim_max_days"), dl)}
