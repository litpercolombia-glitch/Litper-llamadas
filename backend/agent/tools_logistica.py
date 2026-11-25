"""Herramientas del asistente para Logística y Clientes (Zynex contra entrega).

Con estas el asistente responde con números al día y abre el detalle: resumen de
la operación, pedidos por estado, ficha de un pedido y búsqueda de clientes.
Leer no pide confirmación; escribir (nota o caso) sí exige «Aplicar».
"""
from __future__ import annotations

import re
from typing import Any

from agent.tools import ToolError, UNTRUSTED_NATIVE, _org, register_tool

ESTADO_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÑáéíóúñ0-9_ ]{1,60}$")
FILTROS = {"todos", "atencion", "activos", "recompra", "riesgo"}


async def _rpc(fn: str, args: dict) -> Any:
    from fastapi import HTTPException
    from routes import zynex_motor
    try:
        return await zynex_motor.rpc(fn, args)
    except HTTPException as e:
        raise ToolError(str(e.detail))


async def tool_logistica_resumen(ctx, dias: int = 30) -> Any:
    org = _org(ctx)
    dias = max(1, min(90, int(dias or 30)))
    panel = await _rpc("zc_api_panel", {"p_org": org}) or {}
    met = await _rpc("zc_api_metricas", {"p_org": org, "p_dias": dias}) or {}
    cli = await _rpc("zc_api_clientes", {"p_org": org, "p_q": "", "p_filtro": "atencion", "p_limite": 1}) or {}
    return {"dias": dias, "modo": panel.get("modo"),
            "pedidos_por_estado": {t.get("titulo"): t.get("n") for t in panel.get("por_estado") or []},
            "metricas": {k.get("titulo"): k.get("valor") for k in met.get("kpis") or []},
            "transportadoras": met.get("transportadoras") or [],
            "clientes": cli.get("resumen") or {}, "ver_en": "/app/logistica"}


async def tool_logistica_pedidos(ctx, estado: str, limite: int = 30) -> Any:
    estado = (estado or "").strip().upper()
    if not ESTADO_RE.match(estado):
        raise ToolError("Indica el estado tal cual aparece en el resumen, por ejemplo NOVEDAD.")
    filas = await _rpc("zc_api_lista", {"p_org": _org(ctx), "p_clave": f"estado:{estado}",
                                        "p_limite": max(1, min(int(limite or 30), 100))}) or []
    return {"estado": estado, "total": len(filas), "ver_en": "/app/logistica",
            "pedidos": [{k: f.get(k) for k in ("pedido", "ciudad", "valor", "transportadora", "guia", "dias", "accion")}
                        for f in filas]}


async def tool_logistica_pedido(ctx, pedido: str) -> Any:
    num = re.sub(r"\D", "", str(pedido or ""))
    if not num or len(num) > 15:
        raise ToolError("Indica el número del pedido.")
    d = await _rpc("zc_api_pedido", {"p_org": _org(ctx), "p_pedido": int(num)})
    if not d:
        raise ToolError("No encontré ese pedido en tu espacio.")
    cli = d.get("cliente") or {}
    return {"pedido": d.get("pedido"), "dropi": (d.get("dropi") or {}).get("datos") or {},
            "movimientos": (d.get("movimientos") or [])[:10], "historial": (d.get("historial") or [])[:10],
            "cliente": {"resumen": cli.get("resumen"), "caso": cli.get("caso"), "notas": (cli.get("notas") or [])[:5]}}


async def tool_clientes_buscar(ctx, q: str = "", filtro: str = "todos", limite: int = 20) -> Any:
    if filtro not in FILTROS:
        raise ToolError("filtro debe ser: todos, atencion, activos, recompra o riesgo.")
    d = await _rpc("zc_api_clientes", {"p_org": _org(ctx), "p_q": (q or "").strip()[:60], "p_filtro": filtro,
                                       "p_limite": max(1, min(int(limite or 20), 50))}) or {}
    return {"resumen": d.get("resumen") or {}, "clientes": d.get("filas") or [], "ver_en": "/app/clientes"}


def _tel(tel: str) -> str:
    t = re.sub(r"\D", "", str(tel or ""))[-10:]
    if len(t) != 10:
        raise ToolError("Teléfono inválido: deben ser 10 dígitos.")
    return t


async def tool_cliente_nota(ctx, telefono: str, texto: str) -> Any:
    texto = (texto or "").strip()[:1000]
    if not texto:
        raise ToolError("Escribe la nota.")
    ok = await _rpc("zc_api_cliente_nota", {"p_org": _org(ctx), "p_tel": _tel(telefono), "p_texto": texto,
                                            "p_autor": "Asistente"})
    if ok is not True:
        raise ToolError("No se pudo guardar la nota: ese cliente no está en tu espacio.")
    return {"ok": True, "mensaje": "Nota guardada."}


async def tool_cliente_caso(ctx, telefono: str, estado: str, motivo: str = "") -> Any:
    if estado not in ("abierto", "resuelto"):
        raise ToolError("estado debe ser abierto o resuelto.")
    ok = await _rpc("zc_api_cliente_caso", {"p_org": _org(ctx), "p_tel": _tel(telefono), "p_estado": estado,
                                            "p_motivo": (motivo or "").strip()[:300], "p_autor": "Asistente"})
    if ok is not True:
        raise ToolError("No se pudo guardar: ese cliente no está en tu espacio.")
    return {"ok": True, "mensaje": "Queda para que lo atienda una persona." if estado == "abierto" else "Caso resuelto."}


register_tool("logistica_resumen", tool_logistica_resumen, {
    "name": "logistica_resumen",
    "description": "Cómo va la operación de envíos: pedidos por estado, métricas de los últimos "
                   "días (tasa de entrega, plata por rescatar, por transportadora) y clientes que necesitan a una "
                   "persona. Úsala para «cómo voy», «qué tengo pendiente» o cualquier número de logística.",
    "args": {"dias": "int? (1-90, por defecto 30)"}})
register_tool("logistica_pedidos", tool_logistica_pedidos, {
    "name": "logistica_pedidos",
    "description": "Lista los pedidos que están en un estado de envío, escrito tal cual aparece en el resumen "
                   "(ej. NOVEDAD, PENDIENTE CONFIRMACION, EN REPARTO), del más antiguo al más nuevo, con días en el estado.",
    "args": {"estado": "str", "limite": "int? (máx. 100)"}})
register_tool("logistica_pedido", tool_logistica_pedido, {
    "name": "logistica_pedido",
    "description": "Todo sobre un pedido por su número: estado, cliente, dirección, productos, movimientos, "
                   "lo que hizo el motor y las notas del equipo.",
    "args": {"pedido": "str"}})
register_tool("clientes_buscar", tool_clientes_buscar, {
    "name": "clientes_buscar",
    "description": "Busca clientes por nombre, teléfono o ciudad. filtro: atencion (necesitan a una persona), "
                   "activos (pedido en camino), recompra (2 o más compras), riesgo (han devuelto) o todos.",
    "args": {"q": "str?", "filtro": "str?", "limite": "int? (máx. 50)"}})
register_tool("cliente_nota", tool_cliente_nota, {
    "name": "cliente_nota",
    "description": "Guarda una nota del equipo en la ficha de un cliente (por teléfono de 10 dígitos).",
    "args": {"telefono": "str", "texto": "str"}}, requires_confirm=True)
register_tool("cliente_caso", tool_cliente_caso, {
    "name": "cliente_caso",
    "description": "Marca a un cliente para que lo atienda una persona (estado=abierto, con motivo) o cierra su "
                   "caso (estado=resuelto).",
    "args": {"telefono": "str", "estado": "str", "motivo": "str?"}}, requires_confirm=True)

# Estos resultados traen texto de terceros (nombres, direcciones, notas): dato, no orden.
UNTRUSTED_NATIVE.update({"logistica_pedidos", "logistica_pedido", "clientes_buscar"})
