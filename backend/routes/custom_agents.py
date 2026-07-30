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
    "confirmar_pedido", "reagendar", "enviar_whatsapp",
    "transferir_a_humano", "terminar_llamada", "registrar_pago",
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


# ---------- Templates (pre-generated prompts) ----------
TEMPLATES = {
    "rescate_oficina": {
        "label": "Rescate de pedidos en oficina",
        "prompt": (
            "Eres una operadora COD amable, natural y directa. Tu misión es "
            "convencer a {{nombre}} de que retire su pedido de {{producto}} "
            "en la oficina antes de que se devuelva. Confirma la dirección "
            "({{direccion}}) y el valor a pagar ({{valor}}). Nunca digas la "
            "palabra 'impermeable'. Ofrece alternativas: cambio de dirección, "
            "reagendar entrega, o WhatsApp con la ubicación del punto de "
            "retiro. Si el cliente confirma, agenda; si no, negocia una vez."
        ),
        "tools":     ["confirmar_pedido", "reagendar", "enviar_whatsapp", "terminar_llamada"],
        "variables": ["nombre", "producto", "direccion", "valor"],
    },
    "confirmacion_cod": {
        "label": "Confirmación de pedido COD",
        "prompt": (
            "Eres una operadora que confirma pedidos COD. Saluda a {{nombre}}, "
            "confirma el producto {{producto}}, la dirección {{direccion}} y "
            "el valor {{valor}}. Si algo cambió, actualízalo. Cierra con "
            "próxima ventana de entrega. Nunca digas 'impermeable'."
        ),
        "tools":     ["confirmar_pedido", "reagendar", "terminar_llamada"],
        "variables": ["nombre", "producto", "direccion", "valor"],
    },
    "citas": {
        "label": "Recordatorio de citas",
        "prompt": (
            "Eres una asistente que recuerda citas. Saluda a {{nombre}}, "
            "recuérdale su cita el {{fecha_cita}} y ofrécele confirmar, "
            "reagendar o cancelar. Sé breve y cálida."
        ),
        "tools":     ["reagendar", "terminar_llamada"],
        "variables": ["nombre", "fecha_cita"],
    },
    "cobranza": {
        "label": "Cobranza / Recordatorio de pago",
        "prompt": (
            "Eres una asistente cordial de cobranza. Recuérdale a {{nombre}} "
            "que tiene un saldo pendiente por {{valor}}. Ofrécele opciones "
            "de pago y confirma el compromiso. Sé firme pero respetuosa."
        ),
        "tools":     ["registrar_pago", "transferir_a_humano", "enviar_whatsapp"],
        "variables": ["nombre", "valor"],
    },
    "personalizado": {
        "label": "Personalizado (en blanco)",
        "prompt": "Eres una operadora especializada en… (personaliza aquí).",
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
        "confirmar_pedido":     "Confirmar pedido",
        "reagendar":            "Reagendar",
        "enviar_whatsapp":      "Enviar WhatsApp",
        "transferir_a_humano":  "Transferir a humano",
        "terminar_llamada":     "Terminar llamada",
        "registrar_pago":       "Registrar pago",
    }
    return {"tools": [{"key": k, "label": labels[k]} for k in ALLOWED_TOOLS]}


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
    await get_db().custom_agents.insert_one(a)
    a.pop("_id", None)
    return {"ok": True, "agent": a}


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
             summary="Simula una llamada de prueba (BETA — sin marcar aún).",
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

    # Are voice/telephony creds even configured?
    telnyx_ok = bool(os.environ.get("TELNYX_API_KEY", "").strip())
    eleven_ok = bool(os.environ.get("ELEVEN_API_KEY", "").strip())
    if not telnyx_ok or not eleven_ok:
        return {
            "ok": True, "beta": True, "dialed": False,
            "detail": ("Beta — conecta Telnyx y ElevenLabs para llamadas reales. "
                       "Config del agente validada correctamente."),
            "would_call": payload.numero,
            "checks": {"telnyx": telnyx_ok, "elevenlabs": eleven_ok},
        }
    # Placeholder — hook up real Telnyx Voice + ElevenLabs SDK here.
    return {"ok": True, "beta": True, "dialed": False,
            "detail": "Telnyx/ElevenLabs configurados. Marcado real en la próxima iteración.",
            "would_call": payload.numero}
