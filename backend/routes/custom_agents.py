"""Custom-Agents builder (BETA).

Modelo mental estándar Vapi/Retell/Dapta:
  Agent = Persona/Prompt + Voz + Herramientas + Base + Número + Prueba

Este router NO reemplaza a los 5 agentes operativos de Zynex (Riesgo/COD/…):
esos siguen en /api/agents. Aquí los usuarios crean SUS PROPIOS agentes de
voz para sus casos particulares (rescate, confirmación, citas, cobranza…).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from db import get_db
from deps import require_api_key
from retell_service import upsert_agent as _retell_upsert, configured as _retell_ok, place_call as _retell_call


router = APIRouter(prefix="/custom-agents", tags=["custom-agents"])


# ---------- Helpers ----------
def _iso() -> str: return datetime.now(timezone.utc).isoformat()


async def _org_id(request: Request) -> str:
    """Best-effort org resolution: prefer the JWT cookie, fall back to header."""
    try:
        from routes.auth import _decode, COOKIE_NAME
        tok = request.cookies.get(COOKIE_NAME)
        claims = _decode(tok) if tok else None
        if claims and claims.get("org"): return claims["org"]
    except Exception:
        pass
    header_org = request.headers.get("X-Org-Id", "").strip()
    return header_org or "default"


# ---------- Models ----------
ALLOWED_TOOLS = {
    # Non-money (safe to auto-execute)
    "reagendar_entrega", "confirmar_pedido",
    "consultar_disponibilidad", "enviar_whatsapp", "transferir_a_humano",
    # Money (require HITL confirmation — see routes/agent_tools.py)
    "registrar_promesa_pago", "enviar_link_pago",
    # Legacy aliases kept for back-compat with earlier drafts.
    "reagendar", "terminar_llamada", "registrar_pago",
}
ALLOWED_ESTADOS = {"borrador", "prueba", "en_vivo"}


class AgentIn(BaseModel):
    nombre:    str = Field(..., min_length=1, max_length=80)
    proposito: str = Field(..., min_length=1, max_length=80)  # template key or "personalizado"
    prompt:    str = Field(..., min_length=1, max_length=8000)
    saludo:    Optional[str] = ""
    cierre:    Optional[str] = ""
    tono:      Optional[str] = "profesional-cálido"
    idioma:    Optional[str] = "es-CO"
    voz_id:    Optional[str] = None
    tools:     list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)
    numero:    Optional[str] = None
    estado:    str = "borrador"
    retell_agent_id: Optional[str] = None


class AgentPatch(BaseModel):
    nombre:    Optional[str] = None
    prompt:    Optional[str] = None
    saludo:    Optional[str] = None
    cierre:    Optional[str] = None
    tono:      Optional[str] = None
    idioma:    Optional[str] = None
    voz_id:    Optional[str] = None
    tools:     Optional[list[str]] = None
    variables: Optional[list[str]] = None
    numero:    Optional[str] = None
    estado:    Optional[str] = None


def _validate(a: dict):
    bad = [t for t in (a.get("tools") or []) if t not in ALLOWED_TOOLS]
    if bad: raise HTTPException(400, f"Tools inválidas: {bad}")
    if a.get("estado") and a["estado"] not in ALLOWED_ESTADOS:
        raise HTTPException(400, f"Estado inválido: {a['estado']}")


# ---------- Templates (specialist prompts — Claude Haiku 0.3 · es-CO · antifluido · max 2 frases/turno) ----------
TEMPLATES = {
    "rescate_oficina": {
        "label": "Sofía Rescate — Rescate de pedidos en oficina",
        "prompt": (
            "Eres Sofía, asesora de {{empresa}}. Llamas a {{nombre}} porque su pedido de "
            "{{producto}} (pedido {{pedido_id}}) está represado en la oficina de "
            "{{transportadora}} en {{ciudad}} hace {{dias_oficina}} días y está a punto "
            "de devolverse. OBJETIVO: que el cliente recoja el pedido o reprograme la "
            "entrega HOY. Saludo cálido y directo. Explica en 1 frase la urgencia. Ofrece "
            "2 opciones: (a) recoger en la oficina, (b) reprogramar a su dirección. "
            "Objeciones: 'no tengo tiempo' → reprogramar; 'ya no lo quiero' → indaga la "
            "razón real antes de aceptar. El protector es ANTIFLUIDO, nunca impermeable. "
            "ACCIONES: reagendar_entrega si acepta nueva fecha; confirmar_recogida si va "
            "a la oficina; registrar_desistido SOLO si insiste (confirma antes: "
            "'¿cancelo el pedido {{pedido_id}}?'). Si no contesta o pide info escrita → "
            "enviar_whatsapp. Cierre: confirma la acción acordada. Máx 2 frases por turno."
        ),
        "tools":     ["reagendar_entrega", "confirmar_pedido", "enviar_whatsapp"],
        "variables": ["nombre", "empresa", "producto", "pedido_id", "transportadora", "ciudad", "dias_oficina"],
    },
    "confirmacion_cod": {
        "label": "Sofía Confirma — Confirmación de pedido COD",
        "prompt": (
            "Eres Sofía, asesora de {{empresa}}. Llamas a {{nombre}} para confirmar su "
            "pedido nuevo de {{producto}} (pedido {{pedido_id}}, valor {{valor}}) antes "
            "de despacharlo. OBJETIVO: validar que el pedido es real, que la dirección "
            "{{direccion}} es correcta y que estará para recibir y pagar contra entrega. "
            "Verifica 3 cosas: (1) sí lo pidió y lo quiere, (2) dirección exacta con "
            "punto de referencia, (3) que habrá quién reciba y pague {{valor}}. Resuelve "
            "dudas de precio/producto con seguridad (antifluido, garantía). No presiones "
            "si claramente no lo quiere. ACCIONES: confirmar_pedido(direccion, franja); "
            "corregir_datos si cambió; registrar_desistido si no lo quiere (confirma "
            "antes); enviar_whatsapp con resumen. Cierre: repite dirección y franja. "
            "Máx 2 frases por turno."
        ),
        "tools":     ["confirmar_pedido", "enviar_whatsapp"],
        "variables": ["nombre", "empresa", "producto", "pedido_id", "valor", "direccion"],
    },
    "citas": {
        "label": "Asistente Citas — Recordatorio con horarios reales",
        "prompt": (
            "Eres el asistente de voz de {{empresa}}. Llamas a {{nombre}} para recordar "
            "su cita con {{doctor}} el {{fecha_cita}} y confirmar asistencia. OBJETIVO: "
            "confirmar, reagendar o cancelar. REGLA CRÍTICA: NUNCA calcules fechas ni "
            "horarios; el horario disponible te lo entrega la herramienta "
            "consultar_disponibilidad ya calculado; solo léelo. Pregunta si asistirá: sí "
            "→ confirmar; no puede → ofrece el próximo horario de "
            "consultar_disponibilidad. Tono amable y breve. ACCIONES: confirmar_cita; "
            "reagendar_cita(nuevo_horario) usando SOLO horarios de "
            "consultar_disponibilidad; cancelar_cita (confirma antes); enviar_whatsapp "
            "con el detalle. Cierre: repite día y hora. Máx 2 frases por turno."
        ),
        "tools":     ["consultar_disponibilidad", "reagendar_entrega", "enviar_whatsapp"],
        "variables": ["nombre", "empresa", "doctor", "fecha_cita"],
    },
    "cobranza": {
        "label": "Asistente Cobranza — Promesa de pago con guardrail",
        "prompt": (
            "Eres el asistente de {{empresa}}. Llamas a {{nombre}} por un pago pendiente "
            "de {{valor}} del pedido {{pedido_id}}. DISCLOSURE OBLIGATORIO (primera "
            "frase, siempre): 'Hola {{nombre}}, esta es una llamada de {{empresa}} con "
            "asistencia automatizada sobre un tema de pago.' OBJETIVO: acordar el pago o "
            "una promesa de pago con fecha. Tono firme pero respetuoso, sin amenazas ni "
            "intimidación, cumpliendo normas de cobranza. Si puede pagar hoy → "
            "enviar_link_pago ({{link_pago}}). Si no → pide fecha concreta y "
            "registrar_promesa_pago(fecha) (confirma la fecha antes). Nunca inventes "
            "recargos ni consecuencias legales; si preguntan, di que un asesor humano "
            "los contactará. ACCIONES: enviar_link_pago; registrar_promesa_pago(fecha); "
            "transferir_a_humano si se complica o lo pide. Cierre: confirma lo acordado. "
            "Máx 2 frases por turno."
        ),
        "tools":     ["enviar_link_pago", "registrar_promesa_pago", "transferir_a_humano"],
        "variables": ["nombre", "empresa", "valor", "pedido_id", "link_pago"],
    },
    "personalizado": {
        "label": "Personalizado (en blanco)",
        "prompt": "Eres una operadora especializada en… (personaliza aquí). Máx 2 frases por turno. Nunca digas 'impermeable' (usa 'antifluido').",
        "tools":     [],
        "variables": [],
    },
}


@router.get("/templates", summary="Plantillas para el wizard (paso 1).")
async def list_templates():
    return {"templates": [
        {"key": k, "label": v["label"], "prompt": v["prompt"],
         "tools": v["tools"], "variables": v["variables"]}
        for k, v in TEMPLATES.items()
    ]}


@router.get("/tools", summary="Herramientas disponibles para casillas (paso 4).")
async def list_tools():
    labels = {
        "reagendar_entrega":       "Reagendar entrega",
        "confirmar_pedido":        "Confirmar pedido",
        "consultar_disponibilidad":"Consultar disponibilidad (fechas)",
        "enviar_whatsapp":         "Enviar WhatsApp",
        "transferir_a_humano":     "Transferir a humano",
        "registrar_promesa_pago":  "Registrar promesa de pago 💰",
        "enviar_link_pago":        "Enviar link de pago 💰",
    }
    keys = ["reagendar_entrega","confirmar_pedido","consultar_disponibilidad",
            "enviar_whatsapp","transferir_a_humano",
            "registrar_promesa_pago","enviar_link_pago"]
    return {"tools": [{"key": k, "label": labels[k],
                       "money": k in {"registrar_promesa_pago","enviar_link_pago"}}
                      for k in keys]}


@router.get("/voices", summary="Voces disponibles (por ahora estáticas, ElevenLabs).")
async def list_voices():
    return {"voices": [
        {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella (neutra ES)",       "provider": "elevenlabs"},
        {"id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli (colombiana joven)", "provider": "elevenlabs"},
        {"id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh (masculina neutra)", "provider": "elevenlabs"},
        {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel (voz cálida)",     "provider": "elevenlabs"},
    ]}


# ---------- CRUD ----------
@router.get("", summary="Lista los agentes personalizados de la org actual.",
            dependencies=[Depends(require_api_key)])
async def list_agents(request: Request):
    org_id = await _org_id(request)
    docs = await get_db().custom_agents.find(
        {"org_id": org_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return {"agents": docs}


@router.post("", summary="Crea un agente personalizado (borrador por defecto).",
             dependencies=[Depends(require_api_key)])
async def create_agent(payload: AgentIn, request: Request):
    org_id = await _org_id(request)
    a = payload.model_dump()
    _validate(a)
    a["id"]         = uuid.uuid4().hex[:12]
    a["org_id"]     = org_id
    a["created_at"] = _iso()
    a["updated_at"] = _iso()
    # If publishing straight to a live/test state, sync to Retell.
    if a.get("estado") in {"prueba", "en_vivo"} and _retell_ok():
        r = await _retell_upsert(a)
        if r.get("ok") and r.get("retell_agent_id"):
            a["retell_agent_id"] = r["retell_agent_id"]
        else:
            a["retell_error"] = str(r.get("response") or r.get("detail"))[:400]
    await get_db().custom_agents.insert_one(a)
    a.pop("_id", None)
    return {"ok": True, "agent": a, "retell_configured": _retell_ok()}


@router.patch("/{agent_id}", summary="Actualiza campos del agente.",
              dependencies=[Depends(require_api_key)])
async def patch_agent(agent_id: str, patch: AgentPatch, request: Request):
    org_id = await _org_id(request)
    db = get_db()
    a = await db.custom_agents.find_one({"id": agent_id, "org_id": org_id}, {"_id": 0})
    if not a: raise HTTPException(404, "Agente no encontrado.")
    changes = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if not changes: return {"ok": True, "agent": a, "changed": 0}
    merged = {**a, **changes}
    _validate(merged)
    changes["updated_at"] = _iso()
    # Re-sync to Retell whenever a "live" field changed or estado hit prueba/en_vivo.
    live_field_touched = bool({"prompt","voz_id","nombre","idioma","estado","tools"} & set(changes.keys()))
    if live_field_touched and merged.get("estado") in {"prueba","en_vivo"} and _retell_ok():
        r = await _retell_upsert(merged)
        if r.get("ok") and r.get("retell_agent_id"):
            changes["retell_agent_id"] = r["retell_agent_id"]
    await db.custom_agents.update_one({"id": agent_id}, {"$set": changes})
    fresh = await db.custom_agents.find_one({"id": agent_id}, {"_id": 0})
    return {"ok": True, "agent": fresh, "changed": len(changes)}


@router.delete("/{agent_id}", summary="Borra un agente personalizado.",
               dependencies=[Depends(require_api_key)])
async def delete_agent(agent_id: str, request: Request):
    org_id = await _org_id(request)
    r = await get_db().custom_agents.delete_one({"id": agent_id, "org_id": org_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Agente no encontrado.")
    return {"ok": True}


# ---------- Test call (BETA — validates config, does NOT dial for real yet) ----------
class TestCallIn(BaseModel):
    numero: str = Field(..., min_length=6)


@router.post("/{agent_id}/test-call",
             summary="Simula/dispara una llamada de prueba (BETA si falta Retell/número).",
             dependencies=[Depends(require_api_key)])
async def test_call(agent_id: str, payload: TestCallIn, request: Request):
    import os
    org_id = await _org_id(request)
    a = await get_db().custom_agents.find_one({"id": agent_id, "org_id": org_id}, {"_id": 0})
    if not a: raise HTTPException(404, "Agente no encontrado.")
    if not a.get("prompt"):
        raise HTTPException(400, "El agente no tiene prompt. Complétalo primero.")
    if not a.get("voz_id"):
        raise HTTPException(400, "Elige una voz antes de probar.")

    telnyx_ok = bool(os.environ.get("TELNYX_API_KEY", "").strip())
    eleven_ok = bool(os.environ.get("ELEVEN_API_KEY", "").strip())
    retell_ok = _retell_ok()

    # If Retell is set up AND the agent already has a retell_agent_id
    # (or we can create one now) AND a Telnyx-provisioned outbound
    # number exists → place a real call. Otherwise stay in BETA.
    if retell_ok and telnyx_ok and eleven_ok:
        rid = a.get("retell_agent_id")
        if not rid:
            up = await _retell_upsert(a)
            rid = up.get("retell_agent_id")
            if rid:
                await get_db().custom_agents.update_one(
                    {"id": agent_id}, {"$set": {"retell_agent_id": rid}}
                )
        if rid:
            r = await _retell_call(rid, payload.numero, a.get("numero"))
            return {"ok": r.get("ok", False), "beta": False,
                    "dialed": bool(r.get("ok")),
                    "detail": "Llamada iniciada via Retell.",
                    "response": r.get("response")}
    return {
        "ok": True, "beta": True, "dialed": False,
        "detail": ("Beta — falta configurar credenciales para llamada real. "
                   "Config del agente validada correctamente."),
        "would_call": payload.numero,
        "checks": {"retell": retell_ok, "telnyx": telnyx_ok, "elevenlabs": eleven_ok},
    }
