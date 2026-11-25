"""Zynex · Pendientes de Chatea Pro — reglas que cada cliente ajusta.

Tres clases de pendiente: diario (falta un dato para crear el pedido), oficina
(zona de riesgo: se pide un adelanto) y final (no responde: recordatorios y
cancelación). El cliente elige qué columnas del tablero de Chatea trabaja el
agente y los valores de cada regla. Las plantillas se eligen en las casillas.
Aquí solo se guarda la configuración: no se envía nada.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deps import get_org, require_api_key
from routes import zynex_motor

router = APIRouter(prefix="/zcall/motor/pendientes", tags=["zynex-pendientes"])

CLASES = {"diario", "oficina", "final"}
COLUMNA_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÑáéíóúñ0-9_ .\-]{1,40}$")


class PendienteIn(BaseModel):
    activo: bool = False
    columnas: list[str] = Field(default_factory=list, max_length=10)
    adelanto: int | None = Field(default=None, ge=0, le=500000)
    dias_sin_respuesta: int | None = Field(default=None, ge=1, le=10)
    plantillas: int | None = Field(default=None, ge=1, le=3)
    cancelar: bool | None = None
    llamar: bool = False


@router.get("", dependencies=[Depends(require_api_key)])
async def pendientes(request: Request):
    return {"reglas": await zynex_motor.rpc("zc_api_pendientes", {"p_org": get_org(request)}) or []}


@router.put("/{clase}", dependencies=[Depends(require_api_key)])
async def guardar(clase: str, p: PendienteIn, request: Request):
    if clase not in CLASES:
        raise HTTPException(400, "Clase de pendiente inválida.")
    cols = []
    for c in p.columnas:
        c = (c or "").strip()
        if not c:
            continue
        if not COLUMNA_RE.match(c):
            raise HTTPException(400, "El nombre de la columna solo lleva letras, números, espacios y guiones.")
        if c.upper() not in cols:
            cols.append(c.upper())
    params = {k: v for k, v in {"adelanto": p.adelanto, "dias_sin_respuesta": p.dias_sin_respuesta,
                                "plantillas": p.plantillas, "cancelar": p.cancelar, "llamar": p.llamar}.items() if v is not None}
    ok = await zynex_motor.rpc("zc_api_pendiente_guardar", {"p_org": get_org(request), "p_clase": clase,
                                                           "p_activo": p.activo, "p_columnas": cols, "p_params": params})
    if ok is not True:
        raise HTTPException(400, "No se pudo guardar la regla.")
    return {"ok": True, "mensaje": "Regla guardada."}
