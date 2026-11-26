"""Recuperar la contraseña por correo.

  · Pedir: siempre responde lo mismo, exista o no el correo (no revela quién
    tiene cuenta). Máximo 3 por hora por correo y 10 por hora por IP.
  · El enlace lleva un código de un solo uso que vence en 30 minutos. En la
    base se guarda solo su huella (sha256), nunca el código.
  · Cambiar: con el código vigente se guarda la contraseña nueva y se anulan
    los demás códigos de ese correo.
  · El correo sale por SMTP (SMTP_HOST, SMTP_USER, SMTP_PASSWORD). Sin SMTP no
    se puede enviar: `/clave/estado` lo dice para que la pantalla ofrezca
    escribir a soporte en vez de prometer un correo que no llega.
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from db import get_db
import ratelimit

router = APIRouter(prefix="/clave", tags=["recuperar-clave"])
log = logging.getLogger("recuperar")

VENCE_MIN = 30
POR_CORREO, POR_IP, VENTANA_S = 3, 10, 3600
RESPUESTA = {"ok": True, "mensaje": "Si ese correo tiene cuenta, te enviamos un enlace para crear una contraseña nueva. Revisa también la carpeta de spam."}


def _ahora() -> datetime: return datetime.now(timezone.utc)
def _huella(codigo: str) -> str: return hashlib.sha256(codigo.encode()).hexdigest()
def correo_listo() -> bool: return bool(os.environ.get("SMTP_HOST", "").strip())


def _sitio() -> str:
    return (os.environ.get("APP_PUBLIC_URL", "").strip() or "https://call.zynexapp.com").rstrip("/")


def _enviar(destino: str, enlace: str) -> bool:
    """Envía el correo. Devuelve False si no hay SMTP o si falla (se registra sin el enlace)."""
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        return False
    user = os.environ.get("SMTP_USER", "").strip()
    msg = EmailMessage()
    msg["Subject"] = "Crea una contraseña nueva para Zynex"
    msg["From"] = os.environ.get("SMTP_FROM", user or "no-reply@zynexapp.com")
    msg["To"] = destino
    msg.set_content(
        "Hola.\n\nPediste crear una contraseña nueva para tu cuenta de Zynex.\n"
        f"Abre este enlace (vence en {VENCE_MIN} minutos y sirve una sola vez):\n\n{enlace}\n\n"
        "Si no fuiste tú, ignora este correo: tu contraseña sigue igual.\n\nEquipo Zynex\n")
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as s:
            if os.environ.get("SMTP_STARTTLS", "true").lower() != "false":
                s.starttls(context=ssl.create_default_context())
            if user and os.environ.get("SMTP_PASSWORD", "").strip():
                s.login(user, os.environ["SMTP_PASSWORD"].strip())
            s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("recuperar: el correo no salió (%s)", type(e).__name__)
        return False


class PedirIn(BaseModel):
    email: EmailStr


class CambiarIn(BaseModel):
    codigo: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)


@router.get("/estado", summary="¿Se puede recuperar la contraseña por correo en este servidor?")
async def estado():
    return {"por_correo": correo_listo()}


@router.post("/pedir", summary="Pide el enlace para crear una contraseña nueva.")
async def pedir(payload: PedirIn, request: Request = None):
    correo = payload.email.lower().strip()
    ip = ratelimit.client_ip(request) if request is not None else "local"
    if ratelimit.count(f"clave:c:{correo}", VENTANA_S) >= POR_CORREO or ratelimit.count(f"clave:ip:{ip}", VENTANA_S) >= POR_IP:
        raise HTTPException(429, "Ya pediste varios enlaces. Espera una hora o escríbenos por WhatsApp.")
    ratelimit.hit(f"clave:c:{correo}", VENTANA_S); ratelimit.hit(f"clave:ip:{ip}", VENTANA_S)
    if not correo_listo():
        raise HTTPException(503, "Por ahora no podemos enviar correos. Escríbenos por WhatsApp y te ayudamos a entrar.")
    db = get_db()
    user = await db.users.find_one({"email": correo}, {"_id": 0, "id": 1, "provider": 1})
    if user and user.get("provider") != "google":
        codigo = secrets.token_urlsafe(32)
        await db.clave_codigos.insert_one({"huella": _huella(codigo), "user_id": user["id"], "email": correo, "usado": False,
                                           "vence": (_ahora() + timedelta(minutes=VENCE_MIN)).isoformat(), "creado": _ahora().isoformat()})
        await asyncio.to_thread(_enviar, correo, f"{_sitio()}/login?clave={codigo}")
    return RESPUESTA


@router.post("/cambiar", summary="Guarda la contraseña nueva con el código del correo.")
async def cambiar(payload: CambiarIn):
    from routes.auth import _hash
    db = get_db()
    fila = await db.clave_codigos.find_one({"huella": _huella(payload.codigo)})
    if not fila or fila.get("usado") or fila.get("vence", "") <= _ahora().isoformat():
        raise HTTPException(400, "Este enlace ya venció o ya se usó. Pide uno nuevo.")
    ahora = _ahora().isoformat()
    await db.users.update_one({"id": fila["user_id"]}, {"$set": {"password_hash": _hash(payload.password), "password_updated_at": ahora}})
    await db.clave_codigos.update_many({"user_id": fila["user_id"], "usado": False}, {"$set": {"usado": True, "usado_en": ahora}})
    return {"ok": True, "mensaje": "Listo. Ya puedes entrar con tu contraseña nueva."}
