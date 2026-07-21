"""Routes: /health — liveness probe (unauthenticated)."""
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe (no auth).")
async def health():
    return {"ok": True, "service": "litper-connect-hub",
            "ts": datetime.now(timezone.utc).isoformat()}
