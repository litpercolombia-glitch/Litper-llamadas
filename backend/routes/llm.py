"""Routes: /llm — estado y prueba de proveedores de IA del CLIENTE actual."""
from fastapi import APIRouter, Depends, Request

from deps import require_api_key
from agent.router import PROVIDERS, provider_available, ping, _keys_for
from tenant import org_from_request

router = APIRouter(prefix="/llm", tags=["llm"], dependencies=[Depends(require_api_key)])


@router.get("/providers", summary="Proveedores de IA con su estado PARA ESTE CLIENTE.")
async def list_providers(request: Request):
    keys = await _keys_for(org_from_request(request))
    return {"providers": [{"name": n, "model": c["model"], "compat": c["compat"],
                           "configured": provider_available(n, keys)}
                          for n, c in PROVIDERS.items()]}


@router.post("/providers/{name}/ping", summary="Prueba real de 1 mensaje con la llave del cliente.")
async def ping_provider(name: str, request: Request):
    return await ping(name, org_from_request(request))
