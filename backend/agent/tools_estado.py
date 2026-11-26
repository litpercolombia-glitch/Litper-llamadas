"""Herramienta del asistente: cómo están las conexiones de ESTA cuenta.

Sirve para que el asistente no responda a ciegas cuando el usuario comenta algo
como «ya conecté Dropi»: mira el estado real (conectado o no, última lectura,
error, pedidos guardados) y lo cuenta. Solo lee; nunca devuelve llaves ni permisos.
"""
from __future__ import annotations

from typing import Any

from agent.tools import _org, register_tool
from db import get_db


async def tool_conexiones_estado(ctx) -> Any:
    org = _org(ctx)
    d = await get_db().dropi_conexiones.find_one({"org_id": org}, {"_id": 0}) or {}
    dropi = {"conectado": bool(d.get("conectado")) and not d.get("necesita_reconectar"),
             "necesita_reconectar": bool(d.get("necesita_reconectar")),
             "ultima_lectura": d.get("ultimo_sync"), "pedidos_ultima_lectura": d.get("ultimo_guardados"),
             "ultimo_error": d.get("ultimo_error") or "", "lee_cada_min": 5, "permiso": "solo lectura de pedidos"}
    base: dict = {}
    try:
        from routes import zynex_motor
        c = await zynex_motor.rpc("zc_api_dias", {"p_org": org, "p_dias": 2}) or {}
        base = {"pedidos_guardados": c.get("total_pedidos"), "datos_al_corte": c.get("ultima_actualizacion"),
                "creados_hoy_y_ayer": c.get("dias") or []}
    except Exception:  # noqa: BLE001 — sin motor de logística se informa solo la conexión
        pass
    ia = False
    try:
        from agent.tope_ia import tiene_llave_propia
        ia = await tiene_llave_propia(org)
    except Exception:  # noqa: BLE001
        pass
    return {"dropi": dropi, "base_de_pedidos": base, "ia_con_llave_propia": ia,
            "donde_se_conecta": "/app/logistica (tarjeta de Dropi) y /app/conexiones"}


register_tool("conexiones_estado", tool_conexiones_estado, {
    "name": "conexiones_estado",
    "description": "Estado real de las conexiones de esta cuenta: si la tienda de pedidos está conectada, cuándo fue la "
                   "última lectura, si hubo error, cuántos pedidos hay guardados y a qué hora es el último corte. Úsala "
                   "cuando el usuario diga que conectó, activó o configuró algo, o pregunte si algo está funcionando.",
    "args": {}})
