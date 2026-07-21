"""One-shot seed: 12 carriers + demo COD orders across different carriers.

Idempotent — running twice will not duplicate carriers or orders (uses upsert by slug
for carriers and skips demo orders if a demo external_ref already exists).
"""
from __future__ import annotations
import asyncio
import os
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from db import get_db
from data import CARRIERS_SEED
from models import Order, QueueItem


async def seed_carriers():
    db = get_db()
    for c in CARRIERS_SEED:
        await db.carriers.update_one({"slug": c["slug"]}, {"$set": c}, upsert=True)
    print(f"[seed] carriers upserted: {len(CARRIERS_SEED)}")


async def seed_demo_orders():
    db = get_db()
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    three_days_ago = (date.today() - timedelta(days=3)).isoformat()

    demo = [
        # Envía — 1-day deadline (COMPRESSED cadence expected)
        {"external_ref": "DEMO-ENV-001", "customer_name": "Sandra Ruiz",
         "customer_phone": "+573001112233", "address": "Cra 7 #45-12",
         "city": "Bogotá", "country": "CO", "total_amount": 189000, "currency": "COP",
         "carrier_slug": "envia", "tracking_number": "EN12345",
         "products": [{"name": "Faja moldeadora", "qty": 1, "price": 189000}],
         "office_arrival_date": today},

        # Servientrega — 8-day deadline (SPREAD cadence expected)
        {"external_ref": "DEMO-SVE-001", "customer_name": "Carlos Mejía",
         "customer_phone": "+573101234567", "address": "Cll 80 #12-34",
         "city": "Medellín", "country": "CO", "total_amount": 240000, "currency": "COP",
         "carrier_slug": "servientrega", "tracking_number": "SV98765",
         "products": [{"name": "Perfume árabe 100ml", "qty": 1, "price": 240000}],
         "office_arrival_date": yesterday},

        # Interrapidísimo — 4-day (mid)
        {"external_ref": "DEMO-INT-001", "customer_name": "Laura Gómez",
         "customer_phone": "+573204567890", "address": "Av Boyacá 100",
         "city": "Cali", "country": "CO", "total_amount": 129900, "currency": "COP",
         "carrier_slug": "interrapidisimo", "tracking_number": "IR55555",
         "products": [{"name": "Set skincare", "qty": 1, "price": 129900}],
         "office_arrival_date": today},

        # Coordinadora — 8-day, arrived 3 days ago (amarillo)
        {"external_ref": "DEMO-COO-001", "customer_name": "Andrea López",
         "customer_phone": "+573151230000", "address": "Cra 15 #90-45",
         "city": "Barranquilla", "country": "CO", "total_amount": 320000, "currency": "COP",
         "carrier_slug": "coordinadora", "tracking_number": "CO11223",
         "products": [{"name": "Zapatos deportivos", "qty": 1, "price": 320000}],
         "office_arrival_date": three_days_ago},

        # TCC — 3-day
        {"external_ref": "DEMO-TCC-001", "customer_name": "Diego Herrera",
         "customer_phone": "+573007778899", "address": "Cll 26 #68-14",
         "city": "Pereira", "country": "CO", "total_amount": 95000, "currency": "COP",
         "carrier_slug": "tcc", "tracking_number": "TCC7788",
         "products": [{"name": "Audífonos bluetooth", "qty": 2, "price": 47500}],
         "office_arrival_date": yesterday},

        # 99 Minutos — sin oficina (gris)
        {"external_ref": "DEMO-99M-001", "customer_name": "María Torres",
         "customer_phone": "+573045566778", "address": "Cll 50 #10-20",
         "city": "Bogotá", "country": "CO", "total_amount": 45000, "currency": "COP",
         "carrier_slug": "99-minutos", "tracking_number": "99M1010",
         "products": [{"name": "Estuche celular", "qty": 1, "price": 45000}],
         "office_arrival_date": today},

        # Wiilog — 2-day (mid → rojo/amarillo)
        {"external_ref": "DEMO-WII-001", "customer_name": "Juliana Ramírez",
         "customer_phone": "+573124567788", "address": "Cra 50 #23-14",
         "city": "Bucaramanga", "country": "CO", "total_amount": 78000, "currency": "COP",
         "carrier_slug": "wiilog", "tracking_number": "WI2020",
         "products": [{"name": "Reloj deportivo", "qty": 1, "price": 78000}],
         "office_arrival_date": today},
    ]

    inserted = 0
    for o in demo:
        exists = await db.orders.find_one({"external_ref": o["external_ref"]}, {"_id": 0, "id": 1})
        if exists:
            continue
        carrier = await db.carriers.find_one({"slug": o["carrier_slug"]}, {"_id": 0})
        order = Order(**o, status="in_queue")
        await db.orders.insert_one(order.model_dump())
        q = QueueItem(order_id=order.id, carrier_slug=order.carrier_slug,
                      office_arrival_date=o["office_arrival_date"],
                      office_claim_max_days=(carrier or {}).get("office_claim_max_days"),
                      country=order.country)
        await db.call_queue.insert_one(q.model_dump())
        inserted += 1
    print(f"[seed] demo orders inserted: {inserted} (existing skipped)")


async def seed_connectors():
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conns = [
        {"key": "chatea_pro", "name": "Chatea Pro (WhatsApp)", "status": "unconfigured",
         "last_checked_at": None, "metadata": {}},
        {"key": "dropi", "name": "Dropi (Fulfillment)", "status": "unconfigured",
         "last_checked_at": None, "metadata": {}},
        {"key": "whatsapp_business", "name": "WhatsApp Business (Meta Cloud)",
         "status": "unconfigured", "last_checked_at": None, "metadata": {}},
        {"key": "supabase", "name": "Supabase Postgres", "status": "unconfigured",
         "last_checked_at": None, "metadata": {}},
    ]
    for c in conns:
        c["updated_at"] = now
        await db.integration_connectors.update_one({"key": c["key"]},
                                                   {"$setOnInsert": c},
                                                   upsert=True)
    print("[seed] integration_connectors upserted")


async def main():
    await seed_carriers()
    await seed_demo_orders()
    await seed_connectors()
    print("[seed] DONE")


if __name__ == "__main__":
    asyncio.run(main())
