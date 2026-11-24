"""Routes: /carriers/novedades — reference table of carrier statuses → action."""
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from db import get_db
from deps import get_org, require_api_key
from models import Novedad

router = APIRouter(prefix="/carriers/novedades", tags=["carriers"],
                   dependencies=[Depends(require_api_key)])


@router.get("", response_model=List[Novedad],
            summary="List carrier-status novedades (reference table).")
async def list_novedades(carrier: Optional[str] = None,
                        categoria: Optional[str] = None,
                        limit: int = Query(500, le=1000),
                        org: str = Depends(get_org)):
    q: dict = {"org_id": org}  # tabla de referencia del paquete instalado por el cliente
    if carrier:
        q["carrier"] = carrier
    if categoria:
        q["categoria"] = categoria
    docs = await get_db().carrier_novedades.find(q, {"_id": 0}) \
        .sort([("categoria", 1), ("carrier", 1)]).limit(limit).to_list(limit)
    return docs
