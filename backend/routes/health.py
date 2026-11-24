"""Routes: /health — liveness probe (unauthenticated).

También monta Zynex Call (/zcall) y el conector de Claude (/mcp/{token}) y,
en el primer chequeo de salud tras arrancar, deja listos sus índices y su
tarea interna (cada 10 min, solo clientes con «auto_recoger»).
"""
from fastapi import APIRouter
from datetime import datetime, timezone

from routes.zynex_call import router as zynex_call_router, instalar as zynex_instalar
from routes.zynex_mcp import router as zynex_mcp_router

router = APIRouter(tags=["health"])
router.include_router(zynex_call_router)
router.include_router(zynex_mcp_router)


@router.get("/health", summary="Liveness probe (no auth).")
async def health():
    await zynex_instalar()
    return {"ok": True, "service": "zynex-os",
            "ts": datetime.now(timezone.utc).isoformat()}
