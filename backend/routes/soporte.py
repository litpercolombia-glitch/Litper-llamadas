"""Soporte dentro de la app: el cliente pregunta desde el botón flotante, el
equipo responde, y el cliente puede dar permiso TEMPORAL para que soporte entre
a su cuenta.

Reglas de seguridad:
  · El equipo de soporte está APAGADO por defecto. Se enciende de dos formas:
    (a) variables SUPPORT_STAFF_EMAILS y SUPPORT_STAFF_ORG (hacen falta LAS DOS:
    un correo de la lista registrado en otra cuenta no sirve), o (b) una fila en
    la tabla zc_soporte_equipo de la base: la cuenta interna y, si se quiere,
    solo ciertos correos. Si la base no responde, nadie es del equipo.
  · Nadie entra a una cuenta sin permiso vigente dado por el cliente. El permiso
    vence solo (1, 24 o 72 horas) y el cliente lo puede quitar cuando quiera.
  · La sesión de soporte dura 30 minutos como máximo, nunca más que el permiso,
    y queda marcada como de soporte. Cada entrada queda en el registro que el
    cliente puede ver.
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from db import get_db

router = APIRouter(prefix="/soporte", tags=["soporte"])

HORAS_PERMITIDAS = (1, 24, 72)
SESION_MIN = 30
MAX_SIN_RESPUESTA = 20          # mensajes seguidos del cliente sin respuesta del equipo


def _ahora() -> datetime: return datetime.now(timezone.utc)
def _iso(d: datetime | None = None) -> str: return (d or _ahora()).isoformat()


async def _sesion(request: Request) -> dict:
    from routes.auth import current_user
    s = await current_user(request)
    if not s.get("org"):
        raise HTTPException(401, "Sesión sin organización. Vuelve a iniciar sesión.")
    return s


_EQUIPO_CACHE: dict[tuple[str, str], tuple[float, bool]] = {}
EQUIPO_CACHE_S = 60


async def _equipo_en_base(org: str, correo: str) -> bool:
    """La lista del equipo también vive en la base (tabla zc_soporte_equipo), para encenderlo sin tocar el servidor.
    Si la base no responde, la respuesta es NO: ante la duda nadie es del equipo."""
    import time
    clave, ahora = (org, correo), time.monotonic()
    visto = _EQUIPO_CACHE.get(clave)
    if visto and ahora - visto[0] < EQUIPO_CACHE_S:
        return visto[1]
    try:
        from routes import zynex_motor
        r = await zynex_motor.rpc("zc_api_soporte_equipo", {"p_org": org, "p_correo": correo})
        si = bool(isinstance(r, dict) and r.get("es_equipo") is True)
    except Exception:  # noqa: BLE001
        si = False
    _EQUIPO_CACHE[clave] = (ahora, si)
    return si


async def _es_equipo(s: dict) -> bool:
    if s.get("soporte") or not s.get("org"):
        return False
    correo, org = str(s.get("email", "")).lower(), str(s.get("org"))
    correos = {c.strip().lower() for c in os.environ.get("SUPPORT_STAFF_EMAILS", "").split(",") if c.strip()}
    cuenta = os.environ.get("SUPPORT_STAFF_ORG", "").strip()
    if correos and cuenta and correo in correos and org == cuenta:
        return True
    return await _equipo_en_base(org, correo)


async def _equipo(request: Request) -> dict:
    s = await _sesion(request)
    if not await _es_equipo(s):
        raise HTTPException(404, "No encontrado.")
    return s


async def _anotar(org: str, que: str, quien: str, detalle: str = "") -> None:
    await get_db().soporte_registro.insert_one(
        {"id": uuid.uuid4().hex[:12], "org_id": org, "que": que, "quien": quien, "detalle": detalle[:200], "creado": _iso()})


async def _permiso(org: str) -> dict | None:
    p = await get_db().soporte_acceso.find_one({"org_id": org})
    if not p or not p.get("hasta") or p["hasta"] <= _iso():
        return None
    return p


def _limpio(m: dict) -> dict:
    return {k: m.get(k) for k in ("id", "de", "texto", "creado")}


class MensajeIn(BaseModel):
    texto: str = Field(..., min_length=1, max_length=2000)


class PermisoIn(BaseModel):
    horas: int = 24


class RespuestaIn(BaseModel):
    org_id: str = Field(..., min_length=1, max_length=80)
    texto: str = Field(..., min_length=1, max_length=2000)


class EntrarIn(BaseModel):
    org_id: str = Field(..., min_length=1, max_length=80)


# ---------- Lado del cliente ----------
@router.get("/mensajes", summary="La conversación de esta cuenta con soporte.")
async def mis_mensajes(request: Request, marcar: bool = True):
    s = await _sesion(request)
    org = str(s["org"])
    db = get_db()
    ms = await db.soporte_mensajes.find({"org_id": org}).sort("creado", 1).to_list(200)
    if marcar and not s.get("soporte"):
        await db.soporte_mensajes.update_many({"org_id": org, "de": "equipo", "visto": False}, {"$set": {"visto": True}})
    p = await _permiso(org)
    return {"mensajes": [_limpio(m) for m in ms],
            "sin_leer": sum(1 for m in ms if m.get("de") == "equipo" and not m.get("visto")),
            "permiso": {"activo": bool(p), "hasta": p["hasta"] if p else None},
            "es_equipo": await _es_equipo(s), "sesion_soporte": bool(s.get("soporte"))}


@router.post("/mensajes", summary="El cliente le escribe a soporte.")
async def escribir(payload: MensajeIn, request: Request):
    s = await _sesion(request)
    if s.get("soporte"):
        raise HTTPException(403, "En sesión de soporte no se escribe a nombre del cliente.")
    org = str(s["org"])
    db = get_db()
    ultimos = await db.soporte_mensajes.find({"org_id": org}).sort("creado", -1).to_list(MAX_SIN_RESPUESTA)
    if len(ultimos) >= MAX_SIN_RESPUESTA and all(m.get("de") == "cliente" for m in ultimos):
        raise HTTPException(429, "Ya recibimos tus mensajes. Te respondemos pronto por aquí.")
    m = {"id": uuid.uuid4().hex[:12], "org_id": org, "de": "cliente", "correo": s.get("email"),
         "texto": payload.texto.strip(), "creado": _iso(), "visto": True, "atendido": False}
    await db.soporte_mensajes.insert_one(dict(m))
    return {"ok": True, "mensaje": _limpio(m)}


@router.post("/acceso", summary="El cliente da permiso temporal para que soporte entre a su cuenta.")
async def dar_permiso(payload: PermisoIn, request: Request):
    s = await _sesion(request)
    if s.get("soporte"):
        raise HTTPException(403, "El permiso solo lo da el dueño de la cuenta.")
    if payload.horas not in HORAS_PERMITIDAS:
        raise HTTPException(400, "Elige 1, 24 o 72 horas.")
    org = str(s["org"])
    hasta = _iso(_ahora() + timedelta(hours=payload.horas))
    await get_db().soporte_acceso.update_one(
        {"org_id": org}, {"$set": {"org_id": org, "hasta": hasta, "dado_por": s.get("email"), "creado": _iso()}}, upsert=True)
    await _anotar(org, "permiso_dado", str(s.get("email")), f"{payload.horas} h")
    return {"ok": True, "permiso": {"activo": True, "hasta": hasta}}


@router.post("/acceso/quitar", summary="El cliente quita el permiso.")
async def quitar_permiso(request: Request):
    s = await _sesion(request)
    if s.get("soporte"):
        raise HTTPException(403, "El permiso solo lo cambia el dueño de la cuenta.")
    org = str(s["org"])
    await get_db().soporte_acceso.update_one({"org_id": org}, {"$set": {"hasta": _iso()}})
    await _anotar(org, "permiso_quitado", str(s.get("email")))
    return {"ok": True, "permiso": {"activo": False, "hasta": None}}


@router.get("/registro", summary="Quién entró a esta cuenta y cuándo.")
async def registro(request: Request):
    s = await _sesion(request)
    filas = await get_db().soporte_registro.find({"org_id": str(s["org"])}).sort("creado", -1).to_list(50)
    return {"registro": [{k: f.get(k) for k in ("que", "quien", "detalle", "creado")} for f in filas]}


# ---------- Lado del equipo ----------
@router.get("/equipo/bandeja", summary="Cuentas con mensajes, las sin atender primero.")
async def bandeja(request: Request):
    await _equipo(request)
    db = get_db()
    ms = await db.soporte_mensajes.find({}).sort("creado", -1).to_list(2000)
    cuentas: dict[str, dict] = {}
    for m in ms:
        c = cuentas.setdefault(m["org_id"], {"org_id": m["org_id"], "ultimo": m.get("texto", "")[:140],
                                              "ultimo_de": m.get("de"), "cuando": m.get("creado"), "pendientes": 0})
        if m.get("de") == "cliente" and not m.get("atendido"):
            c["pendientes"] += 1
    for c in cuentas.values():
        c["permiso"] = bool(await _permiso(c["org_id"]))
    return {"cuentas": sorted(cuentas.values(), key=lambda c: (-min(c["pendientes"], 1), c["cuando"] or ""), reverse=False)}


@router.get("/equipo/mensajes/{org_id}", summary="La conversación de una cuenta.")
async def conversacion(org_id: str, request: Request):
    await _equipo(request)
    ms = await get_db().soporte_mensajes.find({"org_id": org_id}).sort("creado", 1).to_list(200)
    p = await _permiso(org_id)
    return {"mensajes": [_limpio(m) for m in ms], "permiso": {"activo": bool(p), "hasta": p["hasta"] if p else None}}


@router.post("/equipo/responder", summary="Una persona del equipo responde.")
async def responder(payload: RespuestaIn, request: Request):
    s = await _equipo(request)
    db = get_db()
    m = {"id": uuid.uuid4().hex[:12], "org_id": payload.org_id, "de": "equipo", "correo": s.get("email"),
         "texto": payload.texto.strip(), "creado": _iso(), "visto": False, "atendido": True}
    await db.soporte_mensajes.insert_one(dict(m))
    await db.soporte_mensajes.update_many({"org_id": payload.org_id, "de": "cliente", "atendido": False}, {"$set": {"atendido": True}})
    return {"ok": True, "mensaje": _limpio(m)}


@router.post("/equipo/entrar", summary="Entrar a la cuenta del cliente (solo con su permiso vigente).")
async def entrar(payload: EntrarIn, request: Request, response: Response):
    s = await _equipo(request)
    p = await _permiso(payload.org_id)
    if not p:
        raise HTTPException(403, "Esta cuenta no ha dado permiso, o ya venció. Pídeselo por el chat.")
    from routes.auth import JWT_SECRET, JWT_ALG, COOKIE_NAME
    ahora = _ahora()
    vence = min(ahora + timedelta(minutes=SESION_MIN), datetime.fromisoformat(p["hasta"]))
    token = jwt.encode({"sub": f"soporte:{s.get('sub')}", "org": payload.org_id, "email": s.get("email"), "soporte": True,
                        "iat": int(ahora.timestamp()), "exp": int(vence.timestamp())}, JWT_SECRET, algorithm=JWT_ALG)
    response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, samesite="lax", secure=True,
                        max_age=max(60, int((vence - ahora).total_seconds())), path="/")
    await _anotar(payload.org_id, "soporte_entro", str(s.get("email")), f"sesión hasta {_iso(vence)}")
    return {"ok": True, "hasta": _iso(vence)}
