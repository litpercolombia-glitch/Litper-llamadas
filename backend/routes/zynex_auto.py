"""Zynex Call · configuración automática ("el cliente solo trae su ElevenLabs").

1) Número: el cliente verifica SU celular (como Dapta). Zynex usa su cuenta
   maestra de Twilio, crea una subcuenta por cliente, registra el celular como
   «Verified Caller ID» (Twilio llama y el cliente marca un código) y lo importa
   en el ElevenLabs del cliente. No se compra número ni se piden documentos.
   Si no hay cuenta maestra, usa el Twilio propio del cliente (Conexiones).
2) Agentes: crea los 5 agentes (confirmación, novedad, oficina, reparto,
   devolución) en el ElevenLabs del cliente con el nombre de su negocio.
3) Webhook: registra el webhook post-llamada en el ElevenLabs del cliente.

Cuenta maestra: variables ZYNEX_TWILIO_MASTER_SID y ZYNEX_TWILIO_MASTER_TOKEN.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from db import get_db
from deps import get_org, require_api_key
from routes import zynex_call as zc

router = APIRouter(prefix="/zcall/auto", tags=["zynex-call-auto"])
TW = "https://api.twilio.com/2010-04-01"


# ---------------- Twilio (cuenta maestra + subcuenta por cliente) ----------------
def _master() -> tuple[str, str]:
    return (os.environ.get("ZYNEX_TWILIO_MASTER_SID", "").strip(),
            os.environ.get("ZYNEX_TWILIO_MASTER_TOKEN", "").strip())


def _cifrar(d: dict) -> str:
    from org_credentials import _fernet
    return _fernet().encrypt(json.dumps(d).encode()).decode()


def _descifrar(t: str) -> dict:
    from org_credentials import _fernet
    return json.loads(_fernet().decrypt(t.encode()).decode())


async def _tw(method: str, url: str, auth: tuple[str, str], **kw) -> tuple[int, Any]:
    async with httpx.AsyncClient(timeout=25) as cli:
        r = await cli.request(method, url, auth=auth, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"raw": r.text[:200]}


async def cuenta_twilio(org: str) -> tuple[str, str, str]:
    """(sid, token, origen). Subcuenta de Zynex por cliente; si no hay cuenta
    maestra, el Twilio propio del cliente guardado en Conexiones."""
    db = get_db()
    sid_m, tok_m = _master()
    if sid_m and tok_m:
        cfg = await db.zc_config.find_one({"org_id": org}, {"_id": 0, "twilio_sub": 1}) or {}
        if cfg.get("twilio_sub"):
            d = _descifrar(cfg["twilio_sub"])
            return d["sid"], d["token"], "zynex"
        st, j = await _tw("POST", f"{TW}/Accounts.json", (sid_m, tok_m),
                          data={"FriendlyName": f"Zynex · {org}"[:64]})
        if st not in (200, 201) or not j.get("sid"):
            raise HTTPException(502, f"No se pudo preparar la telefonía de Zynex (Twilio {st}).")
        await db.zc_config.update_one({"org_id": org}, {"$set": {
            "twilio_sub": _cifrar({"sid": j["sid"], "token": j["auth_token"]}), "actualizado": zc._iso()}})
        await zc.evento(org, "twilio_subcuenta", {})
        return j["sid"], j["auth_token"], "zynex"
    from org_credentials import get_credentials
    tw = await get_credentials("twilio", org)
    if tw.get("account_sid") and tw.get("auth_token"):
        return tw["account_sid"], tw["auth_token"], "cliente"
    raise HTTPException(400, "La telefonía de Zynex aún no está activa. Escríbenos por WhatsApp al 314 464 4054.")


class VerificarIn(BaseModel):
    numero: str
    nombre: Optional[str] = None


@router.post("/numero/verificar", dependencies=[Depends(require_api_key)])
async def verificar(p: VerificarIn, request: Request):
    """Paso 1: Twilio llama al celular del cliente y él marca el código que
    le mostramos en pantalla."""
    org = get_org(request)
    await zc.asegurar(org)
    numero = zc.tel_co(p.numero)
    if not numero:
        raise HTTPException(400, "Escribe tu celular de Colombia, ej. 314 464 4054.")
    sid, tok, origen = await cuenta_twilio(org)
    st, j = await _tw("POST", f"{TW}/Accounts/{sid}/OutgoingCallerIds.json", (sid, tok),
                      data={"PhoneNumber": numero, "FriendlyName": (p.nombre or "Zynex Call")[:64]})
    if st not in (200, 201):
        msg = str((j or {}).get("message") or "")
        if "already" in msg.lower() or (j or {}).get("code") == 21450:
            return {"ok": True, "ya_verificado": True, "mensaje": "Ese número ya está verificado. Pulsa «Ya marqué el código»."}
        raise HTTPException(400, f"Twilio no pudo llamar a ese número ({st}). Revisa que sea un celular activo.")
    await get_db().zc_config.update_one({"org_id": org}, {"$set": {
        "numero_pendiente": numero, "actualizado": zc._iso()}})
    await zc.evento(org, "verificacion_numero", {"origen": origen})
    return {"ok": True, "codigo": j.get("validation_code"),
            "mensaje": "Te vamos a llamar en unos segundos. Contesta y marca este código en el teclado."}


@router.post("/numero/confirmar", dependencies=[Depends(require_api_key)])
async def confirmar(request: Request):
    """Paso 2: si Twilio ya lo verificó, lo importa en el ElevenLabs del cliente."""
    org = get_org(request)
    db = get_db()
    cfg = await zc.asegurar(org)
    numero = cfg.get("numero_pendiente") or cfg.get("numero_saliente")
    if not numero:
        raise HTTPException(400, "Primero pide la llamada de verificación.")
    sid, tok, origen = await cuenta_twilio(org)
    st, j = await _tw("GET", f"{TW}/Accounts/{sid}/OutgoingCallerIds.json", (sid, tok), params={"PhoneNumber": numero})
    if st != 200 or not (j.get("outgoing_caller_ids") or []):
        raise HTTPException(400, "Todavía no aparece verificado. Contesta la llamada, marca el código y vuelve a intentar.")
    st, e = await zc._el(org, "POST", "/v1/convai/phone-numbers", json={
        "provider": "twilio", "phone_number": numero, "label": "Zynex Call", "sid": sid, "token": tok})
    if st == 0:
        raise HTTPException(400, e["error"])
    if st not in (200, 201):
        raise HTTPException(400, f"ElevenLabs no aceptó el número ({st}).")
    await db.zc_config.update_one({"org_id": org}, {"$set": {
        "proveedor_telefonia": "twilio", "phone_number_id": e.get("phone_number_id"),
        "numero_saliente": numero, "telefonia_origen": origen, "actualizado": zc._iso()},
        "$unset": {"numero_pendiente": ""}})
    await zc.evento(org, "numero_listo", {"origen": origen})
    return {"ok": True, "mensaje": "Listo: tus agentes ya llaman desde tu número."}


# ---------------- Agentes en el ElevenLabs del cliente ----------------
REGLAS = (
    "Hablas español de Colombia, cálido, claro y breve: frases cortas, una pregunta a la vez. "
    "Nunca inventes datos ni prometas descuentos. Si te preguntan algo que no sabes, ofrece que un asesor "
    "le escriba por WhatsApp. Si la persona no es el cliente o no puede hablar, despídete con amabilidad. "
    "Si piden no volver a llamar, respeta y cierra. Nunca pidas datos de tarjetas. "
    "Al terminar SIEMPRE usa la herramienta end_call y pon en el motivo uno de los resultados permitidos, "
    "exactamente como está escrito."
)
PLANTILLAS = [
    {"agente": "confirmacion", "nombre": "Confirmación de pedido",
     "primer": "Hola, ¿hablo con {{cliente}}? Le habla la asistente de {negocio}. Le llamo para confirmar su pedido de {{producto}}.",
     "objetivo": "Confirmar el pedido para despacharlo. Repite producto ({{producto}}), valor a pagar al recibir "
                 "({{valor}} pesos), dirección ({{direccion}}) y ciudad ({{ciudad}}). Si algo cambió, toma el dato correcto.",
     "resultados": "CONFIRMADO, DATO_CORREGIDO, CANCELACION_SOLICITADA, LLAMAR_DESPUES, PASA_A_ASESOR, NO_ES_LA_PERSONA, NO_CONTACTAR, BUZON_SIN_RESPUESTA"},
    {"agente": "novedad", "nombre": "Novedad de entrega",
     "primer": "Hola, ¿hablo con {{cliente}}? Le habla la asistente de {negocio}, sobre su pedido de {{producto}}.",
     "objetivo": "La transportadora reportó una novedad: {{novedad}}. Resuélvela: corrige dirección o referencia, acuerda horario "
                 "o confirma si ya lo recibió. Dirección registrada: {{direccion}}, {{ciudad}}. Valor: {{valor}} pesos.",
     "resultados": "1 DIRECCION_CORREGIDA, 2 HORARIO_ACORDADO, 3 YA_RECIBIDO, 4 RETIRO_EN_OFICINA, 5 CANCELACION_SOLICITADA, "
                   "6 PASA_A_ASESOR, 7 LLAMAR_DESPUES, 8 NO_ES_LA_PERSONA, 9 BUZON_SIN_RESPUESTA, 10 NO_CONTACTAR"},
    {"agente": "oficina", "nombre": "Reclamo en oficina",
     "primer": "Hola, ¿hablo con {{cliente}}? Le habla la asistente de {negocio}. Su paquete ya está en la oficina de {{transportadora}}.",
     "objetivo": "Lograr que recoja el paquete. Valor a pagar: {{valor}} pesos. Pregunta qué día puede ir. "
                 "Si no puede, ofrece que un asesor le ayude.",
     "resultados": "RECOGE_EN_FECHA, YA_RECOGIDO, NO_PUEDE_IR, PASA_A_ASESOR, LLAMAR_DESPUES, NO_ES_LA_PERSONA, NO_CONTACTAR, BUZON_SIN_RESPUESTA"},
    {"agente": "reparto", "nombre": "Pedido en reparto",
     "primer": "Hola, ¿hablo con {{cliente}}? Le habla la asistente de {negocio}. Su pedido sale hoy a reparto.",
     "objetivo": "Confirmar que estará para recibir y tenga listos {{valor}} pesos en efectivo.",
     "resultados": "CONFIRMA_RECIBIR, NO_ESTARA_HOY, DIRECCION_CORREGIDA, PASA_A_ASESOR, LLAMAR_DESPUES, NO_ES_LA_PERSONA, NO_CONTACTAR, BUZON_SIN_RESPUESTA"},
    {"agente": "devolucion", "nombre": "Recuperar devolución",
     "primer": "Hola, ¿hablo con {{cliente}}? Le habla la asistente de {negocio}, sobre su pedido de {{producto}}.",
     "objetivo": "El pedido va en devolución con {{transportadora}}. Pregunta con respeto qué pasó y si aún lo quiere; "
                 "si sí, ofrece reenviarlo. Valor: {{valor}} pesos.",
     "resultados": "QUIERE_REENVIO, NO_LO_QUIERE, PASA_A_ASESOR, LLAMAR_DESPUES, NO_ES_LA_PERSONA, NO_CONTACTAR, BUZON_SIN_RESPUESTA"},
]
DATOS = {
    "resultado": "Resultado final de la llamada, uno de los permitidos, en MAYÚSCULAS.",
    "nota": "Resumen de una línea de lo que dijo el cliente.",
    "direccion_nueva": "Dirección corregida si el cliente dio una nueva.",
    "referencia_o_apartamento": "Referencia, barrio o apartamento adicional si lo dio.",
}


def cuerpo_agente(t: dict, negocio: str, voice_id: Optional[str]) -> dict:
    prompt = (f"Eres la asistente de voz de {negocio}, tienda con pago contra entrega en Colombia. {REGLAS}\n\n"
              f"OBJETIVO: {t['objetivo']}\n\nRESULTADOS PERMITIDOS: {t['resultados']}.")
    cfg: dict[str, Any] = {
        "agent": {"first_message": t["primer"].replace("{negocio}", negocio), "language": "es",
                  "prompt": {"prompt": prompt, "built_in_tools": {"end_call": {
                      "name": "end_call", "description": "Termina la llamada con el resultado en el motivo.",
                      "params": {"system_tool_type": "end_call"}}}}},
    }
    if voice_id:
        cfg["tts"] = {"voice_id": voice_id, "model_id": "eleven_flash_v2_5"}
    return {"name": f"Zynex Call · {t['nombre']}", "tags": ["zynex-call", t["agente"]], "conversation_config": cfg,
            "platform_settings": {"data_collection": {k: {"type": "string", "description": v} for k, v in DATOS.items()}}}


class AgentesIn(BaseModel):
    negocio: str
    voice_id: Optional[str] = None
    reemplazar: bool = False


@router.post("/agentes", dependencies=[Depends(require_api_key)])
async def crear_agentes(p: AgentesIn, request: Request):
    org = get_org(request)
    await zc.asegurar(org)
    negocio = re.sub(r"\s+", " ", p.negocio).strip()[:60]
    if len(negocio) < 2:
        raise HTTPException(400, "Escribe el nombre de tu negocio.")
    db = get_db()
    hechos, errores = [], []
    for t in PLANTILLAS:
        actual = await db.zc_agentes.find_one({"org_id": org, "agente": t["agente"]}, {"_id": 0})
        if (actual or {}).get("elevenlabs_agent_id") and not p.reemplazar:
            continue
        st, j = await zc._el(org, "POST", "/v1/convai/agents/create", json=cuerpo_agente(t, negocio, p.voice_id))
        if st in (400, 422) and p.voice_id:  # voz no disponible en esa cuenta → voz por defecto
            st, j = await zc._el(org, "POST", "/v1/convai/agents/create", json=cuerpo_agente(t, negocio, None))
        if st == 0:
            raise HTTPException(400, j["error"])
        if st not in (200, 201) or not j.get("agent_id"):
            errores.append(t["nombre"])
            continue
        await db.zc_agentes.update_one({"org_id": org, "agente": t["agente"]},
                                       {"$set": {"elevenlabs_agent_id": j["agent_id"]}})
        hechos.append(t["nombre"])
    await zc.evento(org, "agentes_creados", {"creados": len(hechos), "errores": len(errores)})
    if errores and not hechos:
        raise HTTPException(400, "ElevenLabs no creó los agentes. Revisa que tu llave tenga permiso de Agentes.")
    msg = f"Creé {len(hechos)} agente(s) en tu ElevenLabs." if hechos else "Tus agentes ya estaban creados."
    if errores:
        msg += f" Faltaron: {', '.join(errores)}."
    return {"ok": True, "creados": hechos, "errores": errores, "mensaje": msg}


# ---------------- Webhook post-llamada automático ----------------
@router.post("/webhook", dependencies=[Depends(require_api_key)])
async def webhook_auto(request: Request):
    from webhook_tokens import public_base
    org = get_org(request)
    await zc.asegurar(org)
    t = secrets.token_urlsafe(32)
    url = f"{public_base(request)}/api/zcall/webhook/{t}"
    st, j = await zc._el(org, "POST", "/v1/workspace/webhooks",
                         json={"settings": {"auth_type": "hmac", "name": "Zynex Call", "webhook_url": url}})
    if st == 0:
        raise HTTPException(400, j["error"])
    ok = st in (200, 201) and j.get("webhook_id")
    if ok:
        st2, _ = await zc._el(org, "PATCH", "/v1/convai/settings",
                              json={"webhooks": {"post_call_webhook_id": j["webhook_id"], "events": ["transcript"]}})
        ok = st2 in (200, 201)
    await get_db().zc_config.update_one({"org_id": org}, {"$set": {
        "webhook_token_hash": zc._sha(t), "webhook_auto": bool(ok), "actualizado": zc._iso()}})
    await zc.evento(org, "webhook_auto", {"ok": bool(ok)})
    if ok:
        return {"ok": True, "automatico": True, "mensaje": "Webhook conectado en tu ElevenLabs."}
    return {"ok": True, "automatico": False, "url": url,
            "mensaje": "No pude conectarlo solo. Pega esta URL en ElevenLabs → Agents → Settings → Post-call webhook."}


@router.get("/estado", dependencies=[Depends(require_api_key)])
async def estado_auto(request: Request):
    org = get_org(request)
    cfg = await zc.asegurar(org)
    sid_m, tok_m = _master()
    return {"ok": True, "telefonia_zynex": bool(sid_m and tok_m),
            "numero_pendiente": zc.mask(cfg.get("numero_pendiente")),
            "numero_saliente": zc.mask(cfg.get("numero_saliente")),
            "webhook_auto": bool(cfg.get("webhook_auto"))}
