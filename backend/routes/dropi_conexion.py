"""Zynex · Conectar Dropi sin API — el cliente inicia sesión en Dropi UNA vez.

Dropi no entrega API, pero sí un conector público con inicio de sesión
(el mismo que usan los asistentes de IA). Aquí Zynex se conecta a ese conector
en nombre del cliente:

  1. «Conectar Dropi» → se abre la página de Dropi; el cliente inicia sesión
     allá (Zynex nunca ve su contraseña).
  2. Dropi devuelve un permiso de SOLO LECTURA de pedidos, que se guarda cifrado.
  3. Cada pocos minutos Zynex lee los pedidos recientes y los guarda en la
     cuenta de ese cliente. Sin Claude, sin n8n, sin tareas programadas.

Aislamiento: el permiso se guarda por org; la vuelta de Dropi se ata al org con
un código de un solo uso que vence en 10 minutos. Ningún permiso sale del backend.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from db import get_db
from deps import get_org, require_api_key

log = logging.getLogger("dropi.conexion")
router = APIRouter(prefix="/dropi", tags=["zynex-operacion"])

MCP_URL = os.environ.get("DROPI_MCP_URL", "https://mcp.dropi.co/mcp")
AUTORIZAR = os.environ.get("DROPI_OAUTH_AUTHORIZE", "https://mcp.dropi.co/login/authorize")
TOKEN = os.environ.get("DROPI_OAUTH_TOKEN", "https://mcp.dropi.co/oauth/token")
REGISTRO = os.environ.get("DROPI_OAUTH_REGISTER", "https://mcp.dropi.co/oauth/register")
PERMISOS = os.environ.get("DROPI_SCOPES", "read:orders")     # solo lectura de pedidos
PAGINA = 50
MAX_PAGINAS = 10
CABECERA = re.compile(r"^\s*\w+\[(\d+)\]\{([^}]*)\}:\s*$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cifrar(texto: str) -> str:
    from org_credentials import _fernet
    return _fernet().encrypt(texto.encode()).decode()


def _descifrar(ct: str) -> str:
    from org_credentials import _fernet
    return _fernet().decrypt(ct.encode()).decode()


def _app_url() -> str:
    return (os.environ.get("ZYNEX_APP_URL") or "https://call.zynexapp.com").rstrip("/")


def _vuelta_url(request: Request | None = None) -> str:
    import webhook_tokens
    return f"{webhook_tokens.public_base(request)}/api/zcall/motor/operacion/dropi/vuelta"


async def _post(url: str, *, json_body: dict | None = None, form: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as cli:
        r = await cli.post(url, json=json_body, data=form)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


async def _cliente(redirect: str) -> str:
    """Identificador de Zynex ante Dropi (se registra una sola vez por dirección de vuelta)."""
    db = get_db()
    doc = await db.dropi_oauth_cliente.find_one({"redirect": redirect}, {"_id": 0})
    if doc and doc.get("client_id"):
        return doc["client_id"]
    r = await _post(REGISTRO, json_body={
        "client_name": "Zynex", "redirect_uris": [redirect], "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"], "token_endpoint_auth_method": "none", "scope": PERMISOS})
    cid = str(r.get("client_id") or "")
    if not cid:
        raise RuntimeError("registro sin client_id")
    await db.dropi_oauth_cliente.update_one({"redirect": redirect}, {"$set": {"redirect": redirect, "client_id": cid,
                                            "created_at": _now().isoformat()}}, upsert=True)
    return cid


# ------------------------------------------------------------------ lectura
def pedidos_de_texto(texto: str) -> list[dict]:
    """Lo que devuelve el conector → lista de pedidos. Entiende JSON y la tabla compacta
    `items[N]{campo,campo}:` seguida de N filas separadas por comas."""
    texto = (texto or "").strip()
    if not texto:
        return []
    if texto[0] in "[{":
        try:
            return _lista_de_pedidos(json.loads(texto))
        except ValueError:
            pass
    lineas = texto.splitlines()
    for i, linea in enumerate(lineas):
        m = CABECERA.match(linea)
        if not m:
            continue
        campos = [c.strip() for c in m.group(2).split(",")]
        filas = [x for x in lineas[i + 1:i + 1 + int(m.group(1))] if x.strip()]
        out = []
        for fila in csv.reader(io.StringIO("\n".join(x.strip() for x in filas)), skipinitialspace=True):
            if len(fila) == len(campos):
                out.append(dict(zip(campos, fila)))
        return out
    return []


def _lista_de_pedidos(dato, nivel: int = 0) -> list[dict]:
    """Primera lista de objetos que aparezca en la respuesta, esté al nivel que esté."""
    if isinstance(dato, list):
        objs = [o for o in dato if isinstance(o, dict)]
        if objs or not dato:
            return objs
        return []
    if isinstance(dato, dict) and nivel < 4:
        for v in dato.values():
            if isinstance(v, (list, dict)):
                r = _lista_de_pedidos(v, nivel + 1)
                if r:
                    return r
        if nivel == 0 and any(k in dato for k in ("order_id", "id", "pedido")):
            return [dato]
    return []


def _forma(texto: str, truncado: bool) -> str:
    """Cómo viene una respuesta que no se pudo leer: tamaño y comienzo, sin cifras ni datos de clientes."""
    cab = re.sub(r"\d", "9", (texto or "")[:90]).replace("\n", "⏎")
    return f"sin_leer largo={len(texto or '')} truncado={truncado} inicio={cab}"


async def _guardar_tokens(org: str, tok: dict, client_id: str, anterior: dict | None = None) -> None:
    acceso = str(tok.get("access_token") or "")
    if not acceso:
        raise RuntimeError("sin access_token")
    refresco = str(tok.get("refresh_token") or "")
    vence = _now() + timedelta(seconds=max(60, int(tok.get("expires_in") or 3600)))
    cambios = {"org_id": org, "client_id": client_id, "acceso_ct": _cifrar(acceso), "vence": vence.isoformat(),
               "conectado": True, "necesita_reconectar": False, "actualizado": _now().isoformat()}
    if refresco:
        cambios["refresco_ct"] = _cifrar(refresco)
    elif anterior and anterior.get("refresco_ct"):
        cambios["refresco_ct"] = anterior["refresco_ct"]
    await get_db().dropi_conexiones.update_one({"org_id": org}, {"$set": cambios}, upsert=True)


async def _acceso(org: str, forzar: bool = False) -> str | None:
    """Permiso vigente del cliente; lo renueva si venció. None si hay que volver a conectar."""
    db = get_db()
    doc = await db.dropi_conexiones.find_one({"org_id": org, "conectado": True}, {"_id": 0})
    if not doc:
        return None
    if not forzar and (doc.get("vence") or "") > (_now() + timedelta(seconds=60)).isoformat():
        return _descifrar(doc["acceso_ct"])
    if not doc.get("refresco_ct"):
        await db.dropi_conexiones.update_one({"org_id": org}, {"$set": {"necesita_reconectar": True}})
        return None
    try:
        tok = await _post(TOKEN, form={"grant_type": "refresh_token", "refresh_token": _descifrar(doc["refresco_ct"]),
                                       "client_id": doc["client_id"], "resource": MCP_URL})
        await _guardar_tokens(org, tok, doc["client_id"], doc)
        return str(tok["access_token"])
    except Exception as e:  # noqa: BLE001 — sin secretos en el log
        log.warning("Dropi no renovó el permiso (org=%s): %s", org, type(e).__name__)
        await db.dropi_conexiones.update_one({"org_id": org}, {"$set": {"necesita_reconectar": True}})
        return None


_NOTAS: dict[str, str] = {}
BARRIDO_DIAS = 30       # hasta dónde se revisan cambios de estado de pedidos viejos


async def _latido(org: str, ok: bool, detalle: str) -> None:
    """Deja rastro de cada lectura (sin secretos) para poder ver si la conexión está sana."""
    try:
        from routes import zynex_motor
        await zynex_motor.rpc("zc_api_latido", {"p_org": org, "p_fuente": "dropi_conector", "p_ok": ok, "p_detalle": detalle[:300]})
    except Exception:  # noqa: BLE001 — el rastro nunca tumba la lectura
        pass


async def _leer_rango(org: str, acceso: str, desde: str, hasta: str) -> tuple[int, int, str]:
    """Lee y guarda los pedidos creados entre dos fechas. Devuelve (leídos, guardados, permiso vigente)."""
    import mcp_client
    from routes import zynex_motor
    from routes.zynex_importar import fila_de_entrada
    args = {"from": desde, "until": hasta, "result_number": PAGINA}
    leidos = guardados = 0
    for pagina in range(MAX_PAGINAS):
        try:
            r = await mcp_client.call_tool({"url": MCP_URL, "auth_type": "bearer", "secret": acceso},
                                           "list_orders", {**args, "start": pagina * PAGINA})
        except Exception as e:  # noqa: BLE001
            if "401" not in str(e) or pagina:
                raise
            acceso = await _acceso(org, forzar=True)
            if not acceso:
                raise RuntimeError("reconectar")
            r = await mcp_client.call_tool({"url": MCP_URL, "auth_type": "bearer", "secret": acceso},
                                           "list_orders", {**args, "start": 0})
        if r.get("is_error"):
            raise RuntimeError("Dropi respondió con error: " + str(r.get("text") or "")[:120])
        pedidos = pedidos_de_texto(r.get("text") or "")
        if not pedidos and pagina == 0:
            _NOTAS[org] = _forma(r.get("text") or "", bool(r.get("truncated")))   # para diagnosticar, sin datos
        leidos += len(pedidos)
        filas = [f for f in (fila_de_entrada(o) for o in pedidos) if f]
        if filas:
            g = await zynex_motor.rpc("zc_api_pedidos_importar", {"p_org": org, "p_filas": filas, "p_fuente": "dropi_conector"})
            if not isinstance(g, dict) or not g.get("ok"):
                raise RuntimeError("espacio sin activar")
            guardados += int(g.get("guardados") or 0)
        if len(pedidos) < PAGINA:
            break
    return leidos, guardados, acceso


async def sincronizar(org: str, dias: int = 2, barrer: bool = True) -> dict:
    """Lee los pedidos recientes del cliente en Dropi y los guarda en SU cuenta. Solo lectura.
    Además, en cada pasada relee UN día más antiguo (rotando hasta 30 días atrás): así los
    cambios de estado de pedidos viejos (oficina, novedad, entregado) también llegan."""
    import mcp_client
    db = get_db()
    acceso = await _acceso(org)
    if not acceso:
        await _latido(org, False, "reconectar")
        return {"ok": False, "error": "reconectar"}
    hoy = (_now() - timedelta(hours=5)).date()          # día de Colombia
    dias = max(1, min(dias, 88))
    leidos = guardados = 0
    error, dia_barrido = "", None
    try:
        leidos, guardados, acceso = await _leer_rango(org, acceso, (hoy - timedelta(days=dias)).isoformat(),
                                                      (hoy + timedelta(days=1)).isoformat())
        if barrer and dias < BARRIDO_DIAS:
            doc = await db.dropi_conexiones.find_one({"org_id": org}, {"_id": 0, "barrido_dia": 1}) or {}
            dia_barrido = int(doc.get("barrido_dia") or dias) + 1
            if dia_barrido > BARRIDO_DIAS or dia_barrido <= dias:
                dia_barrido = dias + 1
            d = (hoy - timedelta(days=dia_barrido)).isoformat()
            l2, g2, acceso = await _leer_rango(org, acceso, d, d)
            leidos, guardados = leidos + l2, guardados + g2
    except Exception as e:  # noqa: BLE001
        error = "reconectar" if str(e) == "reconectar" else (mcp_client.safe_error(e)[:200] or type(e).__name__)
        log.warning("Sincronización Dropi falló (org=%s): %s", org, error)
    await db.dropi_conexiones.update_one({"org_id": org}, {"$set": {
        "ultimo_intento": _now().isoformat(), "ultimo_error": error,
        **({} if error else {"ultimo_sync": _now().isoformat(), "ultimo_leidos": leidos, "ultimo_guardados": guardados}),
        **({"barrido_dia": dia_barrido} if dia_barrido and not error else {})}})
    nota = _NOTAS.pop(org, "")
    await _latido(org, not error, error or f"leidos={leidos} guardados={guardados} barrido_dia={dia_barrido} {nota}".strip())
    return {"ok": not error, "leidos": leidos, "guardados": guardados, **({"error": error} if error else {})}


async def ciclo() -> int:
    """Una pasada por todas las cuentas conectadas. Nunca tumba el planificador."""
    n = 0
    try:
        docs = await get_db().dropi_conexiones.find({"conectado": True, "necesita_reconectar": {"$ne": True}},
                                                    {"_id": 0, "org_id": 1}).to_list(5000)
        for d in docs:
            try:
                await sincronizar(d["org_id"])
                n += 1
            except Exception as e:  # noqa: BLE001
                log.warning("ciclo Dropi (org=%s): %s", d.get("org_id"), type(e).__name__)
                await _latido(d.get("org_id") or "", False, "ciclo: " + type(e).__name__)
    except Exception as e:  # noqa: BLE001
        log.warning("ciclo Dropi falló: %s", type(e).__name__)
        await _latido("_sistema", False, "ciclo: " + type(e).__name__)
    return n


# ------------------------------------------------------------------ rutas
@router.post("/conectar", dependencies=[Depends(require_api_key)],
             summary="Devuelve la dirección de Dropi donde el cliente inicia sesión y autoriza la lectura de sus pedidos.")
async def conectar(request: Request):
    org = get_org(request)
    redirect = _vuelta_url(request)
    try:
        client_id = await _cliente(redirect)
    except Exception as e:  # noqa: BLE001
        log.warning("Registro en Dropi falló: %s", type(e).__name__)
        raise HTTPException(502, "Dropi no respondió para iniciar la conexión. Inténtalo en unos minutos.")
    estado, verificador = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).decode().rstrip("=")
    await get_db().dropi_oauth_estados.insert_one({
        "estado": estado, "org_id": org, "verificador_ct": _cifrar(verificador), "client_id": client_id,
        "redirect": redirect, "vence": (_now() + timedelta(minutes=10)).isoformat(), "usado": False})
    q = urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": redirect, "scope": PERMISOS,
                   "state": estado, "code_challenge": reto, "code_challenge_method": "S256", "resource": MCP_URL})
    return {"url": f"{AUTORIZAR}?{q}", "vence_en_min": 10}


@router.get("/vuelta", summary="Dropi devuelve aquí al cliente después de iniciar sesión. Guarda el permiso cifrado.")
async def vuelta(code: str = "", state: str = "", error: str = ""):
    db = get_db()
    destino = f"{_app_url()}/app/logistica?dropi="
    doc = await db.dropi_oauth_estados.find_one({"estado": state, "usado": False}, {"_id": 0}) if state else None
    if not doc or (doc.get("vence") or "") < _now().isoformat():
        return RedirectResponse(destino + "vencido", status_code=302)
    await db.dropi_oauth_estados.update_one({"estado": state}, {"$set": {"usado": True}})
    if error or not code:
        return RedirectResponse(destino + "cancelado", status_code=302)
    try:
        tok = await _post(TOKEN, form={"grant_type": "authorization_code", "code": code, "redirect_uri": doc["redirect"],
                                       "client_id": doc["client_id"], "code_verifier": _descifrar(doc["verificador_ct"]),
                                       "resource": MCP_URL})
        await _guardar_tokens(doc["org_id"], tok, doc["client_id"])
    except Exception as e:  # noqa: BLE001
        log.warning("Canje de Dropi falló (org=%s): %s", doc.get("org_id"), type(e).__name__)
        return RedirectResponse(destino + "error", status_code=302)
    return RedirectResponse(destino + "conectado", status_code=302)


@router.get("/estado", dependencies=[Depends(require_api_key)],
            summary="¿Está Dropi conectado en ESTA cuenta? Última lectura y si hay que volver a conectar. Sin secretos.")
async def estado(request: Request):
    d = await get_db().dropi_conexiones.find_one({"org_id": get_org(request)}, {"_id": 0}) or {}
    return {"conectado": bool(d.get("conectado")), "necesita_reconectar": bool(d.get("necesita_reconectar")),
            "ultimo_sync": d.get("ultimo_sync"), "ultimo_leidos": d.get("ultimo_leidos"),
            "ultimo_guardados": d.get("ultimo_guardados"), "ultimo_error": d.get("ultimo_error") or "",
            "cada_min": int(os.environ.get("DROPI_SYNC_MINUTES", "5")), "permiso": "solo lectura de pedidos"}


@router.post("/sincronizar", dependencies=[Depends(require_api_key)],
             summary="Lee ahora los pedidos recientes de Dropi de esta cuenta.")
async def sincronizar_ahora(request: Request):
    r = await sincronizar(get_org(request), dias=7, barrer=False)
    if not r.get("ok") and r.get("error") == "reconectar":
        raise HTTPException(409, "Conecta Dropi de nuevo: el permiso venció o no existe.")
    return r


@router.post("/desconectar", dependencies=[Depends(require_api_key)],
             summary="Quita el permiso de Dropi de esta cuenta. Los pedidos ya guardados se quedan.")
async def desconectar(request: Request):
    await get_db().dropi_conexiones.update_one({"org_id": get_org(request)}, {"$set": {
        "conectado": False, "acceso_ct": "", "refresco_ct": "", "actualizado": _now().isoformat()}})
    return {"ok": True}


# ------------------------------------------------------------------ planificador
def _enganchar_planificador() -> None:
    """Suma la lectura periódica al planificador que arranca el servidor (sin tocar su archivo)."""
    import scheduler
    if getattr(scheduler.start, "_con_dropi", False):
        return
    original = scheduler.start

    def start():
        s = original()
        try:
            if s is not None and not s.get_job("dropi_ciclo"):
                s.add_job(ciclo, "interval", minutes=max(2, int(os.environ.get("DROPI_SYNC_MINUTES", "5"))),
                          id="dropi_ciclo", max_instances=1, coalesce=True)
        except Exception as e:  # noqa: BLE001
            log.warning("No pude programar la lectura de Dropi: %s", type(e).__name__)
        return s
    start._con_dropi = True
    scheduler.start = start


_enganchar_planificador()
