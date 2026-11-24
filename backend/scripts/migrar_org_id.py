"""Migración idempotente: pone org_id donde falte (datos previos al multi-cliente).

Desde que cada lectura filtra por org_id, un documento SIN org_id no lo ve
nadie. Este script asigna esos documentos antiguos a un cliente:

Uso (desde backend/):
    python scripts/migrar_org_id.py                    # simulación: solo cuenta
    python scripts/migrar_org_id.py --apply            # asigna org_id="default"
    python scripts/migrar_org_id.py --org <ORG_ID> --apply
        # asigna al cliente real (ej. la org de Litper; sale de GET /api/auth/me)

- Solo toca documentos donde org_id falta o es null: correrlo dos veces no
  cambia nada, y nunca mueve datos que ya tienen dueño.
- Marca el paquete "cod_colombia" como instalado para ese cliente si ya tenía
  las transportadoras sembradas por el arranque antiguo, y le crea un perfil
  (CO / COP / America/Bogota) si no tiene, para conservar su comportamiento.
- No borra nada. Ejecutarlo ANTES de arrancar la versión nueva (los índices
  únicos compuestos con org_id se crean al arrancar).
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Colecciones con datos de cliente (todas las que las rutas filtran por org_id).
COLLECTIONS = [
    "orders", "call_queue", "call_schedules", "customer_tasks", "message_log",
    "catalog_products", "uploaded_files", "copilot_skills", "voice_profiles",
    "connected_numbers", "prompts", "whatsapp_rules", "whatsapp_contacts",
    "dropi_previews", "vip_leads", "integration_connectors", "chat_threads",
    "chat_messages", "carriers", "carrier_novedades", "rto_blacklist",
    "ceo_reports", "novedades_ticks", "settings", "webhook_events",
    "agent_tool_calls", "feedback", "calls", "custom_agents",
]
SIN_ORG = {"$or": [{"org_id": {"$exists": False}}, {"org_id": None}]}


async def migrate(db, org: str = "default", apply: bool = False) -> dict:
    """Devuelve {colección: documentos sin org_id}. Con apply=True los asigna."""
    counts: dict[str, int] = {}
    for name in COLLECTIONS:
        coll = db[name]
        n = await coll.count_documents(SIN_ORG)
        counts[name] = n
        if apply and n:
            await coll.update_many(SIN_ORG, {"$set": {"org_id": org}})
    if apply:
        now = datetime.now(timezone.utc).isoformat()
        if await db.carriers.count_documents({"org_id": org}):
            await db.org_packs.update_one(
                {"org_id": org, "pack": "cod_colombia"},
                {"$setOnInsert": {"org_id": org, "pack": "cod_colombia",
                                  "installed_at": now, "source": "migrar_org_id"}},
                upsert=True)
            await db.org_profiles.update_one(
                {"org_id": org},
                {"$setOnInsert": {"org_id": org, "pais": "CO", "moneda": "COP",
                                  "zona_horaria": "America/Bogota", "idioma": "es",
                                  "updated_at": now}},
                upsert=True)
    return counts


async def main(org: str, apply: bool) -> None:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from db import get_db
    counts = await migrate(get_db(), org, apply)
    total = sum(counts.values())
    for name, n in counts.items():
        if n:
            print(f"  {name:24s} {n}")
    verbo = "asignados a" if apply else "se asignarían a"
    print(f"{total} documentos sin org_id {verbo} org_id={org!r}.")
    if not apply:
        print("Simulación. Repite con --apply para ejecutar.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--org", default="default", help='org destino (por defecto "default")')
    ap.add_argument("--apply", action="store_true", help="ejecuta (sin esto solo simula)")
    a = ap.parse_args()
    asyncio.run(main(a.org, a.apply))
