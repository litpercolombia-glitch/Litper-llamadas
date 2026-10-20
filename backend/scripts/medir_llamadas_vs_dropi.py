"""Mide las llamadas reales de Zynex Connect contra el estado final en Dropi.

Hito M2 (31-oct): 50 llamadas reales de Litper medidas contra Dropi.
La verdad es Dropi, no el resultado que reporta la llamada.

Solo lectura: no escribe en Mongo ni en Dropi.

Uso:
    MONGO_URL=... DB_NAME=... python scripts/medir_llamadas_vs_dropi.py \
        --dropi export_dropi.csv [--desde 2026-10-01] [--hasta 2026-10-31] \
        [--col-id ID] [--col-estado ESTATUS] [--json salida.json]

El CSV de Dropi es el reporte de órdenes (una fila por pedido o por producto;
se colapsa por ID). Se cruza con orders.external_ref.

Grupos:
  llamado  = item de call_queue con >= 1 intento channel=call, status=done y
             evidencia de llamada real (call_sid o duration_seconds > 0).
  control  = item de call_queue del mismo periodo sin llamada real.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone

META_LLAMADAS = 50
RESULTADOS_POSITIVOS = {"confirmado", "ya_recogio", "extension"}


def clasificar_dropi(estado: str | None) -> str:
    """entregado | devuelto | abierto | sin_dato."""
    if not estado:
        return "sin_dato"
    e = estado.strip().upper()
    if "ENTREGAD" in e and "NO ENTREGAD" not in e:
        return "entregado"
    if any(k in e for k in ("DEVOL", "DEVUELT", "RECHAZ", "CANCEL")):
        return "devuelto"
    return "abierto"


def es_llamada_real(intento: dict) -> bool:
    return (
        intento.get("channel") == "call"
        and intento.get("status") == "done"
        and (bool(intento.get("call_sid")) or (intento.get("duration_seconds") or 0) > 0)
    )


def _ic95_diferencia(p1: float, n1: int, p2: float, n2: int) -> tuple[float, float] | None:
    if not n1 or not n2:
        return None
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    d = p1 - p2
    return (round((d - 1.96 * se) * 100, 1), round((d + 1.96 * se) * 100, 1))


def medir(queue: list[dict], schedules: list[dict], orders: list[dict],
          dropi: dict[str, str]) -> dict:
    """Función pura: devuelve el reporte. `dropi` = {id_dropi: estado}."""
    order_by_id = {o["id"]: o for o in orders}
    sched_by_q = {s.get("queue_id"): s for s in schedules}

    grupos: dict[str, list[dict]] = {"llamado": [], "control": []}
    llamadas_reales = 0
    for q in queue:
        intentos = (sched_by_q.get(q["id"]) or {}).get("attempts", [])
        reales = [a for a in intentos if es_llamada_real(a)]
        llamadas_reales += len(reales)
        order = order_by_id.get(q.get("order_id")) or {}
        ref = str(order.get("external_ref") or "").strip()
        fila = {
            "queue_id": q["id"],
            "external_ref": ref or None,
            "estado_cola": q.get("status"),
            "resultado_llamada": (reales[-1].get("result") if reales else None),
            "dropi": clasificar_dropi(dropi.get(ref)) if ref else "sin_dato",
        }
        grupos["llamado" if reales else "control"].append(fila)

    def resumen(filas: list[dict]) -> dict:
        c = Counter(f["dropi"] for f in filas)
        cerrados = c["entregado"] + c["devuelto"]
        return {
            "items": len(filas),
            "cruzados_con_dropi": len(filas) - c["sin_dato"],
            "entregado": c["entregado"], "devuelto": c["devuelto"],
            "abierto": c["abierto"], "sin_dato": c["sin_dato"],
            "tasa_entrega_cerrados_pct": round(c["entregado"] / cerrados * 100, 1) if cerrados else None,
            "_cerrados": cerrados,
        }

    r_l, r_c = resumen(grupos["llamado"]), resumen(grupos["control"])

    # Concordancia: ¿lo que dijo la llamada coincide con lo que pasó en Dropi?
    concord = Counter()
    for f in grupos["llamado"]:
        if f["dropi"] not in ("entregado", "devuelto") or not f["resultado_llamada"]:
            continue
        positivo = f["resultado_llamada"] in RESULTADOS_POSITIVOS
        concord["acierta" if positivo == (f["dropi"] == "entregado") else "falla"] += 1
    n_conc = concord["acierta"] + concord["falla"]

    ic = None
    if r_l["tasa_entrega_cerrados_pct"] is not None and r_c["tasa_entrega_cerrados_pct"] is not None:
        ic = _ic95_diferencia(r_l["tasa_entrega_cerrados_pct"] / 100, r_l["_cerrados"],
                              r_c["tasa_entrega_cerrados_pct"] / 100, r_c["_cerrados"])
    for r in (r_l, r_c):
        r.pop("_cerrados")

    medidas = r_l["cruzados_con_dropi"]
    return {
        "corte_utc": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "llamadas_reales": llamadas_reales,
        "items_llamados_medidos_contra_dropi": medidas,
        "meta_hito": META_LLAMADAS,
        "hito_cumplido": medidas >= META_LLAMADAS,
        "llamado": r_l,
        "control": r_c,
        "diferencia_entrega_pts": (
            round(r_l["tasa_entrega_cerrados_pct"] - r_c["tasa_entrega_cerrados_pct"], 1)
            if ic is not None else None),
        "ic95_diferencia_pts": ic,
        "senal": ("señal" if ic and (ic[0] > 0 or ic[1] < 0) else "ruido") if ic else "sin dato confiable",
        "concordancia_llamada_vs_dropi_pct": round(concord["acierta"] / n_conc * 100, 1) if n_conc else None,
    }


def leer_dropi_csv(ruta: str, col_id: str, col_estado: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(ruta, newline="", encoding="utf-8-sig") as fh:
        muestra = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(muestra, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        for row in csv.DictReader(fh, dialect=dialect):
            k = str(row.get(col_id) or "").strip()
            if k:
                out[k] = row.get(col_estado) or ""
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dropi", required=True, help="CSV exportado de Dropi")
    ap.add_argument("--col-id", default="ID")
    ap.add_argument("--col-estado", default="ESTATUS")
    ap.add_argument("--desde", help="YYYY-MM-DD (created_at de call_queue)")
    ap.add_argument("--hasta", help="YYYY-MM-DD inclusive")
    ap.add_argument("--json", help="Ruta para guardar el reporte")
    a = ap.parse_args(argv)

    from pymongo import MongoClient  # motor ya instala pymongo
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    filtro: dict = {}
    if a.desde or a.hasta:
        filtro["created_at"] = {}
        if a.desde:
            filtro["created_at"]["$gte"] = a.desde
        if a.hasta:
            filtro["created_at"]["$lte"] = a.hasta + "T23:59:59"
    queue = list(db.call_queue.find(filtro, {"_id": 0}))
    q_ids = [q["id"] for q in queue]
    schedules = list(db.call_schedules.find({"queue_id": {"$in": q_ids}}, {"_id": 0}))
    o_ids = [q.get("order_id") for q in queue]
    orders = list(db.orders.find({"id": {"$in": o_ids}}, {"_id": 0, "id": 1, "external_ref": 1}))

    reporte = medir(queue, schedules, orders, leer_dropi_csv(a.dropi, a.col_id, a.col_estado))
    txt = json.dumps(reporte, ensure_ascii=False, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            fh.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
