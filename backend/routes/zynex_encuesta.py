"""Formulario de descubrimiento para dropshippers de Dropi.

Público (sin sesión): POST /encuesta guarda una respuesta en Supabase.
Con sesión: GET /encuesta/resultados devuelve conteos y respuestas; solo lo ven
las empresas vinculadas a un espacio de Zynex (el equipo).
No envía mensajes a nadie. El WhatsApp solo se guarda si la persona acepta.
"""
from __future__ import annotations

import hashlib
import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import ratelimit
from deps import get_org, require_api_key
from routes.zynex_motor import rpc

router = APIRouter(prefix="/encuesta", tags=["encuesta"])

MAX_POR_HORA = 5
VENTANA_S = 3600


class EncuestaIn(BaseModel):
    pedidos_dia: Literal["menos_20", "20_100", "100_500", "mas_500"]
    pais: str = Field(min_length=2, max_length=40)
    dolores: list[Literal["confirmar", "novedades", "oficina", "devoluciones", "chats"]] = Field(min_length=1, max_length=5)
    quien: Literal["yo", "una_persona", "equipo", "herramienta"]
    herramienta: Optional[str] = Field(default=None, max_length=300)
    arreglar: Optional[str] = Field(default=None, max_length=600)
    whatsapp: Optional[str] = Field(default=None, max_length=25)
    acepta_contacto: bool = False
    origen: Optional[str] = Field(default=None, max_length=60)
    sitio_web: Optional[str] = Field(default=None, max_length=200)  # trampa para bots: debe llegar vacío


def ip_hash(request: Request) -> str:
    sal = os.environ.get("ENCRYPTION_KEY") or os.environ.get("JWT_SECRET") or "zynex"
    return hashlib.sha256(f"{sal}:{ratelimit.client_ip(request)}".encode()).hexdigest()[:32]


@router.post("", summary="Guarda una respuesta del formulario público (máx. 5 por hora por conexión).")
async def responder(p: EncuestaIn, request: Request):
    if p.sitio_web:
        return {"ok": True}  # bot: se descarta en silencio
    key = "encuesta:" + ratelimit.client_ip(request)
    if ratelimit.count(key, VENTANA_S) >= MAX_POR_HORA:
        raise HTTPException(429, "Ya recibimos varias respuestas desde esta conexión. Gracias.")
    ratelimit.hit(key, VENTANA_S)
    datos = p.model_dump(exclude={"sitio_web"})
    datos["dolores"] = list(dict.fromkeys(p.dolores))
    if not p.acepta_contacto:
        datos["whatsapp"] = None
    try:
        await rpc("zc_form_guardar", {"p": datos, "p_ip_hash": ip_hash(request)})
    except HTTPException as e:
        if e.status_code == 503:
            raise
        raise HTTPException(502, "No pudimos guardar tu respuesta. Intenta de nuevo en un momento.")
    return {"ok": True, "mensaje": "¡Gracias! Tu respuesta quedó guardada."}


@router.get("/resultados", dependencies=[Depends(require_api_key)])
async def resultados(request: Request):
    d = await rpc("zc_form_resultados", {"p_org": get_org(request)})
    if d is None:
        raise HTTPException(403, "Solo el equipo de Zynex ve estos resultados.")
    return d
