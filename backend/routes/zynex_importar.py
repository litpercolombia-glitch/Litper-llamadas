"""Zynex · Traer mi operación — carga el reporte de órdenes de Dropi del cliente.

El cliente sube su archivo de Dropi (Excel o CSV) y elige cuántos días traer
(30, 60 o 90). Los pedidos quedan en SU espacio: alimentan Clientes y Métricas.
No crea tareas ni envía mensajes: solo guarda la historia para medir y mejorar.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from deps import get_org, require_api_key
from dropi_import import parse_sheet
from routes import zynex_motor

router = APIRouter(prefix="/zcall/motor/operacion", tags=["zynex-operacion"])

MAX_BYTES = 15 * 1024 * 1024
LOTE = 2000
DIAS_OK = (30, 60, 90)


def filas_de(consolidado: list[dict], dias: int, hoy: date | None = None) -> tuple[list[dict], dict]:
    """Convierte el resultado del lector de Dropi en filas para la base y cuenta lo que se descarta."""
    corte = ((hoy or date.today()) - timedelta(days=dias)).isoformat()
    filas, sin_dato, fuera = [], 0, 0
    for e in consolidado or []:
        pedido = re.sub(r"\D", "", str(e.get("external_ref") or ""))
        estado = str(e.get("status_raw") or "").strip()
        if not pedido or not estado:
            sin_dato += 1
            continue
        creado = str(e.get("order_date") or "")[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", creado):
            if creado < corte:
                fuera += 1
                continue
        else:
            creado = None
        total = e.get("total_amount")
        filas.append({
            "pedido": pedido, "estado": estado,
            "telefono": str(e.get("customer_phone") or ""), "nombre": str(e.get("customer_name") or ""),
            "ciudad": str(e.get("city") or ""), "transportadora": str(e.get("carrier_raw") or ""),
            "guia": str(e.get("tracking_number") or ""),
            "valor": str(int(round(float(total)))) if isinstance(total, (int, float)) and total > 0 else None,
            "creado": creado,
        })
    return filas, {"sin_dato": sin_dato, "fuera_de_periodo": fuera}


@router.post("/importar", dependencies=[Depends(require_api_key)],
             summary="Sube el reporte de órdenes de Dropi y guarda los últimos 30, 60 o 90 días.")
async def importar(request: Request, file: UploadFile = File(...), dias: int = Form(90)):
    if dias not in DIAS_OK:
        raise HTTPException(400, "Elige 30, 60 o 90 días.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "El archivo está vacío.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "El archivo pesa más de 15 MB. Descarga un periodo más corto.")
    try:
        res = parse_sheet(data, file.filename or "", None)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "No pudimos leer el archivo. Sube el reporte de órdenes de Dropi en Excel o CSV.")
    filas, desc = filas_de(res.consolidated, dias)
    if not filas:
        raise HTTPException(400, "No encontramos pedidos en ese periodo. Revisa que el archivo tenga las columnas ID y ESTATUS.")
    org, guardados = get_org(request), 0
    for i in range(0, len(filas), LOTE):
        r = await zynex_motor.rpc("zc_api_pedidos_importar", {"p_org": org, "p_filas": filas[i:i + LOTE], "p_fuente": "archivo_dropi"})
        if not isinstance(r, dict) or not r.get("ok"):
            raise HTTPException(400, "Activa tu espacio en Logística antes de traer tu operación."
                                if isinstance(r, dict) and "vinculado" in str(r.get("error")) else "No se pudieron guardar los pedidos.")
        guardados += int(r.get("guardados") or 0)
    return {"ok": True, "dias": dias, "leidos": len(res.consolidated or []), "guardados": guardados, **desc,
            "mensaje": f"Listo: {guardados} pedidos de los últimos {dias} días."}
