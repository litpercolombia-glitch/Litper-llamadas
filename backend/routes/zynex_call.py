"""Zynex Call — llamadas de voz por estado de Dropi (ElevenLabs del cliente + su número).

Motor propio, sin Talkyria. Todo es por cliente (org): llaves en org_credentials
(chatea_pro, elevenlabs), configuración y cola en Mongo con org_id.

Flujo:
  Chatea Pro (campos del contacto, incluido el último estado de Dropi que llega
  por la integración Chatea↔Dropi) ──► cola por agente ──► ElevenLabs llama
  ──► webhook post-llamada ──► resultado en la app + campos/etiquetas en Chatea.
Claude entra por el conector MCP (routes/zynex_mcp.py): sube pedidos de Dropi
y lee resultados para escribirlos de vuelta en Dropi.

Reglas: modo prueba = solo números del equipo; activo exige escribir ACTIVAR y
tener ElevenLabs, número y webhook. Ventana 8–10 a. m. hora del negocio, lunes a
sábado. Reintento solo para buzón / llamar después. Nunca se llama sin cliente,
valor y teléfono (la llamada queda bloqueada).
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from db import get_db
from deps import get_org, require_api_key

log = logging.getLogger("zynex_call")
router = APIRouter(prefix="/zcall", tags=["zynex-call"])

EL = "https://api.elevenlabs.io"
CH_DEFAULT = "https://chateapro.app/api"
TZ_OFFSET_H = -5  # America/Bogota (sin horario de verano)

RES_OK = ["CONFIRMADO", "DATO_CORREGIDO", "RECOGE_EN_FECHA", "YA_RECOGIDO", "CONFIRMA_RECIBIR",
          "YA_RECIBIDO", "QUIERE_REENVIO", "DIRECCION_CORREGIDA", "HORARIO_ACORDADO", "RETIRO_EN_OFICINA"]
RES_REINTENTO = ["BUZON_SIN_RESPUESTA", "LLAMAR_DESPUES"]
RES_ASESOR = ["PASA_A_ASESOR", "NO_PUEDE_IR", "NO_ESTARA_HOY", "DATO_CORREGIDO", "DIRECCION_CORREGIDA",
              "RETIRO_EN_OFICINA", "CANCELACION_SOLICITADA", "NO_LO_QUIERE"]
TODOS = list(dict.fromkeys(RES_OK + RES_REINTENTO + RES_ASESOR + ["NO_ES_LA_PERSONA", "NO_CONTACTAR"]))
NOVEDAD_NUM = {"1": "DIRECCION_CORREGIDA", "2": "HORARIO_ACORDADO", "3": "YA_RECIBIDO", "4": "RETIRO_EN_OFICINA",
               "5": "CANCELACION_SOLICITADA", "6": "PASA_A_ASESOR", "7": "LLAMAR_DESPUES", "8": "NO_ES_LA_PERSONA",
               "9": "BUZON_SIN_RESPUESTA", "10": "NO_CONTACTAR"}

# Agentes por estado de Dropi (idénticos a Dropi). Las variables que exige cada uno.
AGENTES_BASE = [
    {"agente": "confirmacion", "nombre": "Confirmación", "estados_dropi": ["PENDIENTE CONFIRMACION"],
     "requeridas": ["cliente", "valor", "producto", "direccion", "ciudad"], "prioridad": 1},
    {"agente": "novedad", "nombre": "Novedad", "estados_dropi": ["NOVEDAD"],
     "requeridas": ["cliente", "valor", "producto", "direccion", "ciudad", "novedad"], "prioridad": 2},
    {"agente": "oficina", "nombre": "Reclamo en oficina", "estados_dropi": ["PARA RECLAMAR EN OFICINA", "EN OFICINA"],
     "requeridas": ["cliente", "valor", "transportadora"], "prioridad": 3},
    {"agente": "reparto", "nombre": "En reparto", "estados_dropi": ["EN REPARTO"],
     "requeridas": ["cliente", "valor"], "prioridad": 4},
    {"agente": "devolucion", "nombre": "Recuperar devolución", "estados_dropi": ["DEVOLUCION", "DEVOLUCION EN TRANSITO"],
     "requeridas": ["cliente", "valor", "producto", "transportadora"], "prioridad": 5},
]
VARS_AGENTE = ["cliente", "producto", "valor", "direccion", "ciudad", "transportadora", "guia", "novedad",
               "dias_en_oficina", "direccion_oficina", "motivo_devolucion", "dato_faltante"]
VARS_MAPEO = ["cliente", "valor", "telefono", "producto", "direccion", "ciudad", "transportadora", "guia",
              "novedad", "dropi_order_id", "estado_dropi"]
TRANSFORMACIONES = ["texto", "numero", "telefono_co", "corto", "minusculas", "nombre_corto", "ciudad"]

# Candidatos de campos de Chatea Pro (plantillas Dropi). El primero con valor gana.
CANDIDATOS: dict[str, tuple[list[str], str]] = {
    "cliente": ([r"^nombre completo$", r"^nombre$", r"\[logistica\] cliente: nombre", r"nombre del cliente"], "nombre_corto"),
    "valor": ([r"^valor de la compra$", r"precio total \(formateado\)"], "numero"),
    "producto": ([r"^productos escogidos$", r"\[whatsapp ia\] nombre del producto", r"\[logistica\] productos de la orden"], "corto"),
    "direccion": ([r"direcci[oó]n para llamadas", r"^direcci[oó]n$", r"\[logistica\] direcci[oó]n: direcci[oó]n completa"], "texto"),
    "ciudad": ([r"^ciudad$", r"traducci[oó]n de ciudad", r"\[logistica\] direcci[oó]n: ciudad"], "ciudad"),
    "transportadora": ([r"^transportadora$", r"^\[logistica\] transportadora$"], "minusculas"),
    "guia": ([r"\[logistica\] numero de gu[ií]a", r"^guia_envio$"], "texto"),
    "novedad": ([r"novedad: comentario del repartidor", r"explicacion del estado logistico"], "corto"),
    "dropi_order_id": ([r"^\[logistica\] id de la orden$", r"^\[logistica\] order id$", r"^dropi_order_id$"], "texto"),
    "estado_dropi": ([r"^[uú]ltimo estado recibido$", r"\[logistica\] estado de respaldo", r"^estado_pedido$"], "texto"),
}
CAMPOS_RESULTADO = ["[Zynex Call] Resultado", "[Zynex Call] Nota", "[Zynex Call] Fecha", "[Zynex Call] Agente",
                    "[Zynex Call] Conversación", "[Zynex Call] Dirección corregida"]
ETIQUETAS = ["[Zynex Call] Llamado", "[Zynex Call] Requiere asesor", "[Zynex Call] No contactar",
             "[Zynex Call] Pre-aviso llamada"]


# ---------------- utilidades ----------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime | None = None) -> str:
    return (d or _now()).isoformat()


def _sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def mask(t: Optional[str]) -> Optional[str]:
    return ("•••" + str(t)[-4:]) if t else None


def tel_co(v: Any) -> Optional[str]:
    s = str(v or "").strip()
    d = re.sub(r"\D", "", s)
    if len(d) == 10 and d.startswith("3"):
        return "+57" + d
    if len(d) == 12 and d.startswith("573"):
        return "+" + d
    if s.startswith("+") and len(d) >= 10:
        return "+" + d
    return None


def transformar(v: Any, t: str) -> str:
    if v is None:
        return ""
    s = v if isinstance(v, str) else str(v)
    s = s.strip()
    if not s or s == "null":
        return ""
    if t == "numero":
        return re.sub(r"\D", "", s)
    if t == "telefono_co":
        return tel_co(s) or ""
    if t == "minusculas":
        return s.lower()
    if t == "nombre_corto":
        return " ".join(w[:1].upper() + w[1:].lower() for w in re.split(r"\s+", s)[:2])
    if t == "ciudad":
        s = re.sub(r"\s*\(.*?\)\s*", " ", s)
        s = re.sub(r",.*$", "", s).strip().lower()
        return " ".join(w[:1].upper() + w[1:] for w in s.split())
    if t == "corto":
        s = re.sub(r"\s+", " ", s.lower())
        if len(s) > 90:
            s = re.sub(r"\s+\S*$", "", s[:90]) + " y más"
        return s
    return re.sub(r"\s+", " ", s)


def norm_resultado(r: Any) -> Optional[str]:
    if r is None:
        return None
    import unicodedata
    s = unicodedata.normalize("NFD", str(r).strip().upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", "_", s)
    m = re.match(r"^\d+", s)
    if m and m.group(0) in NOVEDAD_NUM:
        return NOVEDAD_NUM[m.group(0)]
    if s == "BUZON_O_SIN_RESPUESTA":
        s = "BUZON_SIN_RESPUESTA"
    for t in TODOS:
        if s == t or s.startswith(t):
            return t
    return None


def _parse_hhmm(v: str) -> tuple[int, int]:
    h, m = (str(v or "08:00") + ":00").split(":")[:2]
    return int(h), int(m)


def proxima_ventana(cfg: dict, desde: datetime | None = None) -> datetime:
    """Próximo instante dentro de la ventana (hora Colombia), lunes a sábado."""
    desde = desde or _now()
    off = timedelta(hours=TZ_OFFSET_H)
    hi, mi = _parse_hhmm(cfg.get("ventana_ini", "08:00"))
    hf, mf = _parse_hhmm(cfg.get("ventana_fin", "10:00"))
    for d in range(8):
        local = desde + off + timedelta(days=d)
        if local.weekday() == 6:  # domingo
            continue
        ini = datetime(local.year, local.month, local.day, hi, mi, tzinfo=timezone.utc) - off
        fin = datetime(local.year, local.month, local.day, hf, mf, tzinfo=timezone.utc) - off
        if desde < ini:
            return ini
        if ini <= desde < fin:
            return desde
    return desde + timedelta(days=1)


def en_ventana(cfg: dict, t: datetime | None = None) -> bool:
    t = t or _now()
    return proxima_ventana(cfg, t) == t


async def evento(org: str, tipo: str, detalle: dict, llamada_id: Optional[str] = None):
    await get_db().zc_eventos.insert_one({"org_id": org, "tipo": tipo, "detalle": detalle,
                                         "llamada_id": llamada_id, "creado": _iso()})


# ---------------- configuración por cliente ----------------
async def asegurar(org: str) -> dict:
    """Crea config, agentes y mapeo base la primera vez (idempotente)."""
    await instalar()
    db = get_db()
    cfg = await db.zc_config.find_one({"org_id": org}, {"_id": 0})
    if not cfg:
        cfg = {"org_id": org, "modo": "prueba", "ventana_ini": "08:00", "ventana_fin": "10:00",
               "max_intentos": 3, "minutos_entre_intentos": 120, "numeros_equipo": [],
               "pre_aviso_whatsapp": True, "auto_recoger": False, "proveedor_telefonia": None,
               "phone_number_id": None, "numero_saliente": None, "webhook_token_hash": None,
               "mcp_token_hash": None, "creado": _iso(), "actualizado": _iso()}
        await db.zc_config.update_one({"org_id": org}, {"$setOnInsert": cfg}, upsert=True)
        cfg = await db.zc_config.find_one({"org_id": org}, {"_id": 0})
    for a in AGENTES_BASE:
        await db.zc_agentes.update_one(
            {"org_id": org, "agente": a["agente"]},
            {"$setOnInsert": {**a, "org_id": org, "elevenlabs_agent_id": None, "activo": False}},
            upsert=True)
    await db.zc_mapeo.update_one(
        {"org_id": org, "variable": "telefono"},
        {"$setOnInsert": {"org_id": org, "variable": "telefono", "fuente": "suscriptor", "ref": "phone",
                          "refs_alt": [], "nombre_campo": "Teléfono del contacto", "transformacion": "telefono_co"}},
        upsert=True)
    return cfg


async def _llave(org: str, proveedor: str, campo: str = "api_key") -> str:
    from org_credentials import get_credentials
    try:
        return (await get_credentials(proveedor, org)).get(campo, "") or ""
    except Exception:  # noqa: BLE001
        return ""


# ---------------- Chatea Pro ----------------
async def _chatea(org: str, method: str, path: str, **kw) -> tuple[int, Any]:
    key = await _llave(org, "chatea_pro")
    if not key:
        return 0, {"error": "Conecta Chatea Pro en Conexiones."}
    base = (await _llave(org, "chatea_pro", "base_url")) or CH_DEFAULT
    async with httpx.AsyncClient(timeout=20) as cli:
        r = await cli.request(method, base.rstrip("/") + path,
                              headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text[:200]}


async def campos_chatea(org: str) -> list[dict]:
    out: list[dict] = []
    for p in range(1, 11):
        st, j = await _chatea(org, "GET", f"/flow/user-fields?limit=100&page={p}")
        if st != 200:
            if st == 0:
                raise HTTPException(400, j["error"])
            raise HTTPException(400, f"Chatea respondió {st} al leer los campos.")
        out += j.get("data") or []
        if p >= ((j.get("meta") or {}).get("last_page") or 1):
            break
    return out


def automapear(campos: list[dict]) -> list[dict]:
    res = []
    for var, (pats, t) in CANDIDATOS.items():
        hits: list[dict] = []
        for pat in pats:
            h = next((f for f in campos if re.search(pat, str(f.get("name", "")).strip(), re.I) and f not in hits), None)
            if h:
                hits.append(h)
        if hits:
            res.append({"variable": var, "fuente": "campo", "ref": hits[0]["var_ns"],
                        "refs_alt": [h["var_ns"] for h in hits[1:]],
                        "nombre_campo": " → ".join(h["name"] for h in hits), "transformacion": t})
    return res


async def variables_de_contacto(org: str, user_ns: str) -> dict:
    st, j = await _chatea(org, "GET", "/subscriber/get-info", params={"user_ns": user_ns})
    if st != 200:
        raise HTTPException(400, (j or {}).get("error") or f"Chatea respondió {st} al leer el contacto.")
    s = j.get("data") or j
    campos = {f.get("var_ns"): f.get("value") for f in (s.get("user_fields") or [])}
    vars_: dict[str, str] = {}
    async for m in get_db().zc_mapeo.find({"org_id": org}, {"_id": 0}):
        val = ""
        for ref in [m["ref"], *(m.get("refs_alt") or [])]:
            crudo = campos.get(ref) if m["fuente"] == "campo" else s.get(ref) if m["fuente"] == "suscriptor" else ref
            val = transformar(crudo, m["transformacion"])
            if val:
                break
        vars_[m["variable"]] = val
    if not vars_.get("cliente") and s.get("first_name"):
        vars_["cliente"] = transformar(s["first_name"], "nombre_corto")
    tags = [str((t or {}).get("name", t)) if isinstance(t, dict) else str(t) for t in (s.get("tags") or [])]
    return {"vars": vars_, "tags": tags}


async def escribir_chatea(org: str, user_ns: str, datos: dict, tags: list[str]) -> str:
    errs = []
    if datos:
        st, _ = await _chatea(org, "PUT", "/subscriber/set-user-fields-by-name",
                              json={"user_ns": user_ns, "data": [{"field_name": k, "value": str(v)} for k, v in datos.items()]})
        if st != 200:
            errs.append(f"campos {st}")
    for t in tags:
        st, _ = await _chatea(org, "POST", "/subscriber/add-tag-by-name", json={"user_ns": user_ns, "tag_name": t})
        if st != 200:
            errs.append(f"etiqueta {st}")
    return "ok" if not errs else "error: " + ", ".join(errs)


# ---------------- validación y cola ----------------
async def agente_por_estado(org: str, estado: str) -> Optional[dict]:
    e = str(estado or "").strip().upper()
    agentes = [a async for a in get_db().zc_agentes.find({"org_id": org}, {"_id": 0})]
    if not e:  # venta recién cerrada (sin estado aún) → confirmación
        return next((a for a in agentes if a["agente"] == "confirmacion"), None)
    return next((a for a in agentes if any(x.upper() == e for x in a["estados_dropi"])), None)


def validar(agente: dict, vars_: dict, telefono: Optional[str]) -> list[str]:
    faltan = [r for r in agente["requeridas"] if not vars_.get(r)]
    if not telefono:
        faltan.insert(0, "telefono")
    if vars_.get("valor") and not re.fullmatch(r"\d{4,9}", vars_["valor"]):
        faltan.append("valor_invalido")
    return faltan


def dinamicas(vars_: dict, meta: dict) -> dict:
    d = {k: (vars_.get(k) or ("" if k == "dato_faltante" else "(sin dato)")) for k in VARS_AGENTE}
    d.update({"meta_" + k: str(v) for k, v in meta.items()})
    return d


async def encolar(org: str, cfg: dict, agente: dict, vars_: dict, user_ns: Optional[str], origen: str) -> dict:
    db = get_db()
    tel = vars_.get("telefono") or None
    faltan = validar(agente, vars_, tel)
    oid = vars_.get("dropi_order_id") or None
    if oid and await db.zc_llamadas.find_one({"org_id": org, "agente": agente["agente"], "dropi_order_id": oid,
                                              "estado": {"$in": ["en_cola", "bloqueada", "llamando"]}}, {"_id": 1}):
        return {"ok": True, "duplicada": True, "mensaje": "Ese pedido ya está en cola para este agente."}
    doc = {"id": secrets.token_hex(8), "org_id": org, "agente": agente["agente"], "user_ns": user_ns, "telefono": tel,
           "dropi_order_id": oid, "estado_dropi": vars_.get("estado_dropi") or None, "variables": vars_,
           "faltantes": faltan, "estado": "bloqueada" if faltan else "en_cola",
           "motivo_estado": ("Faltan datos: " + ", ".join(faltan)) if faltan else None,
           "proxima_llamada": None if faltan else _iso(proxima_ventana(cfg)), "intentos": 0,
           "conversation_id": None, "resultado": None, "nota": None, "direccion_corregida": None,
           "sync_chatea": None, "sync_dropi": None, "origen": origen, "creado": _iso(), "actualizado": _iso()}
    await db.zc_llamadas.insert_one(dict(doc))
    return {"ok": True, "id": doc["id"], "estado": doc["estado"], "faltantes": faltan,
            "proxima_llamada": doc["proxima_llamada"]}


# ---------------- ElevenLabs ----------------
async def _el(org: str, method: str, path: str, **kw) -> tuple[int, Any]:
    key = await _llave(org, "elevenlabs")
    if not key:
        return 0, {"error": "Conecta ElevenLabs en Conexiones."}
    async with httpx.AsyncClient(timeout=30) as cli:
        r = await cli.request(method, EL + path, headers={"xi-api-key": key}, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text[:200]}


async def marcar(org: str, ll: dict, cfg: dict) -> dict:
    db = get_db()
    ag = await db.zc_agentes.find_one({"org_id": org, "agente": ll["agente"]}, {"_id": 0})
    if not (ag or {}).get("elevenlabs_agent_id"):
        return {"ok": False, "error": "El agente no tiene ID de ElevenLabs (pestaña Agentes)."}
    if not cfg.get("phone_number_id"):
        return {"ok": False, "error": "Conecta un número en Zynex Call → Reglas y número."}
    ruta = "/v1/convai/sip-trunk/outbound-call" if cfg.get("proveedor_telefonia") == "sip" else "/v1/convai/twilio/outbound-call"
    body = {"agent_id": ag["elevenlabs_agent_id"], "agent_phone_number_id": cfg["phone_number_id"], "to_number": ll["telefono"],
            "conversation_initiation_client_data": {"dynamic_variables": dinamicas(
                ll.get("variables") or {}, {"llamada_id": ll["id"], "org": org, "agente": ll["agente"],
                                            "dropi_order_id": ll.get("dropi_order_id") or ""})}}
    st, j = await _el(org, "POST", ruta, json=body)
    if st != 200 or (isinstance(j, dict) and j.get("success") is False):
        msg = (j or {}).get("message") or ((j or {}).get("detail") or {})
        await db.zc_llamadas.update_one({"id": ll["id"]}, {"$set": {"estado": "error", "actualizado": _iso(),
                                         "motivo_estado": f"ElevenLabs {st}: {str(msg)[:200]}"}})
        return {"ok": False, "error": f"ElevenLabs no inició la llamada ({st})."}
    await db.zc_llamadas.update_one({"id": ll["id"]}, {"$set": {"estado": "llamando", "conversation_id": j.get("conversation_id"),
                                     "actualizado": _iso()}, "$inc": {"intentos": 1}})
    await evento(org, "llamada_iniciada", {"agente": ll["agente"]}, ll["id"])
    return {"ok": True, "conversation_id": j.get("conversation_id")}


async def recoger_de_chatea(org: str, cfg: dict, limite: int = 20) -> dict:
    """Botón «Traer pedidos»: busca en Chatea los contactos cuyo estado de Dropi
    corresponde a un agente activo y los pone en cola (sin duplicar en 3 días)."""
    db = get_db()
    m_estado = await db.zc_mapeo.find_one({"org_id": org, "variable": "estado_dropi"}, {"_id": 0})
    if not m_estado:
        return {"encolados": 0, "bloqueados": 0, "nota": "Falta enlazar la variable estado_dropi (pestaña Variables)."}
    n = bloq = 0
    hace3 = _iso(_now() - timedelta(days=3))
    async for ag in db.zc_agentes.find({"org_id": org, "activo": True}, {"_id": 0}):
        for est in ag["estados_dropi"]:
            st, j = await _chatea(org, "GET", "/subscribers", params={"limit": limite, "user_field_ns": m_estado["ref"],
                                                                          "user_field_value": est})
            if st != 200:
                continue
            for s in j.get("data") or []:
                if await db.zc_llamadas.find_one({"org_id": org, "user_ns": s["user_ns"], "agente": ag["agente"],
                                                  "creado": {"$gte": hace3}}, {"_id": 1}):
                    continue
                try:
                    v = await variables_de_contacto(org, s["user_ns"])
                except HTTPException:
                    continue
                if any(re.search(r"no contactar", t, re.I) for t in v["tags"]):
                    continue
                r = await encolar(org, cfg, ag, v["vars"], s["user_ns"], "chatea")
                if r.get("estado") == "bloqueada":
                    bloq += 1
                elif not r.get("duplicada"):
                    n += 1
    return {"encolados": n, "bloqueados": bloq}


async def despachar(org: str, maximo: int = 5) -> dict:
    db = get_db()
    cfg = await asegurar(org)
    if cfg.get("modo") == "pausado":
        return {"ok": True, "nada": "Zynex Call está en pausa."}
    if not en_ventana(cfg):
        return {"ok": True, "nada": "Fuera de la ventana de llamadas."}
    if not await _llave(org, "elevenlabs"):
        return {"ok": False, "error": "Conecta ElevenLabs en Conexiones."}
    hechos = []
    cur = db.zc_llamadas.find({"org_id": org, "estado": "en_cola", "proxima_llamada": {"$lte": _iso()}},
                              {"_id": 0}).sort("proxima_llamada", 1).limit(maximo)
    async for ll in cur:
        if cfg.get("modo") != "activo" and ll.get("telefono") not in (cfg.get("numeros_equipo") or []):
            hechos.append({"id": ll["id"], "saltada": "modo prueba: solo números del equipo"})
            continue
        if ll.get("user_ns") and await _llave(org, "chatea_pro"):
            try:
                v = await variables_de_contacto(org, ll["user_ns"])
                cerrado = any(re.search(r"ya confirmado|no contactar|cancelar comunicaci", t, re.I) for t in v["tags"])
                ag = await db.zc_agentes.find_one({"org_id": org, "agente": ll["agente"]}, {"_id": 0})
                nuevo = v["vars"].get("estado_dropi")
                cambio = bool(nuevo) and ag and not any(e.upper() == nuevo.upper() for e in ag["estados_dropi"])
                if cerrado or cambio:
                    await db.zc_llamadas.update_one({"id": ll["id"]}, {"$set": {"estado": "cancelada", "actualizado": _iso(),
                                                     "motivo_estado": "Chatea ya lo resolvió" if cerrado else f"El pedido cambió a {nuevo}"}})
                    hechos.append({"id": ll["id"], "cancelada": True})
                    continue
                if cfg.get("pre_aviso_whatsapp") and not ll.get("intentos"):
                    await escribir_chatea(org, ll["user_ns"], {}, ["[Zynex Call] Pre-aviso llamada"])
            except HTTPException:
                pass
        hechos.append({"id": ll["id"], **(await marcar(org, ll, cfg))})
    return {"ok": True, "procesadas": hechos}


async def tick_todos() -> int:
    """Planificador interno (cada 10 min): para cada cliente con auto_recoger,
    trae de Chatea y despacha dentro de su ventana. Sin tareas de Claude."""
    n = 0
    async for cfg in get_db().zc_config.find({"auto_recoger": True, "modo": {"$ne": "pausado"}}, {"_id": 0}):
        org = cfg["org_id"]
        try:
            if en_ventana(cfg):
                await recoger_de_chatea(org, cfg)
                await despachar(org)
                n += 1
        except Exception as e:  # noqa: BLE001
            log.warning("zcall tick %s: %s", org, type(e).__name__)
    return n


# ---------------- webhook post-llamada (público, con token) ----------------
def _razon_end_call(data: dict) -> Optional[str]:
    for t in reversed(data.get("transcript") or []):
        for tc in (t or {}).get("tool_calls") or []:
            if re.search(r"end_call", str(tc.get("tool_name") or tc.get("name") or ""), re.I):
                p = tc.get("params_as_json") or tc.get("parameters") or tc.get("params") or {}
                if isinstance(p, str):
                    try:
                        import json
                        p = json.loads(p)
                    except ValueError:
                        p = {}
                r = norm_resultado((p or {}).get("reason") or (p or {}).get("razon"))
                if r:
                    return r
    dc = ((data.get("analysis") or {}).get("data_collection_results") or {}).get("resultado") or {}
    return norm_resultado(dc.get("value") if isinstance(dc, dict) else dc)


@router.post("/webhook/{token}", summary="Post-llamada de ElevenLabs (con token del cliente).")
async def webhook(token: str, request: Request):
    db = get_db()
    cfg = await db.zc_config.find_one({"webhook_token_hash": _sha(token)}, {"_id": 0})
    if not cfg:
        raise HTTPException(401, "no autorizado")
    org = cfg["org_id"]
    body = await request.json()
    data = body.get("data") or {}
    conv = data.get("conversation_id")
    dyn = (data.get("conversation_initiation_client_data") or {}).get("dynamic_variables") or {}
    ll = await db.zc_llamadas.find_one({"org_id": org, "conversation_id": conv}, {"_id": 0}) if conv else None
    if not ll and dyn.get("meta_llamada_id"):
        ll = await db.zc_llamadas.find_one({"org_id": org, "id": str(dyn["meta_llamada_id"])}, {"_id": 0})
    if not ll:
        await evento(org, "webhook_sin_llamada", {"type": body.get("type")})
        return {"ok": True, "ignorado": True}
    if ll.get("estado") == "terminada" and ll.get("resultado"):
        return {"ok": True, "repetido": True}
    espera = timedelta(minutes=int(cfg.get("minutos_entre_intentos") or 120))
    if body.get("type") == "call_initiation_failure":
        reintenta = (ll.get("intentos") or 0) < int(cfg.get("max_intentos") or 3)
        await db.zc_llamadas.update_one({"id": ll["id"]}, {"$set": {
            "estado": "en_cola" if reintenta else "terminada", "resultado": None if reintenta else "BUZON_SIN_RESPUESTA",
            "motivo_estado": "No se pudo conectar", "actualizado": _iso(),
            "proxima_llamada": _iso(proxima_ventana(cfg, _now() + espera)) if reintenta else None}})
        return {"ok": True}
    resultado = _razon_end_call(data) or "BUZON_SIN_RESPUESTA"  # silencio sin end_call = buzón
    dc = (data.get("analysis") or {}).get("data_collection_results") or {}
    nota = str(((dc.get("nota") or {}).get("value")) or (data.get("analysis") or {}).get("transcript_summary") or "")
    nota = re.sub(r"\b\d{12,19}\b", "[oculto]", nota)[:200]
    direc = " · ".join(str((dc.get(k) or {}).get("value")) for k in ("referencia_o_apartamento", "direccion_nueva")
                       if (dc.get(k) or {}).get("value")) or None
    reintenta = resultado in RES_REINTENTO and (ll.get("intentos") or 0) < int(cfg.get("max_intentos") or 3)
    await db.zc_llamadas.update_one({"id": ll["id"]}, {"$set": {
        "estado": "en_cola" if reintenta else "terminada", "resultado": resultado, "nota": nota,
        "direccion_corregida": direc, "duracion_s": (data.get("metadata") or {}).get("call_duration_secs"),
        "proxima_llamada": _iso(proxima_ventana(cfg, _now() + espera)) if reintenta else None,
        "motivo_estado": f"Reintento {(ll.get('intentos') or 0) + 1} de {cfg.get('max_intentos')}" if reintenta else None,
        "sync_dropi": "pendiente" if resultado in RES_ASESOR or resultado in RES_OK else "no_requiere",
        "actualizado": _iso()}})
    sync = "sin_contacto_chatea"
    if ll.get("user_ns"):
        tags = ["[Zynex Call] Llamado"]
        if resultado in ("CONFIRMADO", "CONFIRMA_RECIBIR", "YA_RECIBIDO", "YA_RECOGIDO"):
            tags.append("Ya confirmado✅")
        if resultado in RES_ASESOR:
            tags.append("[Zynex Call] Requiere asesor")
        if resultado == "NO_CONTACTAR":
            tags.append("[Zynex Call] No contactar")
        fecha = (_now() + timedelta(hours=TZ_OFFSET_H)).strftime("%d/%m/%Y %I:%M %p")
        datos = {"[Zynex Call] Resultado": resultado, "[Zynex Call] Nota": nota, "[Zynex Call] Fecha": fecha,
                 "[Zynex Call] Agente": ll["agente"], "[Zynex Call] Conversación": conv or ""}
        if direc:
            datos["[Zynex Call] Dirección corregida"] = direc
        sync = await escribir_chatea(org, ll["user_ns"], datos, tags)
    await db.zc_llamadas.update_one({"id": ll["id"]}, {"$set": {"sync_chatea": sync}})
    await evento(org, "resultado", {"resultado": resultado, "reintenta": reintenta, "sync": sync}, ll["id"])
    return {"ok": True, "resultado": resultado, "reintenta": reintenta}


# ---------------- panel (con sesión) ----------------
@router.get("/estado", dependencies=[Depends(require_api_key)])
async def estado(request: Request):
    org = get_org(request)
    db = get_db()
    cfg = await asegurar(org)
    agentes = [a async for a in db.zc_agentes.find({"org_id": org}, {"_id": 0}).sort("prioridad", 1)]
    mapeo = [m async for m in db.zc_mapeo.find({"org_id": org}, {"_id": 0}).sort("variable", 1)]
    filas = []
    async for x in db.zc_llamadas.find({"org_id": org}, {"_id": 0}).sort("creado", -1).limit(200):
        v = x.pop("variables", {}) or {}
        x.update({"telefono": mask(x.get("telefono")), "cliente": (v.get("cliente") or "").split(" ")[0],
                  "valor": v.get("valor")})
        filas.append(x)
    term = [x for x in filas if x["estado"] == "terminada"]
    cont = [x for x in term if x.get("resultado") not in ("BUZON_SIN_RESPUESTA", "NO_ES_LA_PERSONA")]
    exito = [x for x in term if x.get("resultado") in RES_OK]
    por_res: dict[str, int] = {}
    for x in term:
        por_res[x["resultado"]] = por_res.get(x["resultado"], 0) + 1
    conexiones = {"chatea": bool(await _llave(org, "chatea_pro")), "elevenlabs": bool(await _llave(org, "elevenlabs")),
                  "numero": bool(cfg.get("phone_number_id")), "webhook": bool(cfg.get("webhook_token_hash")),
                  "claude": bool(cfg.get("mcp_token_hash"))}
    pub = {k: v for k, v in cfg.items() if k not in ("webhook_token_hash", "mcp_token_hash", "phone_number_id")}
    pub["numeros_equipo"] = [mask(n) for n in cfg.get("numeros_equipo") or []]
    pub["numero_saliente"] = mask(cfg.get("numero_saliente"))
    return {"ok": True, "config": pub, "conexiones": conexiones, "agentes": agentes, "mapeo": mapeo,
            "variables_disponibles": VARS_MAPEO, "transformaciones": TRANSFORMACIONES,
            "campos_resultado": CAMPOS_RESULTADO, "etiquetas": ETIQUETAS, "llamadas": filas,
            "metricas": {"total": len(filas), "en_cola": sum(x["estado"] == "en_cola" for x in filas),
                         "bloqueadas": sum(x["estado"] == "bloqueada" for x in filas), "terminadas": len(term),
                         "tasa_contacto": round(len(cont) / len(term) * 100, 1) if term else None,
                         "tasa_exito": round(len(exito) / len(cont) * 100, 1) if cont else None,
                         "por_resultado": por_res},
            "ventana_ahora": en_ventana(cfg), "proxima_ventana": _iso(proxima_ventana(cfg))}


@router.get("/campos-chatea", dependencies=[Depends(require_api_key)])
async def get_campos(request: Request):
    org = get_org(request)
    return {"ok": True, "campos": [{"var_ns": f["var_ns"], "name": f["name"], "var_type": f.get("var_type")}
                                   for f in await campos_chatea(org)]}


class AutoIn(BaseModel):
    remapear: bool = False


@router.post("/automapear", dependencies=[Depends(require_api_key)])
async def post_automapear(payload: AutoIn, request: Request):
    org = get_org(request)
    await asegurar(org)
    db = get_db()
    campos = await campos_chatea(org)
    prop = automapear(campos)
    hechos = 0
    for p in prop:
        if not payload.remapear and await db.zc_mapeo.find_one({"org_id": org, "variable": p["variable"]}, {"_id": 1}):
            continue
        await db.zc_mapeo.update_one({"org_id": org, "variable": p["variable"]}, {"$set": {**p, "org_id": org}}, upsert=True)
        hechos += 1
    await evento(org, "automapear", {"campos": len(campos), "enlazadas": hechos})
    return {"ok": True, "mensaje": f"Leí {len(campos)} campos de tu Chatea y enlacé {hechos} variables.", "propuesta": prop}


class MapeoIn(BaseModel):
    variable: str
    fuente: str = "campo"
    ref: str
    refs_alt: Optional[list[str]] = None
    nombre_campo: Optional[str] = None
    transformacion: str = "texto"


@router.put("/mapeo", dependencies=[Depends(require_api_key)])
async def put_mapeo(p: MapeoIn, request: Request):
    org = get_org(request)
    if p.variable not in VARS_MAPEO or p.transformacion not in TRANSFORMACIONES or p.fuente not in ("campo", "suscriptor", "fijo"):
        raise HTTPException(400, "Variable, fuente o transformación no válida.")
    if not p.ref:
        raise HTTPException(400, "Elige el campo de Chatea.")
    upd = {"org_id": org, "variable": p.variable, "fuente": p.fuente, "ref": p.ref,
           "nombre_campo": p.nombre_campo, "transformacion": p.transformacion}
    op: dict[str, Any] = {"$set": upd}
    if p.refs_alt is not None:
        upd["refs_alt"] = [r for r in p.refs_alt if r][:5]
    else:
        op["$setOnInsert"] = {"refs_alt": []}
    await get_db().zc_mapeo.update_one({"org_id": org, "variable": p.variable}, op, upsert=True)
    return {"ok": True, "mensaje": f"Variable {p.variable} enlazada."}


class AgenteIn(BaseModel):
    elevenlabs_agent_id: Optional[str] = None
    activo: Optional[bool] = None


@router.patch("/agentes/{agente}", dependencies=[Depends(require_api_key)])
async def patch_agente(agente: str, p: AgenteIn, request: Request):
    org = get_org(request)
    await asegurar(org)
    upd: dict[str, Any] = {}
    if p.elevenlabs_agent_id is not None:
        aid = p.elevenlabs_agent_id.strip()
        if aid and not re.fullmatch(r"agent_[A-Za-z0-9]{10,60}", aid):
            raise HTTPException(400, "El ID del agente de ElevenLabs empieza por agent_.")
        upd["elevenlabs_agent_id"] = aid or None
    if p.activo is not None:
        upd["activo"] = p.activo
    r = await get_db().zc_agentes.update_one({"org_id": org, "agente": agente}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(404, "Agente no existe.")
    return {"ok": True, "mensaje": "Agente actualizado."}


class ConfigIn(BaseModel):
    ventana_ini: Optional[str] = None
    ventana_fin: Optional[str] = None
    max_intentos: Optional[int] = None
    minutos_entre_intentos: Optional[int] = None
    pre_aviso_whatsapp: Optional[bool] = None
    auto_recoger: Optional[bool] = None
    numeros_equipo: Optional[list[str]] = None
    modo: Optional[str] = None
    confirmacion: Optional[str] = None


@router.patch("/config", dependencies=[Depends(require_api_key)])
async def patch_config(p: ConfigIn, request: Request):
    org = get_org(request)
    cfg = await asegurar(org)
    upd: dict[str, Any] = {}
    for k in ("ventana_ini", "ventana_fin"):
        v = getattr(p, k)
        if v is not None:
            if not re.fullmatch(r"\d{2}:\d{2}", v):
                raise HTTPException(400, "Hora en formato HH:MM.")
            upd[k] = v
    if p.max_intentos is not None:
        upd["max_intentos"] = max(1, min(5, p.max_intentos))
    if p.minutos_entre_intentos is not None:
        upd["minutos_entre_intentos"] = max(30, min(1440, p.minutos_entre_intentos))
    for k in ("pre_aviso_whatsapp", "auto_recoger"):
        if getattr(p, k) is not None:
            upd[k] = getattr(p, k)
    if p.numeros_equipo is not None:
        upd["numeros_equipo"] = [n for n in (tel_co(x) for x in p.numeros_equipo) if n]
    if p.modo:
        if p.modo not in ("prueba", "activo", "pausado"):
            raise HTTPException(400, "Modo no válido.")
        if p.modo == "activo":
            if p.confirmacion != "ACTIVAR":
                raise HTTPException(400, "Para llamar a clientes reales escribe ACTIVAR.")
            if not (await _llave(org, "elevenlabs") and cfg.get("phone_number_id") and cfg.get("webhook_token_hash")):
                raise HTTPException(400, "Antes de activar: ElevenLabs, número y webhook deben estar conectados.")
        upd["modo"] = p.modo
    upd["actualizado"] = _iso()
    await get_db().zc_config.update_one({"org_id": org}, {"$set": upd})
    await evento(org, "config", {"campos": list(upd)})
    return {"ok": True, "mensaje": "Configuración guardada."}


class NumeroIn(BaseModel):
    proveedor: str = "twilio"
    numero: str
    etiqueta: Optional[str] = "Zynex Call"
    direccion: Optional[str] = None


@router.post("/numero", dependencies=[Depends(require_api_key)])
async def post_numero(p: NumeroIn, request: Request):
    """Importa el número del cliente a SU ElevenLabs. Twilio usa las llaves de
    Twilio guardadas en Conexiones; SIP usa la dirección del trunk."""
    org = get_org(request)
    await asegurar(org)
    numero = tel_co(p.numero) or (re.sub(r"[^\d+]", "", p.numero) if p.numero.strip().startswith("+") else None)
    if not numero:
        raise HTTPException(400, "Escribe el número en formato internacional, ej. +57 300 000 0000.")
    if p.proveedor == "twilio":
        from org_credentials import get_credentials
        tw = await get_credentials("twilio", org)
        if not (tw.get("account_sid") and tw.get("auth_token")):
            raise HTTPException(400, "Conecta Twilio (Account SID y Auth Token) en Conexiones primero.")
        cuerpo = {"provider": "twilio", "phone_number": numero, "label": p.etiqueta or "Zynex Call",
                  "sid": tw["account_sid"], "token": tw["auth_token"]}
    else:
        if not p.direccion:
            raise HTTPException(400, "Escribe la dirección del trunk SIP.")
        cuerpo = {"provider": "sip_trunk", "phone_number": numero, "label": p.etiqueta or "Zynex Call",
                  "outbound_trunk_config": {"address": p.direccion}}
    st, j = await _el(org, "POST", "/v1/convai/phone-numbers", json=cuerpo)
    if st == 0:
        raise HTTPException(400, j["error"])
    if st not in (200, 201):
        raise HTTPException(400, f"ElevenLabs no importó el número ({st}).")
    await get_db().zc_config.update_one({"org_id": org}, {"$set": {
        "proveedor_telefonia": "sip" if p.proveedor == "sip" else "twilio", "phone_number_id": j.get("phone_number_id"),
        "numero_saliente": numero, "actualizado": _iso()}})
    await evento(org, "numero", {"proveedor": p.proveedor})
    return {"ok": True, "mensaje": "Número importado a tu ElevenLabs y listo para tus agentes."}


@router.post("/webhook-url", dependencies=[Depends(require_api_key)])
async def post_webhook_url(request: Request):
    from webhook_tokens import public_base
    org = get_org(request)
    await asegurar(org)
    t = secrets.token_urlsafe(32)
    await get_db().zc_config.update_one({"org_id": org}, {"$set": {"webhook_token_hash": _sha(t), "actualizado": _iso()}})
    return {"ok": True, "url": f"{public_base(request)}/api/zcall/webhook/{t}",
            "mensaje": "Pégala en ElevenLabs → Agents → Settings → Post-call webhook. Solo se muestra una vez."}


class ContactoIn(BaseModel):
    user_ns: str
    agente: Optional[str] = None


@router.post("/previsualizar", dependencies=[Depends(require_api_key)])
async def post_previsualizar(p: ContactoIn, request: Request):
    org = get_org(request)
    await asegurar(org)
    v = await variables_de_contacto(org, p.user_ns.strip())
    ag = (await get_db().zc_agentes.find_one({"org_id": org, "agente": p.agente}, {"_id": 0})) if p.agente \
        else await agente_por_estado(org, v["vars"].get("estado_dropi", ""))
    faltan = validar(ag, v["vars"], v["vars"].get("telefono")) if ag else ["agente (estado de Dropi sin agente)"]
    vista = {**v["vars"], "telefono": mask(v["vars"].get("telefono"))}
    return {"ok": True, "agente": (ag or {}).get("agente"), "variables": vista, "faltantes": faltan,
            "listo": not faltan, "etiquetas": v["tags"]}


@router.post("/encolar", dependencies=[Depends(require_api_key)])
async def post_encolar(p: ContactoIn, request: Request):
    org = get_org(request)
    cfg = await asegurar(org)
    v = await variables_de_contacto(org, p.user_ns.strip())
    ag = (await get_db().zc_agentes.find_one({"org_id": org, "agente": p.agente}, {"_id": 0})) if p.agente \
        else await agente_por_estado(org, v["vars"].get("estado_dropi", ""))
    if not ag:
        raise HTTPException(400, "No hay agente para ese estado de Dropi; elige uno.")
    return await encolar(org, cfg, ag, v["vars"], p.user_ns.strip(), "manual")


@router.post("/recoger", dependencies=[Depends(require_api_key)])
async def post_recoger(request: Request):
    org = get_org(request)
    cfg = await asegurar(org)
    if not await _llave(org, "chatea_pro"):
        raise HTTPException(400, "Conecta Chatea Pro en Conexiones.")
    return {"ok": True, **(await recoger_de_chatea(org, cfg))}


@router.post("/despachar", dependencies=[Depends(require_api_key)])
async def post_despachar(request: Request):
    return await despachar(get_org(request))


class PruebaIn(BaseModel):
    agente: str = "confirmacion"
    telefono: str


@router.post("/llamar-prueba", dependencies=[Depends(require_api_key)])
async def post_prueba(p: PruebaIn, request: Request):
    org = get_org(request)
    cfg = await asegurar(org)
    tel = tel_co(p.telefono)
    if not tel or tel not in (cfg.get("numeros_equipo") or []):
        raise HTTPException(400, "Solo se puede probar con un número del equipo guardado en Reglas.")
    ag = await get_db().zc_agentes.find_one({"org_id": org, "agente": p.agente}, {"_id": 0})
    if not ag:
        raise HTTPException(404, "Agente no existe.")
    vars_ = {"cliente": "Prueba", "producto": "protector de colchón", "valor": "89900",
             "direccion": "Calle 45 número 12-30, barrio Los Álamos", "ciudad": "Medellín",
             "transportadora": "servientrega", "novedad": "dirección incompleta", "guia": "123456", "telefono": tel}
    doc = {"id": secrets.token_hex(8), "org_id": org, "agente": ag["agente"], "user_ns": None, "telefono": tel,
           "dropi_order_id": None, "estado_dropi": None, "variables": vars_, "faltantes": [], "estado": "en_cola",
           "intentos": 0, "origen": "prueba", "proxima_llamada": _iso(), "creado": _iso(), "actualizado": _iso()}
    await get_db().zc_llamadas.insert_one(dict(doc))
    r = await marcar(org, doc, cfg)
    if not r.get("ok"):
        raise HTTPException(400, r.get("error"))
    return r


@router.post("/llamadas/{llamada_id}/cancelar", dependencies=[Depends(require_api_key)])
async def cancelar(llamada_id: str, request: Request):
    org = get_org(request)
    r = await get_db().zc_llamadas.update_one({"org_id": org, "id": llamada_id, "estado": {"$in": ["en_cola", "bloqueada"]}},
                                              {"$set": {"estado": "cancelada", "motivo_estado": "Cancelada por el dueño",
                                                        "actualizado": _iso()}})
    return {"ok": bool(r.modified_count)}


# ---------------- conector de Claude (token por cliente) ----------------
@router.post("/claude-token", dependencies=[Depends(require_api_key)])
async def post_claude_token(request: Request):
    from webhook_tokens import public_base
    org = get_org(request)
    await asegurar(org)
    t = "zx_" + secrets.token_urlsafe(32)
    await get_db().zc_config.update_one({"org_id": org}, {"$set": {"mcp_token_hash": _sha(t), "actualizado": _iso()}})
    await evento(org, "claude_token", {})
    return {"ok": True, "url": f"{public_base(request)}/api/mcp/{t}",
            "mensaje": "Pega esta URL en Claude → Configuración → Conectores → Agregar conector personalizado. Solo se muestra una vez."}


async def org_por_token_mcp(token: str) -> Optional[str]:
    cfg = await get_db().zc_config.find_one({"mcp_token_hash": _sha(token)}, {"_id": 0, "org_id": 1})
    return (cfg or {}).get("org_id")


async def subir_pedidos(org: str, pedidos: list[dict]) -> dict:
    """Pedidos que Claude trae de Dropi (con su conector) → espejo + cola por agente."""
    db = get_db()
    cfg = await asegurar(org)
    resumen = {"recibidos": len(pedidos), "encolados": 0, "bloqueados": 0, "sin_agente": 0, "duplicados": 0}
    for p in pedidos[:500]:
        oid = str(p.get("dropi_order_id") or p.get("id") or "").strip()
        if not oid:
            continue
        vars_ = {"cliente": transformar(p.get("cliente"), "nombre_corto"), "valor": transformar(p.get("valor"), "numero"),
                 "telefono": tel_co(p.get("telefono")) or "", "producto": transformar(p.get("producto"), "corto"),
                 "direccion": transformar(p.get("direccion"), "texto"), "ciudad": transformar(p.get("ciudad"), "ciudad"),
                 "transportadora": transformar(p.get("transportadora"), "minusculas"), "guia": transformar(p.get("guia"), "texto"),
                 "novedad": transformar(p.get("novedad"), "corto"), "dropi_order_id": oid,
                 "estado_dropi": transformar(p.get("estado_dropi") or p.get("estado"), "texto").upper()}
        await db.zc_pedidos.update_one({"org_id": org, "dropi_order_id": oid},
                                       {"$set": {**vars_, "org_id": org, "actualizado": _iso()}}, upsert=True)
        ag = await agente_por_estado(org, vars_["estado_dropi"])
        if not ag or not vars_["estado_dropi"] or not ag.get("activo"):
            resumen["sin_agente"] += 1
            continue
        r = await encolar(org, cfg, ag, vars_, None, "claude_dropi")
        key = "duplicados" if r.get("duplicada") else "bloqueados" if r.get("estado") == "bloqueada" else "encolados"
        resumen[key] += 1
    await evento(org, "claude_subir_pedidos", resumen)
    return resumen


# ---------------- instalación (índices + tarea interna) ----------------
_INSTALADO = {"indices": False, "tarea": False}


async def instalar() -> None:
    """Idempotente y sin tumbar nada: índices de Mongo y la tarea interna en el
    APScheduler de la app. Se llama desde /health y desde el panel."""
    if not _INSTALADO["indices"]:
        db = get_db()
        specs = [(db.zc_config, "org_id", {"unique": True}), (db.zc_config, "webhook_token_hash", {}),
                 (db.zc_config, "mcp_token_hash", {}),
                 (db.zc_agentes, [("org_id", 1), ("agente", 1)], {"unique": True}),
                 (db.zc_mapeo, [("org_id", 1), ("variable", 1)], {"unique": True}),
                 (db.zc_llamadas, "id", {"unique": True}),
                 (db.zc_llamadas, [("org_id", 1), ("estado", 1), ("proxima_llamada", 1)], {}),
                 (db.zc_llamadas, [("org_id", 1), ("conversation_id", 1)], {}),
                 (db.zc_llamadas, [("org_id", 1), ("user_ns", 1), ("agente", 1), ("creado", -1)], {}),
                 (db.zc_pedidos, [("org_id", 1), ("dropi_order_id", 1)], {"unique": True}),
                 (db.zc_eventos, [("org_id", 1), ("creado", -1)], {})]
        for coll, keys, kw in specs:
            try:
                await coll.create_index(keys, **kw)
            except Exception as e:  # noqa: BLE001
                log.warning("índice zcall %s: %s", keys, type(e).__name__)
        _INSTALADO["indices"] = True
    if not _INSTALADO["tarea"]:
        try:
            import scheduler as sch
            s = getattr(sch, "_scheduler", None)
            if s is not None:
                if not s.get_job("zcall_tick"):
                    s.add_job(_tick_seguro, "interval", minutes=10, id="zcall_tick", max_instances=1, coalesce=True)
                _INSTALADO["tarea"] = True
        except Exception as e:  # noqa: BLE001
            log.warning("zcall tarea: %s", type(e).__name__)


async def _tick_seguro():
    try:
        n = await tick_todos()
        if n:
            log.info("zcall_tick: %s cliente(s)", n)
    except Exception as e:  # noqa: BLE001
        log.warning("zcall_tick falló: %s", type(e).__name__)
