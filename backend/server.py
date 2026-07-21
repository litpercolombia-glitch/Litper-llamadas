"""Litper Connect Hub — FastAPI entry-point.

Public REST API for a COD e-commerce call-center orchestrator (LATAM).
Every business endpoint is protected by X-API-Key. OpenAPI at /docs & /redoc.
"""
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Import after loading .env so os.environ is populated
from db import get_db, close as close_db  # noqa: E402
from data import CARRIERS_SEED  # noqa: E402
import scheduler  # noqa: E402

from routes.health import router as health_router  # noqa: E402
from routes.carriers import router as carriers_router  # noqa: E402
from routes.orders import router as orders_router  # noqa: E402
from routes.queue import router as queue_router  # noqa: E402
from routes.cadence import router as cadence_router  # noqa: E402
from routes.whatsapp import router as whatsapp_router  # noqa: E402
from routes.tasks import router as tasks_router  # noqa: E402
from routes.metrics import router as metrics_router  # noqa: E402
from routes.webhooks import router as webhooks_router  # noqa: E402
from routes.translate import router as translate_router  # noqa: E402
from routes.connectors import router as connectors_router  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("litper.main")


async def _ensure_seed():
    """Upsert carriers + connectors on boot (idempotent)."""
    db = get_db()
    for c in CARRIERS_SEED:
        await db.carriers.update_one({"slug": c["slug"]}, {"$set": c}, upsert=True)
    for c in [("chatea_pro", "Chatea Pro (WhatsApp)"),
              ("dropi", "Dropi (Fulfillment)"),
              ("whatsapp_business", "WhatsApp Business (Meta Cloud)"),
              ("supabase", "Supabase Postgres")]:
        await db.integration_connectors.update_one(
            {"key": c[0]},
            {"$setOnInsert": {"key": c[0], "name": c[1], "status": "unconfigured",
                              "metadata": {}}},
            upsert=True,
        )
    # Ensure indexes
    await db.orders.create_index("id", unique=True)
    await db.orders.create_index("external_ref")
    await db.call_queue.create_index("id", unique=True)
    await db.call_queue.create_index("order_id")
    await db.call_schedules.create_index("queue_id", unique=True)
    await db.customer_tasks.create_index("id", unique=True)
    await db.message_log.create_index("created_at")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_seed()
    scheduler.start()
    log.info("Litper Connect Hub ready.")
    try:
        yield
    finally:
        scheduler.stop()
        await close_db()


app = FastAPI(
    title="Litper Connect Hub API",
    description=(
        "Integration hub + public API for COD e-commerce call-center operations "
        "in LATAM. Orchestrates AI phone calls (VAPI) and WhatsApp (Chatea Pro) to "
        "confirm COD orders sitting at carrier offices before they get returned.\n\n"
        "Auth: every business endpoint requires header `X-API-Key: <PUBLIC_API_KEY>`.\n"
        "Webhooks (/api/webhooks/*) are unauthenticated by design."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routes under /api
from fastapi import APIRouter  # noqa: E402
api = APIRouter(prefix="/api")

api.include_router(health_router)
api.include_router(carriers_router)
api.include_router(orders_router)
api.include_router(queue_router)
api.include_router(cadence_router)
api.include_router(whatsapp_router)
api.include_router(tasks_router)
api.include_router(metrics_router)
api.include_router(webhooks_router)
api.include_router(translate_router)
api.include_router(connectors_router)


@api.get("/", tags=["health"], summary="Root health.")
async def api_root():
    return {"name": "Litper Connect Hub", "version": "1.0.0",
            "docs": "/docs", "redoc": "/redoc"}


app.include_router(api)
