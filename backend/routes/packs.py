"""Routes: /packs — paquetes opcionales de datos (ver backend/packs.py)."""
from fastapi import APIRouter, Depends, HTTPException

from deps import get_org, require_api_key
from packs import PACKS, install_pack, installed_packs

router = APIRouter(prefix="/packs", tags=["packs"],
                   dependencies=[Depends(require_api_key)])


@router.get("", summary="Paquetes disponibles y cuáles tiene instalados el cliente actual.")
async def list_packs(org: str = Depends(get_org)):
    mine = set(await installed_packs(org))
    return {"packs": [{"key": p["key"], "name": p["name"],
                       "description": p["description"], "installed": k in mine}
                      for k, p in PACKS.items()]}


@router.post("/{pack}/install",
             summary="Instala un paquete SOLO en el cliente actual (idempotente).")
async def install(pack: str, org: str = Depends(get_org)):
    if pack not in PACKS:
        raise HTTPException(404, f"Paquete desconocido: {pack}")
    return await install_pack(org, pack)
