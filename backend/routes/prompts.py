"""Routes: /prompts — Sofía's call-script hierarchy.

Hierarchy (highest priority wins):
    campaign  (matches carrier_slug or campaign_key)  →
    product   (matches order.items[*].product_id)      →
    global    (matches country)

The default seeded Sofía script implements the official LIT-LOG-RO flow
(office claim in {carrier} · {city} · {office_address}, urgency
{days_left}/{deadline_text}, extension ticket up to 10 days, Colombian tone
under 60s, ALWAYS "antifluido" — NEVER "impermeable").
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from agent import router as llm_router
from db import get_db
from deps import require_api_key
from models import (Prompt, PromptIn, PromptUpdate, PromptGenerateIn,
                    PromptResolveIn)
from elevenlabs_client import get_client as get_eleven

router = APIRouter(prefix="/prompts", tags=["prompts"],
                   dependencies=[Depends(require_api_key)])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@router.get("", response_model=list[Prompt])
async def list_prompts(scope: Optional[str] = None,
                       country: Optional[str] = None):
    q: dict = {}
    if scope:
        q["scope"] = scope
    if country:
        q["country"] = country
    docs = await get_db().prompts.find(q, {"_id": 0}) \
        .sort([("priority", -1), ("created_at", -1)]).to_list(500)
    return docs


@router.get("/{prompt_id}", response_model=Prompt)
async def get_prompt(prompt_id: str):
    doc = await get_db().prompts.find_one({"id": prompt_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Prompt not found")
    return doc


@router.post("", response_model=Prompt, status_code=201)
async def create_prompt(p: PromptIn):
    doc = Prompt(**p.model_dump())
    await get_db().prompts.insert_one(doc.model_dump())
    return doc


@router.patch("/{prompt_id}", response_model=Prompt)
async def update_prompt(prompt_id: str, patch: PromptUpdate):
    db = get_db()
    existing = await db.prompts.find_one({"id": prompt_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Prompt not found")
    upd = {k: v for k, v in patch.model_dump().items() if v is not None}
    upd["updated_at"] = _iso()
    await db.prompts.update_one({"id": prompt_id}, {"$set": upd})
    doc = await db.prompts.find_one({"id": prompt_id}, {"_id": 0})
    return doc


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str):
    r = await get_db().prompts.delete_one({"id": prompt_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Prompt not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Resolve — pick the best matching prompt for a given context.
# ---------------------------------------------------------------------------
async def _pick_prompt(*, country: Optional[str], product_id: Optional[str],
                       carrier_slug: Optional[str]) -> dict | None:
    db = get_db()
    # Load all active prompts once — the collection is small.
    all_prompts = await db.prompts.find({"active": True}, {"_id": 0}) \
        .sort("priority", -1).to_list(500)

    def score(p: dict) -> int:
        s = 0
        scope = p.get("scope")
        if scope == "campaign":
            if carrier_slug and p.get("campaign_key") == carrier_slug:
                s += 300
            elif p.get("campaign_key"):
                return -1
        if scope == "product":
            if product_id and p.get("product_id") == product_id:
                s += 200
            elif p.get("product_id"):
                return -1
        if scope == "global":
            s += 100
        if p.get("country") and country and p["country"] == country:
            s += 20
        elif p.get("country") and country and p["country"] != country:
            return -1
        s += int(p.get("priority", 0))
        return s

    best = None
    best_score = -1
    for p in all_prompts:
        sc = score(p)
        if sc > best_score:
            best = p
            best_score = sc
    return best


@router.post("/resolve",
             summary="Return the best-matching prompt for an order/product/country/carrier. "
                     "Order variables (product_name, days_left, ...) are ALSO rendered.")
async def resolve_prompt(payload: PromptResolveIn):
    db = get_db()
    country = payload.country
    product_id = payload.product_id
    carrier_slug = payload.carrier_slug
    order_vars: dict = {}

    if payload.order_id:
        # Reuse the prompt-vars renderer on orders
        order = await db.orders.find_one({"id": payload.order_id}, {"_id": 0})
        if order:
            country = country or order.get("country")
            carrier_slug = carrier_slug or order.get("carrier_slug")
            # Render vars
            from routes.orders import order_prompt_vars  # local to avoid cycles
            order_vars = await order_prompt_vars(payload.order_id)

    p = await _pick_prompt(country=country, product_id=product_id,
                           carrier_slug=carrier_slug)
    if not p:
        raise HTTPException(404, "No hay ningún prompt activo que aplique. Crea uno primero.")

    rendered = _render_prompt(p, order_vars)
    return {
        "prompt": p,
        "rendered_system_prompt": rendered["system_prompt"],
        "rendered_first_message": rendered["first_message"],
        "variables": order_vars,
    }


def _render_prompt(prompt: dict, vars_: dict) -> dict:
    sp = prompt.get("system_prompt") or ""
    fm = prompt.get("first_message") or ""
    for k, v in (vars_ or {}).items():
        needle = "{" + str(k) + "}"
        if needle in sp: sp = sp.replace(needle, str(v))
        if needle in fm: fm = fm.replace(needle, str(v))
    return {"system_prompt": sp, "first_message": fm}


# ---------------------------------------------------------------------------
# Generate — LLM meta-prompt that authors a full Sofía script.
# ---------------------------------------------------------------------------
GENERATE_META = """Eres un experto en scripts de call-center para e-commerce COD en LATAM (Colombia principalmente).
Tu tarea es escribir el system prompt COMPLETO de Sofía, la IA que llama a clientes para que reclamen en oficina un pedido represado.

Requisitos NO NEGOCIABLES:
- Tono {tono}. Español colombiano natural. Duración objetivo < 60 segundos.
- La persona a llamar es real; sé breve, cálida y directa.
- SIEMPRE decir "antifluido" — NUNCA "impermeable".
- Flujo:
  1) Saludo + verifica identidad (¿Habla con {customer_first_name}?).
  2) Presenta que el pedido "{product_name}" está represado en la oficina de {carrier_name} en {city} · {office_address}.
  3) Urgencia clara: quedan {days_left} días ({deadline_text}) antes de devolución.
  4) Pregunta la fecha EXACTA de recogida.
  5) Si el cliente no puede en el plazo, ofrece un ticket de extensión (máx 10 días).
  6) Cierra con el número de guía {guia}.
- Manejo explícito de respuestas del cliente:
  * "Sí, lo recojo hoy/mañana" → confirma la fecha + agradece.
  * "En otro día" → sondea si cabe en {days_left} días. Si no, ofrece la extensión Dropi (max 10 d).
  * "Estoy de viaje" → agenda la extensión + confirma día exacto de regreso.
  * "Ya no lo quiero" → pregunta razón, ofrece la promo/precio si aplica ({promo_name} a {promo_price}), si insiste marca cancelación.
  * "Número equivocado" → cierra educada.
  * "Ya lo recogí" → confirma con qué guía y da las gracias.
- Producto: {product}. Beneficios: {beneficios}. Objeciones frecuentes: {objeciones}. Transportadora principal: {transportadora}.
- Variables permitidas (usa las llaves EXACTAS): {customer_first_name} {product_name} {carrier_name} {city} {office_address} {days_left} {deadline_text} {total_to_pay} {guia} {promo_name} {promo_price}.

Devuelve SOLO el system prompt (sin comentarios ni JSON). Empieza directamente con la primera línea del prompt.
"""


@router.post("/generate",
             summary="Ask the LLM router to author a full Sofía script for the given product / carrier / tone. "
                     "Returns { system_prompt, first_message, model_used }. "
                     "If the LLM omits required constraints (antifluido, full flow), we fall back to a "
                     "template-based script so the output is ALWAYS valid.")
async def generate_prompt(payload: PromptGenerateIn):
    meta = GENERATE_META.format(
        tono=payload.tono, product=payload.product,
        beneficios=payload.beneficios or "—",
        objeciones=payload.objeciones or "—",
        transportadora=payload.transportadora or "—",
        # placeholders — the LLM will echo them into the output prompt
        customer_first_name="{customer_first_name}", product_name="{product_name}",
        carrier_name="{carrier_name}", city="{city}", office_address="{office_address}",
        days_left="{days_left}", deadline_text="{deadline_text}",
        total_to_pay="{total_to_pay}", guia="{guia}",
        promo_name="{promo_name}", promo_price="{promo_price}",
    )
    llm_ok = True
    llm_err: str | None = None
    text = ""
    model = "template-fallback"
    try:
        text, model = await llm_router.call(
            system=("Eres un redactor de scripts de call-center e-commerce COD en LATAM. "
                    "Sigue las REGLAS DURAS al pie de la letra. "
                    "SIEMPRE dices 'antifluido', NUNCA 'impermeable'. "
                    "Escribe el system prompt COMPLETO con las 6 etapas del FLUJO."),
            messages=[{"role": "user", "content": meta}],
            tier="default", override=payload.model,
            session_id="prompt-generate",
        )
    except Exception as e:  # noqa: BLE001
        llm_ok = False
        llm_err = str(e)

    # Validation: the output MUST contain 'antifluido' AND either the FLUJO
    # structure OR be substantially long (>=900 chars). Otherwise we rebuild
    # from the deterministic template.
    txt_low = text.lower()
    is_valid = (
        llm_ok
        and "antifluido" in txt_low
        and "impermeable" not in txt_low
        and (len(text.strip()) >= 900 or "flujo" in txt_low)
    )
    if not is_valid:
        text = _template_sofia_script(payload)
        model = f"{model} (template-repaired)" if llm_ok else "template-fallback"

    first_message = (
        "Hola, ¿hablo con {customer_first_name}? "
        "Soy Sofía, del equipo Litper. Te llamo por tu pedido de {product_name} "
        "que está en la oficina de {carrier_name} en {city}."
    )
    return {
        "system_prompt": text.strip(),
        "first_message": first_message,
        "model_used": model,
        "llm_error": llm_err,
    }


def _template_sofia_script(p: PromptGenerateIn) -> str:
    """Deterministic Sofía script generator — used when the LLM output is
    invalid (missing 'antifluido', too short, or contains 'impermeable')."""
    bene = (p.beneficios or "").strip() or "producto de calidad Litper"
    obj  = (p.objeciones or "").strip() or "precio, tiempos de entrega, dudas de calidad"
    carrier = (p.transportadora or "el carrier asignado").strip()
    tono = (p.tono or "colombiano cálido y directo").strip()
    return f"""Eres Sofía, la asesora del equipo Litper (Colombia). Llamas a un cliente cuyo pedido de {p.product} está represado en oficina y necesitas que lo reclame ANTES de que se devuelva. Tono {tono}. Español natural. Duración objetivo < 60 segundos. Sé breve.

REGLAS DURAS
- SIEMPRE di "antifluido" al referirte al producto (NUNCA otras palabras como "im-per-meable").
- No prometas descuentos que no estén en {{promo_name}}.
- Confirma identidad ANTES de dar detalles del pedido.
- Producto y beneficios clave: {bene}.

FLUJO DE LA LLAMADA
1) Saludo + verifica identidad: "Hola, ¿hablo con {{customer_first_name}}?".
2) Presenta el tema: "Te llamo del equipo Litper. Tu pedido de {{product_name}} está represado en la oficina de {{carrier_name}} en {{city}} — {{office_address}}."
3) Urgencia: "Tienes {{days_left}} días para reclamarlo, {{deadline_text}}. Después el paquete se devuelve."
4) Pide fecha exacta de recogida: "¿Qué día exacto puedes ir a recogerlo?".
5) Guía + total: "El número de guía es {{guia}}. Total contra entrega: {{total_to_pay}}."
6) Si el cliente no puede en {{days_left}} días, ofrece ticket de EXTENSIÓN Dropi (hasta 10 días adicionales) y confirma el día exacto.

MANEJO DE OBJECIONES (frecuentes: {obj})
- "Sí, lo recojo hoy/mañana" → confirma fecha + agradece + cierra: "Perfecto, te esperan con la guía {{guia}}."
- "En otro día" → pregunta cuál. Si cabe en {{days_left}} días → confirma. Si no → ofrece extensión Dropi (max 10 d) y agenda el día.
- "Estoy de viaje" → agenda extensión + confirma día exacto de regreso.
- "Ya no lo quiero" → pregunta la razón. Si es precio, menciona {{promo_name}} a {{promo_price}} si aplica. Si insiste, marca cancelación educada.
- "Número equivocado" → "Perdona la molestia, gracias por atender." Cierra.
- "Ya lo recogí" → "¡Perfecto! ¿Me confirmas la guía {{guia}}? Gracias."
- Silencio / voicemail → deja un mensaje corto de 12 segundos con guía y deadline.

CIERRE
- Confirma día + guía + agradece por nombre. Menciona el carrier {carrier} para reforzar contexto.
"""


# ---------------------------------------------------------------------------
# Test voice — synthesize a preview via ElevenLabs.
# ---------------------------------------------------------------------------
class _TestVoiceIn(dict):
    pass


@router.post("/test-voice",
             summary="Synthesize a short audio preview via ElevenLabs so the operator "
                     "can hear how Sofía will say the opening line.")
async def test_voice(payload: dict):
    voice_id = (payload.get("voice_id") or os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", "")).strip()
    text = (payload.get("text") or "").strip()
    if not voice_id:
        raise HTTPException(400, "Falta voice_id. Elige una voz o define ELEVENLABS_DEFAULT_VOICE_ID.")
    if not text:
        raise HTTPException(400, "Falta text.")
    audio, err = await get_eleven().synthesize(voice_id=voice_id, text=text[:400])
    if err:
        raise HTTPException(502, f"ElevenLabs TTS falló: {err}")
    return Response(content=audio or b"", media_type="audio/mpeg",
                    headers={"Content-Disposition": 'inline; filename="sofia-preview.mp3"'})
