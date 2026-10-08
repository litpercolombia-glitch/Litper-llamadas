"""Migración única: mueve las credenciales guardadas bajo org_id="default"
al cliente real (ej. la org de Litper), para que no "desaparezcan" cuando
la pantalla empiece a usar el org del JWT.

Uso (desde backend/):
    python scripts/migrar_credenciales_default.py --to <ORG_ID_DE_LITPER>          # simulación
    python scripts/migrar_credenciales_default.py --to <ORG_ID_DE_LITPER> --apply  # ejecuta

El ORG_ID sale de GET /api/auth/me ("org_id") con la sesión de Litper.
Copia al destino y luego VACÍA el registro "default" (sin cifrado) para que quede inutilizable.
Si el destino ya tiene ese proveedor, NO lo pisa.
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from db import get_db  # noqa: E402


async def main(to_org: str, apply: bool) -> None:
    db = get_db()
    moved, skipped = [], []
    async for d in db.org_credentials.find({"org_id": "default"}, {"_id": 0}):
        prov = d["provider"]
        if await db.org_credentials.find_one({"org_id": to_org, "provider": prov}):
            skipped.append(prov)
            if apply:   # el destino ya tiene su llave: igual se vacía "default"
                await db.org_credentials.update_one(
                    {"org_id": "default", "provider": prov},
                    {"$set": {"migrated_to": to_org, "ciphertext": "", "hint": "",
                              "is_configured": False}})
            continue
        moved.append(prov)
        if apply:
            new = {**d, "org_id": to_org,
                   "migrated_from": "default",
                   "updated_at": datetime.now(timezone.utc).isoformat()}
            await db.org_credentials.insert_one(new)
            # Vaciar el cajón "default" para que nadie más pueda usar esas llaves.
            await db.org_credentials.update_one(
                {"org_id": "default", "provider": prov},
                {"$set": {"migrated_to": to_org, "ciphertext": "", "hint": "",
                          "is_configured": False}})
    print(("APLICADO" if apply else "SIMULACIÓN"), "->", to_org)
    print("  copiados:", moved or "ninguno")
    print("  ya existían en destino ('default' igual se vacía):", skipped or "ninguno")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.to, a.apply))
