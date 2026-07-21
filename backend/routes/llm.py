"""Routes: /llm — provider status + ping for the Copilot brain."""
from fastapi import APIRouter, Depends

from deps import require_api_key
from agent.router import PROVIDERS, provider_available, ping

router = APIRouter(prefix="/llm", tags=["llm"], dependencies=[Depends(require_api_key)])


@router.get("/providers", summary="List LLM providers with configured/available status.")
async def list_providers():
    out = []
    for name, cfg in PROVIDERS.items():
        out.append({
            "name": name,
            "model": cfg["model"],
            "compat": cfg["compat"],
            "configured": provider_available(name),
        })
    return {"providers": out}


@router.post("/providers/{name}/ping", summary="Send a tiny ping to a provider.")
async def ping_provider(name: str):
    return await ping(name)
