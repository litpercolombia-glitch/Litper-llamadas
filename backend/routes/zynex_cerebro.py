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
CANALES = {"llamada", "whatsapp", "mensaje", "chat", "correo", "otro"}


class DichoIn(BaseModel):
    texto: str = Field(min_length=3, max_length=1000)
    canal: str = Field(default="llamada", max_length=20)
    compromiso: str = Field(default="", max_length=300)
    ticket: bool = False


class PromptIn(BaseModel):
    contenido: str = Field(min_length=200, max_length=12000)


class ResolverIn(BaseModel):
    nota: str = Field(min_length=5, max_length=500)


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
        try:
            d["extra"].update(await rpc("zc_api_cb_extra2", {"p_org": get_org(request)}) or {})
        except HTTPException:
            pass
    return d


@router.get("/cola", dependencies=[Depends(require_api_key)])
async def cola(proceso: str, request: Request, limite: int = 100):
    if proceso not in PROCESOS:
        raise HTTPException(400, "Proceso inválido.")
    filas = await rpc("zc_api_cb_cola", {"p_org": get_org(request), "p_proceso": proceso,
                                         "p_limite": max(1, min(int(limite), 1000))})
    return {"proceso": proceso, "filas": filas or []}


@router.get("/pedidos/{pedido}/linea", dependencies=[Depends(require_api_key)])
async def linea(pedido: str, request: Request):
    d = await rpc("zc_api_cb_linea", {"p_org": get_org(request), "p_pedido": _pedido(pedido)})
    if not d or not d.get("encontrado"):
        raise HTTPException(404, (d or {}).get("error") or "Pedido no encontrado.")
    return d


@router.post("/pedidos/{pedido}/dicho", dependencies=[Depends(require_api_key)])
async def dicho(pedido: str, p: DichoIn, request: Request):
    canal = p.canal if p.canal in CANALES else "otro"
    r = await rpc("zc_api_cb_dicho", {"p_org": get_org(request), "p_pedido": _pedido(pedido), "p_texto": p.texto.strip(),
                                      "p_canal": canal, "p_compromiso": p.compromiso.strip(), "p_ticket": p.ticket,
                                      "p_autor": _autor(request)})
    r = r or {}
    if not r.get("ok"):
        raise HTTPException(400, r.get("error") or "No se pudo guardar el registro.")
    return {"ok": True, "id": r.get("id"), "repetido": bool(r.get("repetido")),
            "caso_para_persona": bool(r.get("caso_para_persona"))}


@router.get("/persona", dependencies=[Depends(require_api_key)])
async def persona(request: Request):
    return {"casos": await rpc("zc_api_cb_persona", {"p_org": get_org(request)}) or []}


@router.post("/persona/{caso}/resolver", dependencies=[Depends(require_api_key)])
async def resolver(caso: int, p: ResolverIn, request: Request):
    r = await rpc("zc_api_cb_persona", {"p_org": get_org(request), "p_id": caso, "p_nota": p.nota.strip(),
                                        "p_autor": _autor(request)})
    r = r or {}
    if not r.get("ok"):
        raise HTTPException(400, r.get("error") or "Caso no encontrado o ya cerrado.")
    return {"ok": True, "no_se_reabre_hasta": r.get("no_se_reabre_hasta")}


@router.get("/reglas", dependencies=[Depends(require_api_key)])
async def reglas(request: Request):
    return {"reglas": await rpc("zc_api_cb_reglas", {"p_org": get_org(request)}) or []}


PROMPTS = {"maestro", "pedidos", "pendientes", "seguimiento", "novedades", "oficina", "postventa"}


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
        raise HTTPException(400, (r or {}).get("error") or "No se pudo guardar. Revisa que el texto tenga al menos 200 caracteres.")
    return {"ok": True, "version": r.get("version")}


# ---------------------------------------------------------------- tienda, catálogo, conocimiento y guiones
GUIONES = {"pedidos", "pendientes", "seguimiento", "novedades", "oficina", "postventa"}


class TiendaIn(BaseModel):
    datos: dict[str, str] = Field(default_factory=dict)


class NotaIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=120)
    contenido: str = Field(min_length=10, max_length=4000)
    proceso: str = Field(default="general", max_length=30)


class GuionIn(BaseModel):
    texto: str = Field(min_length=40, max_length=3000)


def _ok(r, defecto: str) -> dict:
    r = r if isinstance(r, dict) else {}
    if not r.get("ok"):
        raise HTTPException(400, r.get("error") or defecto)
    return r


@router.get("/tienda", dependencies=[Depends(require_api_key)])
async def tienda(request: Request):
    return _ok(await rpc("zc_api_cb_tienda", {"p_org": get_org(request)}), "No se pudo leer los datos de la tienda.")


@router.put("/tienda", dependencies=[Depends(require_api_key)])
async def tienda_guardar(p: TiendaIn, request: Request):
    if len(p.datos) > 12:
        raise HTTPException(400, "Demasiados campos.")
    return _ok(await rpc("zc_api_cb_tienda", {"p_org": get_org(request), "p_datos": p.datos, "p_autor": _autor(request)}),
               "No se pudieron guardar los datos de la tienda.")


@router.post("/catalogo/actualizar", dependencies=[Depends(require_api_key)])
async def catalogo_actualizar(request: Request):
    return _ok(await rpc("zc_api_cb_catalogo_actualizar", {"p_org": get_org(request)}), "No se pudo actualizar el catálogo.")


@router.get("/conocimiento", dependencies=[Depends(require_api_key)])
async def conocimiento(request: Request):
    return _ok(await rpc("zc_api_cb_conocimiento", {"p_org": get_org(request)}), "No se pudo leer la base de conocimiento.")


@router.post("/conocimiento", dependencies=[Depends(require_api_key)])
async def conocimiento_agregar(p: NotaIn, request: Request):
    return _ok(await rpc("zc_api_cb_conocimiento", {"p_org": get_org(request), "p_titulo": p.titulo.strip(),
                                                    "p_contenido": p.contenido.strip(), "p_proceso": p.proceso.strip() or "general",
                                                    "p_autor": _autor(request)}), "No se pudo guardar la nota.")


@router.post("/guion/{proceso}/{tipo}", dependencies=[Depends(require_api_key)])
async def guion_armar(proceso: str, tipo: str, p: GuionIn, request: Request):
    if proceso not in GUIONES or tipo not in {"texto", "voz"}:
        raise HTTPException(400, "Proceso o tipo inválido.")
    r = _ok(await rpc("zc_api_cb_guion_armar", {"p_org": get_org(request), "p_proceso": proceso, "p_tipo": tipo,
                                                "p_texto": p.texto.strip(), "p_autor": _autor(request)}),
            "No se pudo armar el guion.")
    return {"ok": True, "version": r.get("version"), "vista_previa": r.get("vista_previa")}


# ---------------------------------------------------------------- lote de prueba (no envía nada)
@router.get("/lote", dependencies=[Depends(require_api_key)])
async def lote(request: Request):
    return _ok(await rpc("zc_api_cb_lote", {"p_org": get_org(request)}), "No se pudo leer el lote de prueba.")


@router.post("/lote/armar", dependencies=[Depends(require_api_key)])
async def lote_armar(request: Request):
    return _ok(await rpc("zc_api_cb_lote", {"p_org": get_org(request), "p_armar": True, "p_max": 20}),
               "No se pudo armar el lote de prueba.")


@router.delete("/conocimiento/{nota_id}", dependencies=[Depends(require_api_key)])
async def conocimiento_quitar(nota_id: int, request: Request):
    return _ok(await rpc("zc_api_cb_conocimiento_quitar", {"p_org": get_org(request), "p_id": nota_id}), "No se pudo quitar la nota.")
