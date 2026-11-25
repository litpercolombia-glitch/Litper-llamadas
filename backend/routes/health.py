"""Routes: /health — liveness probe (unauthenticated).

También monta Zynex Call (/zcall, /zcall/auto) y el conector de Claude (/mcp/{token}) y,
en el primer chequeo de salud tras arrancar, deja listos sus índices y su
tarea interna (cada 10 min, solo clientes con «auto_recoger»).
"""
from fastapi import APIRouter
from datetime import datetime, timezone

from routes.zynex_call import router as zynex_call_router, instalar as zynex_instalar
from routes.zynex_mcp import router as zynex_mcp_router
from routes.zynex_auto import router as zynex_auto_router
from routes.zynex_motor import router as zynex_motor_router, configurado as motor_configurado

router = APIRouter(tags=["health"])
router.include_router(zynex_call_router)
router.include_router(zynex_mcp_router)
router.include_router(zynex_auto_router)
router.include_router(zynex_motor_router)


@router.get("/health", summary="Liveness probe (no auth).")
async def health():
    await zynex_instalar()
    return {"ok": True, "service": "zynex-os", "motor_logistica": motor_configurado(),
            "ts": datetime.now(timezone.utc).isoformat()}
