"""Zynex · Control de mando — cerebro central logístico (modo sombra).

Las reglas viven en datos (tabla zc_cb_regla en Supabase), no en prompts. Aquí
solo se lee el informe por proceso, las colas, la línea de tiempo del pedido y
los casos para una persona, y se guarda lo que dijo el cliente. Nada de esto
envía mensajes ni llama: el motor decide y anota.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deps import get_org, require_api_key
from routes.zynex_motor import configurado, rpc

router = APIRouter(prefix="/zcall/cerebro", tags=["zynex-cerebro"])
PROCESOS = {"pendientes", "seguimiento", "novedades", "oficina", "cierre", "postventa", "proveedores"}
CANALES = {"llamada", "mensaje", "chat", "otro"}


class DichoIn(BaseModel):
    texto: str = Field(min_length=2, max_length=1000)
    canal: str = Field(default="llamada", max_length=20)
    compromiso: str = Field(default="", max_length=300)
    ticket: bool = False


class PromptIn(BaseModel):
    contenido: str = Field(min_length=200, max_length=12000)


class ResolverIn(BaseModel):
    nota: str = Field(min_length=2, max_length=500)


def _pedido(pedido: str) -> int:
    if not pedido.isdigit() or len(pedido) > 15:
        raise HTTPException(400, "Número de pedido inválido.")
    return int(pedido)


def _autor(request: Request) -> str | None:
    u = getattr(request.state, "user", None) or {}
    v = (u.get("name") or u.get("email")) if isinstance(u, dict) else None
    return str(v)[:80] if v else None


@router.get("/control", dependencies=[Depends(require_api_key)])
async def control(request: Request):
    if not configurado():
        return {"conectado": False, "vinculado": False}
    d = await rpc("zc_api_control", {"p_org": get_org(request)}) or {}
    d["conectado"] = True
    if d.get("vinculado"):
        try:
            d["extra"] = await rpc("zc_api_cb_extra", {"p_org": get_org(request)}) or {}
        except HTTPException:
            d["extra"] = {}
    return d


@router.get("/cola", dependencies=[Depends(require_api_key)])
async def cola(proceso: str, request: Request, limite: int = 100):
    if proceso not in PROCESOS:
        raise HTTPException(400, "Proceso inválido.")
    filas = await rpc("zc_api_cb_cola", {"p_org": get_org(request), "p_proceso": proceso,
                                         "p_limite": max(1, min(int(limite), 300))})
    return {"proceso": proceso, "filas": filas or []}


@router.get("/pedidos/{pedido}/linea", dependencies=[Depends(require_api_key)])
async def linea(pedido: str, request: Request):
    d = await rpc("zc_api_cb_linea", {"p_org": get_org(request), "p_pedido": _pedido(pedido)})
    if not d or not d.get("decision"):
        raise HTTPException(404, "Pedido no encontrado.")
    return d


@router.post("/pedidos/{pedido}/dicho", dependencies=[Depends(require_api_key)])
async def dicho(pedido: str, p: DichoIn, request: Request):
    canal = p.canal if p.canal in CANALES else "otro"
    r = await rpc("zc_api_cb_dicho", {"p_org": get_org(request), "p_pedido": _pedido(pedido), "p_texto": p.texto.strip(),
                                      "p_canal": canal, "p_compromiso": p.compromiso.strip(), "p_ticket": p.ticket,
                                      "p_autor": _autor(request)})
    if not (r or {}).get("ok"):
        raise HTTPException(404, "Pedido no encontrado.")
    return {"ok": True}


@router.get("/persona", dependencies=[Depends(require_api_key)])
async def persona(request: Request):
    return {"casos": await rpc("zc_api_cb_persona", {"p_org": get_org(request)}) or []}


@router.post("/persona/{caso}/resolver", dependencies=[Depends(require_api_key)])
async def resolver(caso: int, p: ResolverIn, request: Request):
    r = await rpc("zc_api_cb_persona", {"p_org": get_org(request), "p_id": caso, "p_nota": p.nota.strip(),
                                        "p_autor": _autor(request)})
    if not (r or {}).get("ok"):
        raise HTTPException(404, "Caso no encontrado o ya resuelto.")
    return {"ok": True}


@router.get("/reglas", dependencies=[Depends(require_api_key)])
async def reglas(request: Request):
    return {"reglas": await rpc("zc_api_cb_reglas", {"p_org": get_org(request)}) or []}


PROMPTS = {"maestro", "pedidos", "pendientes", "seguimiento", "novedades", "oficina"}


@router.get("/prompts", dependencies=[Depends(require_api_key)])
async def prompts(request: Request):
    return {"prompts": await rpc("zc_api_cb_prompts", {"p_org": get_org(request)}) or []}


@router.put("/prompts/{proceso}/{tipo}", dependencies=[Depends(require_api_key)])
async def guardar_prompt(proceso: str, tipo: str, p: PromptIn, request: Request):
    if proceso not in PROMPTS or tipo not in {"texto", "voz"}:
        raise HTTPException(400, "Proceso o tipo inválido.")
    r = await rpc("zc_api_cb_prompt_guardar", {"p_org": get_org(request), "p_proceso": proceso, "p_tipo": tipo,
                                               "p_contenido": p.contenido.strip(), "p_autor": _autor(request)})
    if not (r or {}).get("ok"):
        raise HTTPException(400, "No se pudo guardar. Revisa que el texto tenga al menos 200 caracteres.")
    return {"ok": True, "version": r.get("version")}
