"""Conector de Claude (MCP remoto, JSON-RPC por HTTP) — uno por cliente.

Cada cliente genera su URL en Conexiones → «Conectar Claude» y la pega en
Claude → Conectores. Así Claude hace de puente con Dropi (que no tiene API):
lee pedidos con el conector de Dropi del usuario y los sube aquí; luego lee los
resultados de las llamadas para actualizar Dropi.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from db import get_db
from routes import zynex_call as zc
from routes import zynex_motor

router = APIRouter(prefix="/mcp", tags=["claude-mcp"])
PROTO = "2025-06-18"

TOOLS = [
    {"name": "zynex_estado",
     "description": "Estado de Zynex Call del negocio: conexiones, modo, cola y métricas de llamadas.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "zynex_subir_pedidos",
     "description": ("Sube pedidos leídos de Dropi para que los agentes de voz llamen según el estado "
                     "(PENDIENTE CONFIRMACION, NOVEDAD, EN OFICINA/PARA RECLAMAR EN OFICINA, EN REPARTO, DEVOLUCION). "
                     "Cada pedido: dropi_order_id, estado_dropi, cliente, telefono, valor, producto, direccion, ciudad, "
                     "transportadora, guia, novedad. Máximo 500 por llamada."),
     "inputSchema": {"type": "object", "required": ["pedidos"], "properties": {"pedidos": {
         "type": "array", "items": {"type": "object", "properties": {k: {"type": "string"} for k in (
             "dropi_order_id", "estado_dropi", "cliente", "telefono", "valor", "producto", "direccion",
             "ciudad", "transportadora", "guia", "novedad")}, "required": ["dropi_order_id", "estado_dropi"]}}}}},
    {"name": "zynex_cola",
     "description": "Llamadas en cola o bloqueadas (y por qué), para revisar antes de despachar.",
     "inputSchema": {"type": "object", "properties": {"limite": {"type": "integer", "default": 50}}}},
    {"name": "zynex_despachar",
     "description": "Despacha ya las llamadas pendientes dentro de la ventana (respeta modo prueba).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "zynex_resultados",
     "description": ("Resultados de llamadas que aún no se han escrito en Dropi (sync_dropi=pendiente): "
                     "dropi_order_id, resultado, nota, dirección corregida. Úsalos para actualizar Dropi."),
     "inputSchema": {"type": "object", "properties": {"limite": {"type": "integer", "default": 50}}}},
    {"name": "zynex_marcar_dropi",
     "description": "Marca llamadas como ya actualizadas en Dropi después de que Claude hizo el cambio.",
     "inputSchema": {"type": "object", "required": ["ids"], "properties": {
         "ids": {"type": "array", "items": {"type": "string"}}, "nota": {"type": "string"}}}},
    {"name": "zynex_logistica_solicitudes",
     "description": ("Lo que Zynex le pide a Claude traer de Dropi (ida). Devuelve solicitudes pendientes con su "
                     "solicitud_id, el tipo (traer_operacion o refrescar_pedidos), los parámetros y las instrucciones. "
                     "Cúmplelas con el conector de Dropi del usuario y entrega con zynex_logistica_entregar."),
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "zynex_logistica_entregar",
     "description": ("Entrega a Zynex pedidos leídos de Dropi (vuelta). Alimenta Clientes, Métricas, el panel de "
                     "Logística y la ficha de cada pedido. Básico: pedido (id de la orden), estado, telefono, nombre, "
                     "ciudad, valor, transportadora, guia, creado (AAAA-MM-DD). Si tienes el detalle de get_order, "
                     "manda también direccion, departamento, documento, metodo_pago, actualizado, notas, novedad y "
                     "productos [{producto, variacion, cantidad, precio, subtotal, producto_id}]; cualquier otro dato "
                     "en otros {nombre: valor}. Máximo 500 por llamada. Si respondes a una solicitud manda "
                     "solicitud_id, y final=true en la última página de esa solicitud. No envía mensajes a clientes."),
     "inputSchema": {"type": "object", "required": ["pedidos"], "properties": {
         "pedidos": {"type": "array", "items": {"type": "object", "additionalProperties": True, "properties": {
             **{k: {"type": "string"} for k in ("pedido", "estado", "telefono", "nombre", "ciudad", "valor",
                                                 "transportadora", "guia", "creado", "direccion", "departamento",
                                                 "documento", "metodo_pago", "actualizado", "notas", "novedad")},
             "productos": {"type": "array", "items": {"type": "object"}},
             "otros": {"type": "object"}},
             "required": ["pedido", "estado"]}},
         "solicitud_id": {"type": "integer"}, "final": {"type": "boolean", "default": False}}}},
    {"name": "zynex_logistica_resumen",
     "description": ("Resumen de la operación en Zynex: pedidos por estado, métricas de los últimos días (tasa de "
                     "entrega, plata por rescatar, por transportadora) y clientes que necesitan a una persona."),
     "inputSchema": {"type": "object", "properties": {"dias": {"type": "integer", "default": 30}}}},
]

CAMPOS_PEDIDO = ("pedido", "estado", "telefono", "nombre", "ciudad", "valor", "transportadora", "guia", "creado")
MAX_DATOS = 20000  # bytes de detalle por pedido


def _limpio(v: Any, nivel: int = 0) -> Any:
    """Recorta el detalle de Dropi a algo seguro de guardar (textos cortos, listas y objetos acotados)."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, list):
        return [_limpio(x, nivel + 1) for x in v[:50]] if nivel < 3 else None
    if isinstance(v, dict):
        return {str(k)[:60]: _limpio(x, nivel + 1) for k, x in list(v.items())[:80]} if nivel < 3 else None
    return str(v)[:500]


def datos_extra(p: dict) -> dict:
    """Todo lo que Claude trae de Dropi aparte de los campos básicos va a la ficha del pedido."""
    d = {k: _limpio(v) for k, v in p.items() if k not in CAMPOS_PEDIDO and v not in (None, "", [], {})}
    return d if len(json.dumps(d, ensure_ascii=False, default=str)) <= MAX_DATOS else {}


def _txt(obj: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False, default=str)}]}


async def _call(org: str, name: str, args: dict) -> dict:
    db = get_db()
    if name == "zynex_estado":
        cfg = await zc.asegurar(org)
        n = {e: await db.zc_llamadas.count_documents({"org_id": org, "estado": e})
             for e in ("en_cola", "bloqueada", "llamando", "terminada")}
        pend = await db.zc_llamadas.count_documents({"org_id": org, "sync_dropi": "pendiente"})
        return _txt({"modo": cfg.get("modo"), "ventana": f"{cfg.get('ventana_ini')}–{cfg.get('ventana_fin')}",
                     "ventana_ahora": zc.en_ventana(cfg), "llamadas": n, "pendientes_dropi": pend,
                     "elevenlabs": bool(await zc._llave(org, "elevenlabs")),
                     "chatea": bool(await zc._llave(org, "chatea_pro")), "numero": bool(cfg.get("phone_number_id"))})
    if name == "zynex_subir_pedidos":
        pedidos = args.get("pedidos") or []
        if not isinstance(pedidos, list):
            raise ValueError("pedidos debe ser una lista")
        return _txt(await zc.subir_pedidos(org, pedidos))
    if name == "zynex_cola":
        lim = max(1, min(200, int(args.get("limite") or 50)))
        filas = [x async for x in db.zc_llamadas.find(
            {"org_id": org, "estado": {"$in": ["en_cola", "bloqueada"]}},
            {"_id": 0, "id": 1, "agente": 1, "dropi_order_id": 1, "estado": 1, "motivo_estado": 1,
             "proxima_llamada": 1, "intentos": 1}).sort("creado", -1).limit(lim)]
        return _txt(filas)
    if name == "zynex_despachar":
        return _txt(await zc.despachar(org))
    if name == "zynex_resultados":
        lim = max(1, min(200, int(args.get("limite") or 50)))
        filas = [x async for x in db.zc_llamadas.find(
            {"org_id": org, "sync_dropi": "pendiente"},
            {"_id": 0, "id": 1, "agente": 1, "dropi_order_id": 1, "resultado": 1, "nota": 1,
             "direccion_corregida": 1, "actualizado": 1}).sort("actualizado", -1).limit(lim)]
        return _txt(filas)
    if name == "zynex_marcar_dropi":
        ids = [str(i) for i in (args.get("ids") or [])][:500]
        r = await db.zc_llamadas.update_many({"org_id": org, "id": {"$in": ids}},
                                             {"$set": {"sync_dropi": "ok", "nota_dropi": (args.get("nota") or "")[:200],
                                                       "actualizado": zc._iso()}})
        await zc.evento(org, "claude_marcar_dropi", {"n": r.modified_count})
        return _txt({"marcadas": r.modified_count})
    if name == "zynex_logistica_solicitudes":
        return _txt(await zynex_motor.rpc("zc_api_solicitudes", {"p_org": org, "p_generar": True}))
    if name == "zynex_logistica_entregar":
        pedidos = args.get("pedidos") or []
        if not isinstance(pedidos, list) or not pedidos:
            raise ValueError("pedidos debe ser una lista con al menos un pedido")
        if len(pedidos) > 500:
            raise ValueError("máximo 500 pedidos por llamada: entrega por partes")
        filas = [{**{k: (None if p.get(k) is None else str(p.get(k))[:200]) for k in CAMPOS_PEDIDO},
                  "datos": datos_extra(p)} for p in pedidos if isinstance(p, dict)]
        sol = args.get("solicitud_id")
        r = await zynex_motor.rpc("zc_api_entregar", {"p_org": org, "p_filas": filas,
                                                     "p_solicitud": int(sol) if str(sol or "").isdigit() else None,
                                                     "p_final": bool(args.get("final"))})
        await zc.evento(org, "claude_entrega_logistica", {"n": len(filas)})
        return _txt(r)
    if name == "zynex_logistica_resumen":
        dias = max(1, min(90, int(args.get("dias") or 30)))
        panel = await zynex_motor.rpc("zc_api_panel", {"p_org": org})
        met = await zynex_motor.rpc("zc_api_metricas", {"p_org": org, "p_dias": dias})
        cli = await zynex_motor.rpc("zc_api_clientes", {"p_org": org, "p_q": "", "p_filtro": "atencion", "p_limite": 1})
        return _txt({"vinculado": bool((panel or {}).get("vinculado")), "modo": (panel or {}).get("modo"),
                     "pedidos_por_estado": {t.get("titulo"): t.get("n") for t in (panel or {}).get("por_estado") or []},
                     "metricas": {k.get("titulo"): k.get("valor") for k in (met or {}).get("kpis") or []},
                     "transportadoras": (met or {}).get("transportadoras") or [],
                     "clientes": (cli or {}).get("resumen") or {}})
    raise ValueError(f"Herramienta desconocida: {name}")


def _rpc(id_: Any, result: Any = None, error: dict | None = None) -> dict:
    out: dict = {"jsonrpc": "2.0", "id": id_}
    if error:
        out["error"] = error
    else:
        out["result"] = result
    return out


@router.get("/{token}", summary="Info del conector (para comprobar la URL).")
async def mcp_get(token: str):
    if not await zc.org_por_token_mcp(token):
        raise HTTPException(401, "Token no válido. Genera uno nuevo en Conexiones → Conectar Claude.")
    return {"ok": True, "servidor": "Zynex OS", "protocolo": PROTO, "herramientas": [t["name"] for t in TOOLS]}


@router.post("/{token}", summary="Endpoint MCP (JSON-RPC 2.0, streamable HTTP sin sesión).")
async def mcp_post(token: str, request: Request):
    org = await zc.org_por_token_mcp(token)
    if not org:
        return JSONResponse(_rpc(None, error={"code": -32001, "message": "Token no válido"}), status_code=401)
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(_rpc(None, error={"code": -32700, "message": "JSON inválido"}), status_code=400)
    msgs = body if isinstance(body, list) else [body]
    out = []
    for m in msgs:
        mid, method, params = m.get("id"), m.get("method"), m.get("params") or {}
        if mid is None:  # notificación (p. ej. notifications/initialized)
            continue
        try:
            if method == "initialize":
                res = {"protocolVersion": params.get("protocolVersion") or PROTO,
                       "capabilities": {"tools": {"listChanged": False}},
                       "serverInfo": {"name": "zynex-os", "version": "1.0.0"},
                       "instructions": ("Zynex OS para ventas contra entrega con Dropi. Logística (ida y vuelta): "
                                        "zynex_logistica_solicitudes dice qué traer de Dropi → léelo con el conector "
                                        "de Dropi → zynex_logistica_entregar lo guarda → zynex_logistica_resumen "
                                        "muestra cómo va. Trabaja una solicitud (una semana) a la vez y cierra cada "
                                        "una con final=true; si no alcanzas, di cuántas faltan y que el usuario "
                                        "escriba de nuevo «Sincroniza mi Zynex». Llamadas: zynex_subir_pedidos → zynex_despachar → "
                                        "zynex_resultados → actualiza Dropi → zynex_marcar_dropi.")}
            elif method == "ping":
                res = {}
            elif method == "tools/list":
                res = {"tools": TOOLS}
            elif method == "tools/call":
                res = await _call(org, params.get("name", ""), params.get("arguments") or {})
            else:
                out.append(_rpc(mid, error={"code": -32601, "message": f"Método no soportado: {method}"}))
                continue
            out.append(_rpc(mid, res))
        except (ValueError, HTTPException) as e:
            msg = e.detail if isinstance(e, HTTPException) else str(e)
            out.append(_rpc(mid, {"content": [{"type": "text", "text": f"Error: {msg}"}], "isError": True}))
    if not out:
        return Response(status_code=202)
    return JSONResponse(out if isinstance(body, list) else out[0])
