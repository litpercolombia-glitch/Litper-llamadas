"""Zynex · Agente de Logística — panel, casillas, secuencia, clientes (CRM) y métricas.

El motor vive en Supabase (tablas zc_*, en modo sombra). Aquí solo se lee y se
guarda la configuración del cliente llamando funciones de la base con la llave
de servicio del servidor (nunca sale al navegador). Cada empresa (org) ve solo
el espacio al que fue vinculada con un código de un solo uso.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deps import get_org, require_api_key

log = logging.getLogger("zynex_motor")
router = APIRouter(prefix="/zcall/motor", tags=["zynex-motor"])

CLAVE_RE = re.compile(r"^(estado|accion):[A-Za-zÁÉÍÓÚÑáéíóúñ0-9_ ]{1,60}$")
METRICA_RE = re.compile(r"^m:[A-Za-z0-9_]{1,30}$")
TEL_RE = re.compile(r"^[0-9]{10}$")
FILTROS = {"todos", "atencion", "activos", "recompra", "riesgo"}
PLANTILLA_RE = re.compile(r"^[a-z0-9_]{1,120}$")
ACCION_TXT = {
    "enviaria_mensaje": "Enviaría mensaje", "llamaria": "Llamaría", "lo_envia_su_bot": "Lo envía tu bot", "esperar_ventana": "Espera el horario",
    "cancelar": "Cancelada: el estado cambió", "humano": "Pasa a una persona",
    "pendiente": "En cola", "sombra_decidida": "Decidida", "cancelada": "Cancelada",
}


def configurado() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


async def rpc(fn: str, args: dict[str, Any]) -> Any:
    if not configurado():
        raise HTTPException(503, "El motor de logística aún no está conectado en el servidor.")
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(f"{url}/rest/v1/rpc/{fn}", json=args,
                               headers={"apikey": key, "Authorization": f"Bearer {key}"})
    except httpx.HTTPError as e:  # noqa: BLE001
        log.warning("motor rpc %s: %s", fn, e)
        raise HTTPException(502, "No se pudo leer el motor de logística. Intenta de nuevo.")
    if r.status_code == 404:
        raise HTTPException(501, "Esta parte aún no está activada en la base de datos. Soporte de Zynex la activa.")
    if r.status_code >= 300:
        log.warning("motor rpc %s -> %s %s", fn, r.status_code, r.text[:200])
        raise HTTPException(502, "El motor de logística respondió con error.")
    return r.json()


class VincularIn(BaseModel):
    codigo: str = Field(min_length=8, max_length=80)


class CasillaIn(BaseModel):
    plantilla: str = Field(default="", max_length=120)


@router.get("/panel", dependencies=[Depends(require_api_key)])
async def panel(request: Request):
    if not configurado():
        return {"conectado": False, "vinculado": False}
    d = await rpc("zc_api_panel", {"p_org": get_org(request)})
    d["conectado"] = True
    for t in d.get("tareas") or []:
        t["titulo"] = ACCION_TXT.get(t.get("titulo"), t.get("titulo"))
    return d


@router.post("/vincular", dependencies=[Depends(require_api_key)])
async def vincular(p: VincularIn, request: Request):
    ok = await rpc("zc_api_vincular", {"p_org": get_org(request), "p_codigo": p.codigo.strip()})
    if ok is not True:
        raise HTTPException(400, "Código inválido, vencido o ya usado.")
    return {"ok": True, "mensaje": "Espacio vinculado."}


@router.get("/lista", dependencies=[Depends(require_api_key)])
async def lista(clave: str, request: Request, limite: int = 200):
    if not CLAVE_RE.match(clave or ""):
        raise HTTPException(400, "Filtro inválido.")
    filas = await rpc("zc_api_lista", {"p_org": get_org(request), "p_clave": clave,
                                       "p_limite": max(1, min(int(limite), 500))})
    for f in filas or []:
        f["accion_txt"] = ACCION_TXT.get(f.get("accion") or f.get("tarea"), f.get("accion") or "Sin tarea")
        if f.get("cliente"):
            f["cliente"] = str(f["cliente"]).split(" ")[0]
    return {"clave": clave, "filas": filas or []}


@router.get("/casillas", dependencies=[Depends(require_api_key)])
async def casillas(request: Request):
    return {"casillas": await rpc("zc_api_casillas", {"p_org": get_org(request)}) or []}


@router.put("/casillas/{slot}", dependencies=[Depends(require_api_key)])
async def guardar_casilla(slot: str, p: CasillaIn, request: Request):
    plantilla = p.plantilla.strip().lower()
    if not re.match(r"^[a-z0-9_]{1,40}$", slot):
        raise HTTPException(400, "Casilla inválida.")
    if plantilla and not PLANTILLA_RE.match(plantilla):
        raise HTTPException(400, "El nombre de la plantilla solo lleva minúsculas, números y guion bajo.")
    ok = await rpc("zc_api_casilla_guardar", {"p_org": get_org(request), "p_slot": slot, "p_plantilla": plantilla})
    if ok is not True:
        raise HTTPException(400, "No se pudo guardar la casilla.")
    return {"ok": True, "mensaje": "Casilla guardada." if plantilla else "Casilla vaciada."}


@router.get("/secuencia", dependencies=[Depends(require_api_key)])
async def secuencia(request: Request):
    return {"pasos": await rpc("zc_api_secuencia", {"p_org": get_org(request)}) or []}


# ----------------------------------------------------------------- clientes (CRM)
class NotaIn(BaseModel):
    texto: str = Field(min_length=1, max_length=1000)


class CasoIn(BaseModel):
    estado: str = Field(pattern="^(abierto|resuelto)$")
    motivo: str = Field(default="", max_length=300)


def _autor(request: Request) -> str | None:
    from tenant import _jwt_claims
    c = _jwt_claims(request) or {}
    return (c.get("name") or c.get("email") or c.get("sub") or None)


def _tel(tel: str) -> str:
    t = re.sub(r"\D", "", tel or "")[-10:]
    if not TEL_RE.match(t):
        raise HTTPException(400, "Teléfono inválido.")
    return t


@router.get("/clientes", dependencies=[Depends(require_api_key)])
async def clientes(request: Request, q: str = "", filtro: str = "atencion", limite: int = 100):
    if filtro not in FILTROS:
        raise HTTPException(400, "Filtro inválido.")
    return await rpc("zc_api_clientes", {"p_org": get_org(request), "p_q": (q or "").strip()[:60],
                                         "p_filtro": filtro, "p_limite": max(1, min(int(limite), 300))})


@router.get("/clientes/{tel}", dependencies=[Depends(require_api_key)])
async def cliente(tel: str, request: Request):
    d = await rpc("zc_api_cliente", {"p_org": get_org(request), "p_tel": _tel(tel)})
    if not d:
        raise HTTPException(404, "No encontramos ese cliente.")
    for p in d.get("pedidos") or []:
        p["accion_txt"] = ACCION_TXT.get(p.get("accion"), "") if p.get("accion") else ""
    return d


@router.post("/clientes/{tel}/notas", dependencies=[Depends(require_api_key)])
async def cliente_nota(tel: str, p: NotaIn, request: Request):
    ok = await rpc("zc_api_cliente_nota", {"p_org": get_org(request), "p_tel": _tel(tel),
                                           "p_texto": p.texto.strip(), "p_autor": _autor(request)})
    if ok is not True:
        raise HTTPException(400, "No se pudo guardar la nota.")
    return {"ok": True, "mensaje": "Nota guardada."}


@router.put("/clientes/{tel}/caso", dependencies=[Depends(require_api_key)])
async def cliente_caso(tel: str, p: CasoIn, request: Request):
    ok = await rpc("zc_api_cliente_caso", {"p_org": get_org(request), "p_tel": _tel(tel), "p_estado": p.estado,
                                           "p_motivo": p.motivo.strip(), "p_autor": _autor(request)})
    if ok is not True:
        raise HTTPException(400, "No se pudo guardar.")
    return {"ok": True, "mensaje": "Marcado para que lo atienda una persona." if p.estado == "abierto" else "Caso resuelto."}


# ----------------------------------------------------------------- métricas
@router.get("/metricas", dependencies=[Depends(require_api_key)])
async def metricas(request: Request, dias: int = 30):
    return await rpc("zc_api_metricas", {"p_org": get_org(request), "p_dias": max(1, min(int(dias), 90))})


@router.get("/metricas/lista", dependencies=[Depends(require_api_key)])
async def metricas_lista(clave: str, request: Request, dias: int = 30, limite: int = 200):
    if not METRICA_RE.match(clave or ""):
        raise HTTPException(400, "Filtro inválido.")
    filas = await rpc("zc_api_metrica_lista", {"p_org": get_org(request), "p_clave": clave,
                                               "p_dias": max(1, min(int(dias), 90)), "p_limite": max(1, min(int(limite), 500))})
    for f in filas or []:
        f["accion_txt"] = "—"
        if f.get("cliente"):
            f["cliente"] = str(f["cliente"]).split(" ")[0]
    return {"clave": clave, "filas": filas or []}
