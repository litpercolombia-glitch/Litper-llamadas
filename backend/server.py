"""Zynex OS — FastAPI entry-point.

API multi-cliente: cada dato de negocio pertenece a un org (ver tenant.py y
deps.get_org). Every business endpoint is protected (JWT de sesión o
X-API-Key). OpenAPI at /docs & /redoc.
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
from routes.auth import router as auth_router  # noqa: E402
from routes.agents import router as agents_router  # noqa: E402
from routes.llm import router as llm_router  # noqa: E402
from routes.feedback import router as feedback_router  # noqa: E402
from routes.custom_agents import router as custom_agents_router  # noqa: E402
from routes.calls import router as calls_router  # noqa: E402
from routes.agent_tools import router as agent_tools_router  # noqa: E402
from routes.org_profile import router as org_profile_router  # noqa: E402
from routes.packs import router as packs_router  # noqa: E402
from routes.mcp_servers import router as mcp_servers_router  # noqa: E402
from routes.kb import router as kb_router  # noqa: E402
from routes.automations import router as automations_router  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("zynex.main")


async def _index(coll, keys, **kw) -> None:
    """Crea un índice sin tumbar el arranque (p. ej. si ya existe otro con el
    mismo nombre/opciones distintas, o hay datos viejos que chocan)."""
    try:
        await coll.create_index(keys, **kw)
    except Exception as e:  # noqa: BLE001
        log.warning("índice %s %s no creado: %s", coll.name, keys, e)


async def _drop_index(coll, name: str) -> None:
    """Quita un índice único GLOBAL antiguo (si existe) para reemplazarlo por
    el compuesto con org_id. Tolerante: si no existe, no pasa nada."""
    try:
        await coll.drop_index(name)
        log.info("índice antiguo %s.%s eliminado", coll.name, name)
    except Exception:  # noqa: BLE001
        pass


# Colecciones con datos de cliente que se listan por fecha → (org_id, created_at).
_ORG_LISTED = ["orders", "call_queue", "call_schedules", "customer_tasks", "message_log",
               "voice_profiles", "connected_numbers", "uploaded_files", "catalog_products",
               "prompts", "whatsapp_rules", "vip_leads", "dropi_previews",
               "webhook_events", "copilot_skills", "feedback"]


async def _ensure_indexes():
    """Arranque: SOLO índices. No se siembra ningún dato de negocio — un cliente
    nuevo empieza vacío. Transportadoras, novedades, skills, voces, prompts de
    Sofía y reglas de WhatsApp son el paquete opcional "cod_colombia"
    (backend/packs.py · POST /api/packs/cod_colombia/install). El catálogo de
    conectores es estático (routes/connectors.py) y su estado es por cliente.
    """
    db = get_db()
    # --- Identificadores propios (UUID): únicos globales, no chocan entre clientes.
    for coll in ("orders", "call_queue", "customer_tasks", "voice_profiles",
                 "chat_threads", "copilot_skills", "uploaded_files",
                 "catalog_products", "vip_leads", "prompts", "whatsapp_rules",
                 "orgs", "custom_agents"):
        await _index(db[coll], "id", unique=True)
    await _index(db.call_schedules, "queue_id", unique=True)
    await _index(db.calls, "call_id", unique=True)
    await _index(db.users, "email", unique=True)
    await _index(db.org_credentials, [("org_id", 1), ("provider", 1)], unique=True)
    await _index(db.org_profiles, "org_id", unique=True)
    await _index(db.org_packs, [("org_id", 1), ("pack", 1)], unique=True)
    # Conectores MCP por cliente y acciones del asistente que esperan confirmación.
    await _index(db.mcp_servers, "id", unique=True)
    await _index(db.mcp_servers, [("org_id", 1), ("nombre", 1)], unique=True)
    await _index(db.pending_actions, "id", unique=True)
    await _index(db.pending_actions, [("org_id", 1), ("thread_id", 1), ("status", 1)])
    await _index(db.call_launches, [("org_id", 1), ("created_at", -1)])
    # TTL: Mongo borra sola una acción pendiente 24 h después de vencer
    # (`expires_dt` es fecha real; `expires_at` sigue siendo el ISO que lee la app).
    await _index(db.pending_actions, "expires_dt", expireAfterSeconds=24 * 3600)
    # Token de webhooks por cliente (webhook_tokens.py).
    await _index(db.org_webhook_tokens, "org_id", unique=True)
    await _index(db.org_webhook_tokens, "token", unique=True)
    await _index(db.custom_agents, "tool_token", unique=True, sparse=True)
    await _index(db.agent_call_results, [("org_id", 1), ("created_at", -1)])
    # Base de conocimiento (una por cliente) y automatizaciones.
    await _index(db.org_kb, "org_id", unique=True)
    await _index(db.automations, "id", unique=True)
    await _index(db.automations, [("org_id", 1), ("trigger.tipo", 1), ("activa", 1)])
    await _index(db.automation_runs, [("org_id", 1), ("created_at", -1)])
    await _index(db.automation_runs, [("org_id", 1), ("rule_id", 1), ("created_at", -1)])
    # Contadores atómicos (límite diario por regla, tope por destinatario, eventos
    # repetidos): el índice ÚNICO es lo que hace atómica la reserva. Se borran
    # solos 3 días después de su último uso.
    await _index(db.automation_counters, [("org_id", 1), ("key", 1), ("day", 1)], unique=True)
    await _index(db.automation_counters, "exp", expireAfterSeconds=3 * 24 * 3600)
    await _index(db.message_log, [("org_id", 1), ("phone_digits", 1), ("created_at", -1)], sparse=True)
    # Intentos fallidos de login/registro: Mongo los borra solos a los 15 min.
    await _index(db.auth_attempts, "at", expireAfterSeconds=15 * 60)
    await _index(db.auth_attempts, [("key", 1), ("at", -1)])

    # --- Únicos por DATO DE NEGOCIO: antes eran globales (dos clientes no podían
    # tener el mismo teléfono/estatus/clave). Ahora compuestos con org_id.
    await _drop_index(db.connected_numbers, "phone_number_1")
    await _index(db.connected_numbers,
                 [("org_id", 1), ("phone_number", 1), ("provider", 1)], unique=True)
    await _drop_index(db.whatsapp_contacts, "phone_1")
    await _index(db.whatsapp_contacts, [("org_id", 1), ("phone", 1)], unique=True)
    await _drop_index(db.rto_blacklist, "phone_1")
    await _index(db.rto_blacklist, [("org_id", 1), ("phone", 1)], unique=True)
    await _drop_index(db.carrier_novedades, "carrier_1_estatus_carrier_1")
    await _index(db.carrier_novedades,
                 [("org_id", 1), ("carrier", 1), ("estatus_carrier", 1)], unique=True)
    await _index(db.carriers, [("org_id", 1), ("slug", 1)], unique=True)
    await _drop_index(db.ceo_reports, "id_1")
    await _index(db.ceo_reports, [("org_id", 1), ("id", 1)], unique=True)
    await _drop_index(db.settings, "key_1")
    await _index(db.settings, [("org_id", 1), ("key", 1)], unique=True)
    await _index(db.integration_connectors, [("org_id", 1), ("key", 1)])

    # --- Listados por cliente.
    for coll in _ORG_LISTED:
        await _index(db[coll], [("org_id", 1), ("created_at", -1)])
    await _index(db.custom_agents, [("org_id", 1), ("created_at", -1)])
    await _index(db.calls, [("org_id", 1), ("created_at", -1)])
    await _index(db.agent_tool_calls, [("org_id", 1), ("created_at", -1)])
    await _index(db.chat_threads, [("org_id", 1), ("updated_at", -1)])
    await _index(db.chat_messages, [("org_id", 1), ("thread_id", 1), ("created_at", 1)])
    await _index(db.novedades_ticks, [("org_id", 1), ("ts", -1)])
    await _index(db.orders, [("org_id", 1), ("external_ref", 1)])
    await _index(db.orders, [("org_id", 1), ("customer_phone", 1)])
    await _index(db.call_queue, [("org_id", 1), ("order_id", 1)])
    await _index(db.vip_leads, "whatsapp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_indexes()
    scheduler.start()
    log.info("Zynex OS API ready.")
    try:
        yield
    finally:
        scheduler.stop()
        await close_db()


app = FastAPI(
    # Documentación de la API cerrada en producción (mapa gratis para atacantes/copiones).
    docs_url=None if os.environ.get("EXPOSE_DOCS") != "1" else "/docs",
    redoc_url=None if os.environ.get("EXPOSE_DOCS") != "1" else "/redoc",
    openapi_url=None if os.environ.get("EXPOSE_DOCS") != "1" else "/openapi.json",
    title="Zynex OS API",
    description=(
        "Zynex OS — plataforma multi-cliente de agentes de IA (copiloto, voz y "
        "WhatsApp) para operar cualquier negocio. Cada cliente (org) ve y opera "
        "solo sus propios datos.\n\n"
        "Auth: sesión JWT (cookie o `Authorization: Bearer`) o cabecera "
        "`X-API-Key: <PUBLIC_API_KEY>` (+ `X-Org-Id` servidor-a-servidor).\n"
        "Los webhooks de proveedores no llevan sesión: cada cliente usa su URL "
        "con token (`GET /api/org/webhook-urls`); sin token solo se aceptan con "
        "firma válida. Fallan cerrado."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()],
    # Por defecto solo localhost. Otros orígenes por patrón (p. ej. previews)
    # se habilitan explícitamente con CORS_ORIGIN_REGEX; los fijos, con CORS_ORIGINS.
    allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX", "").strip()
    or r"http://localhost:\d+",
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
api.include_router(copilot_router)
api.include_router(skills_router)
api.include_router(files_router)
api.include_router(dropi_router)
api.include_router(products_router)
api.include_router(prompts_router)
api.include_router(vip_public_router)
api.include_router(vip_admin_router)
api.include_router(config_router)
api.include_router(auth_router)
api.include_router(agents_router)
api.include_router(llm_router)
api.include_router(feedback_router)
api.include_router(custom_agents_router)
api.include_router(calls_router)
api.include_router(agent_tools_router)
api.include_router(org_profile_router)
api.include_router(packs_router)
api.include_router(mcp_servers_router)
api.include_router(kb_router)
api.include_router(automations_router)


@api.get("/", tags=["health"], summary="Root health.")
async def api_root():
    return {"name": "Zynex OS API", "version": "1.0.0",
            "docs": "/docs", "redoc": "/redoc"}


app.include_router(api)
