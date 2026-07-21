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
from data import CARRIERS_SEED, NOVEDADES_SEED  # noqa: E402
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
from routes.voices import router as voices_router  # noqa: E402
from routes.numbers import router as numbers_router  # noqa: E402
from routes.novedades import router as novedades_router  # noqa: E402
from routes.copilot import router as copilot_router  # noqa: E402
from routes.skills import router as skills_router  # noqa: E402
from routes.files import router as files_router  # noqa: E402
from routes.dropi import router as dropi_router  # noqa: E402
from routes.products import router as products_router  # noqa: E402
from routes.prompts import router as prompts_router  # noqa: E402
from routes.vip import public_router as vip_public_router, admin_router as vip_admin_router  # noqa: E402
from routes.config import router as config_router  # noqa: E402
from routes.llm import router as llm_router  # noqa: E402

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
              ("supabase", "Supabase Postgres"),
              ("elevenlabs", "ElevenLabs (Voz IA)"),
              ("twilio", "Twilio (Caller ID)")]:
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
    await db.voice_profiles.create_index("id", unique=True)
    await db.connected_numbers.create_index("phone_number", unique=True)
    await db.carrier_novedades.create_index([("carrier", 1), ("estatus_carrier", 1)],
                                            unique=True)
    await db.chat_threads.create_index("id", unique=True)
    await db.chat_messages.create_index([("thread_id", 1), ("created_at", 1)])
    await db.copilot_skills.create_index("id", unique=True)
    await db.uploaded_files.create_index("id", unique=True)
    await db.catalog_products.create_index("id", unique=True)
    await db.vip_leads.create_index("id", unique=True)
    await db.vip_leads.create_index("whatsapp")
    await db.prompts.create_index("id", unique=True)
    await db.whatsapp_rules.create_index("id", unique=True)
    await db.org_credentials.create_index([("org_id", 1), ("provider", 1)], unique=True)
    await db.whatsapp_contacts.create_index("phone", unique=True)

    # Seed novedades (idempotent by carrier+estatus_carrier)
    for n in NOVEDADES_SEED:
        await db.carrier_novedades.update_one(
            {"carrier": n["carrier"], "estatus_carrier": n["estatus_carrier"]},
            {"$set": n},
            upsert=True,
        )

    # Seed copilot skills (idempotent by trigger)
    from data import SKILLS_SEED, VOICES_SEED
    for s in SKILLS_SEED:
        await db.copilot_skills.update_one(
            {"trigger": s["trigger"]},
            {"$setOnInsert": {**s, "is_seed": True}},
            upsert=True,
        )
    # Seed the 6 preferred ElevenLabs voices (idempotent by voice_id)
    for v in VOICES_SEED:
        await db.voice_profiles.update_one(
            {"elevenlabs_voice_id": v["elevenlabs_voice_id"]},
            {"$setOnInsert": v},
            upsert=True,
        )

    # Seed catalog products with promotions (idempotent by nombre)
    from data import PRODUCTS_SEED
    for p in PRODUCTS_SEED:
        await db.catalog_products.update_one(
            {"nombre": p["nombre"]},
            {"$setOnInsert": p},
            upsert=True,
        )

    # Seed the default Sofía global prompt (LIT-LOG-RO flow — 6-block ElevenLabs).
    # Force-overwrite if the existing doc is from a legacy structure so upgrades
    # roll out cleanly without a manual migration.
    from data import PROMPTS_SEED, WHATSAPP_RULES_SEED
    for pr in PROMPTS_SEED:
        existing = await db.prompts.find_one(
            {"name": pr["name"], "scope": pr["scope"], "country": pr.get("country")},
            {"_id": 0, "system_prompt": 1})
        needs_upgrade = (
            existing
            and (not (existing.get("system_prompt") or "").lstrip().startswith("# Personalidad")
                 or "impermeable" in (existing.get("system_prompt") or "").lower())
        )
        if existing and needs_upgrade:
            await db.prompts.update_one(
                {"name": pr["name"], "scope": pr["scope"], "country": pr.get("country")},
                {"$set": {"system_prompt": pr["system_prompt"],
                          "first_message": pr["first_message"],
                          "variables":     pr["variables"],
                          "updated_at":    pr["updated_at"]}})
        elif not existing:
            await db.prompts.insert_one(pr)
    for rule in WHATSAPP_RULES_SEED:
        await db.whatsapp_rules.update_one(
            {"rule_key": rule["rule_key"]},
            {"$setOnInsert": rule}, upsert=True,
        )


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
api.include_router(novedades_router)  # must be BEFORE carriers to avoid /{slug} match
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
api.include_router(voices_router)
api.include_router(numbers_router)
api.include_router(novedades_router)
api.include_router(copilot_router)
api.include_router(skills_router)
api.include_router(files_router)
api.include_router(dropi_router)
api.include_router(products_router)
api.include_router(prompts_router)
api.include_router(vip_public_router)
api.include_router(vip_admin_router)
api.include_router(config_router)
api.include_router(llm_router)


@api.get("/", tags=["health"], summary="Root health.")
async def api_root():
    return {"name": "Litper Connect Hub", "version": "1.0.0",
            "docs": "/docs", "redoc": "/redoc"}


app.include_router(api)
