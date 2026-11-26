"""Zynex · Traer mi operación — carga el reporte de órdenes de Dropi del cliente.

El cliente sube su archivo de Dropi (Excel o CSV) y elige cuántos días traer
(30, 60 o 90). Los pedidos quedan en SU espacio: alimentan Clientes y Métricas.
No crea tareas ni envía mensajes: solo guarda la historia para medir y mejorar.

PUERTA DE ENTRADA (sin API de Dropi): cada cliente tiene una dirección propia
(`/entrada/{token}`) a la que su automatización (n8n, Chatea Pro u otra) envía
los pedidos tal cual los lee. El token identifica al cliente; nada del cuerpo
decide a qué cuenta entra.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from deps import get_org, require_api_key
from dropi_import import _clean_str, _read_sheet_df, detect_column_map, parse_sheet
from routes import zynex_motor

router = APIRouter(prefix="/zcall/motor/operacion", tags=["zynex-operacion"])

MAX_BYTES = 15 * 1024 * 1024
LOTE = 500  # con el detalle completo de cada pedido, lotes más pequeños
DIAS_OK = (30, 60, 90)


def columnas_por_pedido(data: bytes, nombre: str) -> dict[str, dict]:
    """Todas las columnas del reporte (primera fila de cada orden), tal cual vienen de Dropi."""
    df = _read_sheet_df(data, nombre, None).fillna("")
    id_col = next((raw for raw, canon in detect_column_map(list(df.columns)).items() if canon == "order_id"), None)
    if not id_col:
        return {}
    out: dict[str, dict] = {}
    for _, fila in df.iterrows():
        pedido = re.sub(r"\D", "", _clean_str(fila[id_col]))
        if pedido and pedido not in out:
            out[pedido] = {str(c)[:60]: _clean_str(fila[c])[:300] for c in df.columns if _clean_str(fila[c])}
    return out


def datos_de_reporte(e: dict, crudo: dict | None = None) -> dict:
    """Todo lo que trae el reporte de Dropi para la ficha del pedido."""
    d = {
        "direccion": e.get("address"), "departamento": e.get("department"), "tipo_envio": e.get("payment_type"),
        "vendedor": e.get("seller"), "tienda": e.get("store"), "fecha_guia": e.get("office_arrival_date"),
        "novedad": e.get("novedad"),
        "productos": [{"producto": i.get("product"), "variacion": i.get("variation"), "sku": i.get("sku"),
                       "producto_id": i.get("product_id"), "cantidad": i.get("qty")} for i in (e.get("items") or [])][:50],
        "otros": dict(list((crudo or {}).items())[:80]),
    }
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def filas_de(consolidado: list[dict], dias: int, hoy: date | None = None,
             crudo: dict[str, dict] | None = None) -> tuple[list[dict], dict]:
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
        filas.append({"datos": datos_de_reporte(e, (crudo or {}).get(pedido)), **{
            "pedido": pedido, "estado": estado,
            "telefono": str(e.get("customer_phone") or ""), "nombre": str(e.get("customer_name") or ""),
            "ciudad": str(e.get("city") or ""), "transportadora": str(e.get("carrier_raw") or ""),
            "guia": str(e.get("tracking_number") or ""),
            "valor": str(int(round(float(total)))) if isinstance(total, (int, float)) and total > 0 else None,
            "creado": creado,
        }})
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
    try:
        crudo = columnas_por_pedido(data, file.filename or "")
    except Exception:  # noqa: BLE001  (el detalle es un extra: si falla, se guardan los datos básicos)
        crudo = {}
    filas, desc = filas_de(res.consolidated, dias, crudo=crudo)
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


# ------------------------------------------------------------------ puerta de entrada
ENTRADA_MAX = 500            # pedidos por envío
ENTRADA_BYTES = 2 * 1024 * 1024
ENTRADA_POR_MIN = 120        # envíos por minuto y por cliente
_ALIAS = {
    "pedido": ("pedido", "order_id", "id_orden", "orden", "id"),
    "estado": ("estado", "status", "estatus", "state"),
    "telefono": ("telefono", "phone", "celular", "customer_phone", "telefono_cliente"),
    "nombre": ("nombre", "customer_name", "cliente", "name", "nombre_cliente"),
    "ciudad": ("ciudad", "city", "ciudad_destino"),
    "valor": ("valor", "total_order", "total", "total_amount", "valor_total"),
    "transportadora": ("transportadora", "carrier", "shipping_company", "distribution_company", "transportadora_nombre"),
    "guia": ("guia", "shipping_guide", "tracking_number", "numero_guia", "tracking"),
    "creado": ("creado", "created_at", "fecha", "order_date", "fecha_creacion"),
}
_USADOS = {a for lista in _ALIAS.values() for a in lista}


def _texto(v) -> str:
    """Valor simple como texto; de un objeto toma su nombre (p. ej. la transportadora)."""
    if isinstance(v, dict):
        v = v.get("name") or v.get("nombre") or ""
    return "" if v is None or isinstance(v, (list, dict)) else str(v).strip()


def fila_de_entrada(o: dict) -> dict | None:
    """Un pedido como venga (Dropi, n8n, Chatea Pro) → fila para la base. None si no trae pedido y estado."""
    if not isinstance(o, dict):
        return None
    bajo = {str(k).strip().lower(): v for k, v in o.items()}
    f = {campo: next((_texto(bajo[a]) for a in alias if _texto(bajo.get(a))), "") for campo, alias in _ALIAS.items()}
    if not f["nombre"] and _texto(bajo.get("surname")):
        f["nombre"] = _texto(bajo.get("surname"))
    elif _texto(bajo.get("surname")) and _texto(bajo.get("name")) == f["nombre"]:
        f["nombre"] = f"{f['nombre']} {_texto(bajo.get('surname'))}"
    f["pedido"] = re.sub(r"\D", "", f["pedido"])[:15]
    f["estado"] = f["estado"].upper()[:60]
    if not f["pedido"] or not f["estado"]:
        return None
    f["telefono"] = re.sub(r"\D", "", f["telefono"])[-10:]
    f["creado"] = f["creado"][:10] if re.match(r"^\d{4}-\d{2}-\d{2}", f["creado"]) else None
    try:
        f["valor"] = str(int(round(float(f["valor"])))) if f["valor"] else None
    except ValueError:
        f["valor"] = None
    for k in ("nombre", "ciudad", "transportadora", "guia"):
        f[k] = f[k][:120]
    otros = {str(k)[:60]: (v if isinstance(v, (list, dict)) else _texto(v)[:300])
             for k, v in list(o.items())[:80] if str(k).strip().lower() not in _USADOS and v not in (None, "", [], {})}
    f["datos"] = o["datos"] if isinstance(o.get("datos"), dict) else otros
    return f


def pedidos_del_cuerpo(cuerpo) -> list:
    if isinstance(cuerpo, list):
        return cuerpo
    if isinstance(cuerpo, dict):
        for k in ("pedidos", "orders", "objects", "items", "data"):
            if isinstance(cuerpo.get(k), list):
                return cuerpo[k]
        return [cuerpo]
    return []


@router.post("/entrada/{org_token}",
             summary="Puerta de entrada de pedidos de UN cliente (su token va en la dirección). "
                     "Recibe uno o varios pedidos como los lea su automatización. No envía mensajes.")
async def entrada(org_token: str, request: Request):
    import json
    import ratelimit
    import webhook_tokens
    org = await webhook_tokens.org_for_token(org_token)
    if not org:
        raise HTTPException(404, "Dirección no válida.")
    if ratelimit.count(f"entrada:{org}", 60) >= ENTRADA_POR_MIN:
        raise HTTPException(429, "Demasiados envíos seguidos. Espera un minuto.")
    ratelimit.hit(f"entrada:{org}", 60)
    crudo = await request.body()
    if len(crudo) > ENTRADA_BYTES:
        raise HTTPException(413, "Envío demasiado grande. Manda máximo 500 pedidos por vez.")
    try:
        cuerpo = json.loads(crudo or b"null")
    except ValueError:
        raise HTTPException(400, "El cuerpo debe ser JSON.")
    lista = pedidos_del_cuerpo(cuerpo)
    if len(lista) > ENTRADA_MAX:
        raise HTTPException(413, "Manda máximo 500 pedidos por vez.")
    filas = [f for f in (fila_de_entrada(o) for o in lista) if f]
    if not filas:
        raise HTTPException(400, "No llegó ningún pedido con número y estado.")
    r = await zynex_motor.rpc("zc_api_pedidos_importar", {"p_org": org, "p_filas": filas, "p_fuente": "entrada_automatica"})
    if not isinstance(r, dict) or not r.get("ok"):
        raise HTTPException(409, "Activa tu espacio en Logística antes de enviar pedidos.")
    return {"ok": True, "recibidos": len(lista), "guardados": int(r.get("guardados") or 0),
            "descartados": len(lista) - len(filas)}


@router.get("/entrada", dependencies=[Depends(require_api_key)],
            summary="La dirección de entrada de ESTE cliente, para pegarla en su automatización.")
async def entrada_url(request: Request):
    import webhook_tokens
    token = await webhook_tokens.token_for(get_org(request))
    return {"url": f"{webhook_tokens.public_base(request)}/api/zcall/motor/operacion/entrada/{token}",
            "metodo": "POST", "formato": "JSON: un pedido, una lista o {pedidos:[...]}. Mínimo: pedido y estado.",
            "maximo_por_envio": ENTRADA_MAX, "nota": "Quien tenga esta dirección puede enviar pedidos a tu cuenta. No la compartas."}


class PedirIn(BaseModel):
    dias: int = 90


@router.post("/pedir", dependencies=[Depends(require_api_key)],
             summary="Deja una solicitud para que el Claude del cliente traiga su operación de Dropi.")
async def pedir(p: PedirIn, request: Request):
    if p.dias not in DIAS_OK:
        raise HTTPException(400, "Elige 30, 60 o 90 días.")
    r = await zynex_motor.rpc("zc_api_solicitud_crear", {"p_org": get_org(request), "p_tipo": "traer_operacion",
                                                        "p_params": {"dias": p.dias}, "p_origen": "app"})
    if not isinstance(r, dict) or not r.get("ok"):
        raise HTTPException(400, "Activa tu espacio en Logística antes de pedir tu operación.")
    return {"ok": True, "id": r.get("id"), "partes": r.get("partes"),
            "mensaje": f"Listo: {r.get('partes') or 1} semanas por traer. Ahora dile a tu Claude: «Sincroniza mi Zynex»."}


@router.post("/solicitudes/{sid}/terminar", dependencies=[Depends(require_api_key)],
             summary="Da por terminada una petición a Claude (y las demás semanas de ese mismo pedido).")
async def terminar(sid: int, request: Request):
    r = await zynex_motor.rpc("zc_api_solicitud_cerrar", {"p_org": get_org(request), "p_id": int(sid)})
    if not isinstance(r, dict) or not r.get("ok"):
        raise HTTPException(400, "Esa petición ya estaba cerrada.")
    return {"ok": True, "cerradas": r.get("cerradas"), "mensaje": "Listo: la petición quedó cerrada. Lo que ya llegó se queda guardado."}


@router.get("/solicitudes", dependencies=[Depends(require_api_key)],
            summary="Solicitudes a Claude y su avance (no genera solicitudes nuevas).")
async def solicitudes(request: Request):
    r = await zynex_motor.rpc("zc_api_solicitudes", {"p_org": get_org(request), "p_generar": False})
    return {"solicitudes": (r or {}).get("solicitudes") or []}
