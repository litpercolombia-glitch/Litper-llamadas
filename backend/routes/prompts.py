"""Routes: /prompts — jerarquía de guiones de llamada (por cliente).
(El guion «Sofía» de reclamo en oficina es del paquete cod_colombia.)

Hierarchy (highest priority wins):
    campaign  (matches carrier_slug or campaign_key)  →
    product   (matches order.items[*].product_id)      →
    global    (matches country)

The default seeded Sofía script implements the official LIT-LOG-RO flow
(office claim in {carrier} · {city} · {office_address}, urgency
{days_left}/{deadline_text}, extension ticket up to 10 days, tone under 60s).
Los prompts son POR CLIENTE (org_id); el guion sembrado de Sofía viene solo
con el paquete "cod_colombia" (backend/packs.py). La marca sale del perfil
del cliente y la regla "antifluido" solo aplica si el producto lo menciona.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request, APIRouter, Depends, HTTPException
from tenant import org_from_request
from fastapi.responses import Response

from agent import router as llm_router
from db import get_db
from deps import get_org, require_api_key
from models import (Prompt, PromptIn, PromptUpdate, PromptGenerateIn,
                    PromptResolveIn)
from elevenlabs_client import client_for as eleven_for

router = APIRouter(prefix="/prompts", tags=["prompts"],
                   dependencies=[Depends(require_api_key)])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@router.get("", response_model=list[Prompt])
async def list_prompts(scope: Optional[str] = None,
                       country: Optional[str] = None,
                       org: str = Depends(get_org)):
    q: dict = {"org_id": org}
    if scope:
        q["scope"] = scope
    if country:
        q["country"] = country
    docs = await get_db().prompts.find(q, {"_id": 0}) \
        .sort([("priority", -1), ("created_at", -1)]).to_list(500)
    return docs


@router.get("/{prompt_id}", response_model=Prompt)
async def get_prompt(prompt_id: str, org: str = Depends(get_org)):
    doc = await get_db().prompts.find_one({"id": prompt_id, "org_id": org}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Prompt not found")
    return doc


@router.post("", response_model=Prompt, status_code=201)
async def create_prompt(p: PromptIn, org: str = Depends(get_org)):
    doc = Prompt(**p.model_dump())
    await get_db().prompts.insert_one({**doc.model_dump(), "org_id": org})
    return doc


@router.patch("/{prompt_id}", response_model=Prompt)
async def update_prompt(prompt_id: str, patch: PromptUpdate, org: str = Depends(get_org)):
    db = get_db()
    existing = await db.prompts.find_one({"id": prompt_id, "org_id": org}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Prompt not found")
    upd = {k: v for k, v in patch.model_dump().items() if v is not None}
    upd["updated_at"] = _iso()
    await db.prompts.update_one({"id": prompt_id, "org_id": org}, {"$set": upd})
    doc = await db.prompts.find_one({"id": prompt_id, "org_id": org}, {"_id": 0})
    return doc


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str, org: str = Depends(get_org)):
    r = await get_db().prompts.delete_one({"id": prompt_id, "org_id": org})
    if r.deleted_count == 0:
        raise HTTPException(404, "Prompt not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Resolve — pick the best matching prompt for a given context.
# ---------------------------------------------------------------------------
async def _pick_prompt(*, org: str, country: Optional[str], product_id: Optional[str],
                       carrier_slug: Optional[str]) -> dict | None:
    db = get_db()
    # Load all active prompts once — the collection is small.
    all_prompts = await db.prompts.find({"org_id": org, "active": True}, {"_id": 0}) \
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
async def resolve_prompt(payload: PromptResolveIn, org: str = Depends(get_org)):
    db = get_db()
    country = payload.country
    product_id = payload.product_id
    carrier_slug = payload.carrier_slug
    order_vars: dict = {}

    if payload.order_id:
        # Reuse the prompt-vars renderer on orders
        order = await db.orders.find_one({"id": payload.order_id, "org_id": org}, {"_id": 0})
        if order:
            country = country or order.get("country")
            carrier_slug = carrier_slug or order.get("carrier_slug")
            # Render vars
            from routes.orders import order_prompt_vars  # local to avoid cycles
            order_vars = await order_prompt_vars(payload.order_id, org)

    p = await _pick_prompt(org=org, country=country, product_id=product_id,
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
_REGLA_ANTIFLUIDO = '- SIEMPRE decir "antifluido" — NUNCA "impermeable".'


def _usa_antifluido(p: PromptGenerateIn) -> bool:
    """Regla de producto heredada: solo aplica si el propio producto es antifluido."""
    return "antifluido" in f"{p.product} {p.beneficios}".lower()


GENERATE_META = """Eres un experto en scripts de call-center para e-commerce COD en LATAM.
Tu tarea es escribir el system prompt COMPLETO de Sofía, la IA que llama a clientes para que reclamen en oficina un pedido represado.

Requisitos NO NEGOCIABLES:
- Tono {tono}. Español natural del país del cliente. Duración objetivo < 60 segundos.
- La persona a llamar es real; sé breve, cálida y directa.
{regla_producto}
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


GENERATE_META_GENERIC = """Eres un experto en guiones para agentes de voz que atienden o llaman a clientes de un negocio.
Escribe el system prompt COMPLETO del agente de voz de este negocio.

Negocio: {empresa}. Sector: {sector}. País: {pais}. Idioma: {idioma}.
Sobre el negocio: {descripcion}
Producto o servicio de esta llamada: {product}. Beneficios: {beneficios}. Objeciones frecuentes: {objeciones}.
Objetivo de la llamada: {objetivo}

Requisitos NO NEGOCIABLES:
- Tono {tono}. Frases cortas y naturales. Duración objetivo < 90 segundos.
- Estructura con estos 6 bloques, en este orden y con estos títulos: # Personalidad · # Entorno · # Tono · # Objetivo · # Guardrails · # Herramientas.
- El agente se presenta como asistente virtual de {empresa}; no inventes nombres de personas ni de marcas.
- No inventes precios, descuentos, fechas ni políticas: solo lo que venga en las variables o en este encargo.
- Variables permitidas (usa las llaves EXACTAS): {customer_first_name} {product_name} {city} {total_to_pay}.
- Incluye qué hacer si es número equivocado, si la persona pide no ser contactada y si pide hablar con una persona.

Devuelve SOLO el system prompt (sin comentarios ni JSON). Empieza directamente con la primera línea del prompt.
"""


def _objetivo_generico(p: PromptGenerateIn, profile: dict) -> str:
    if (p.objetivo or "").strip():
        return p.objetivo.strip()
    return (f"atender al cliente sobre {p.product}, resolver sus dudas y dejar acordado "
            "el siguiente paso (confirmar, agendar o registrar su decisión)")


def _template_generic_script(p: PromptGenerateIn, profile: dict) -> str:
    """Guion determinista para CUALQUIER negocio (sin paquete COD): sale del
    perfil del negocio. No menciona oficinas, guías ni transportadoras."""
    empresa = profile.get("empresa") or "nuestro equipo"
    sector = profile.get("sector") or ""
    descripcion = (profile.get("descripcion") or "").strip()
    bene = (p.beneficios or "").strip()
    obj = (p.objeciones or "").strip()
    tono = (p.tono or "cálido y directo").strip()
    objetivo = _objetivo_generico(p, profile)
    extra_guard = ""
    if bene:
        extra_guard += f"\n- Beneficios clave: {bene}."
    if obj:
        extra_guard += f"\n- Objeciones comunes y cómo responder con calma: {obj}."
    del_sector = f" ({sector})" if sector else ""
    sobre = f" Sobre el negocio: {descripcion}" if descripcion else ""
    return f"""# Personalidad
Eres el asistente virtual de {empresa}{del_sector}. Hablas con naturalidad, cercanía y respeto. Eres claro y vas al punto.

# Entorno
Estás en una llamada telefónica con un cliente de {empresa}, {{customer_first_name}}, sobre {{product_name}}.{sobre}

# Tono
{tono}. Frases cortas, ritmo pausado. Nunca suenes robótico. No hables más de 30 segundos seguidos sin dar espacio a la otra persona.

# Objetivo
{objetivo[0].upper() + objetivo[1:]}. Sigue estos pasos EN ORDEN:
1. Saluda y verifica con quién hablas: "Hola, ¿hablo con {{customer_first_name}}?".
2. Preséntate: "Te llamo de {empresa}" y di en una frase el motivo de la llamada sobre {p.product}.
3. Escucha. Responde las dudas solo con la información que tienes.
4. Acuerda el siguiente paso concreto (confirmar, agendar una fecha exacta o registrar su decisión).
5. Repite lo acordado y despídete con amabilidad.

# Guardrails
- No inventes precios, descuentos, fechas ni políticas que no estén en este guion o en las variables.
- No pidas datos sensibles (contraseñas, números de tarjeta).
- Si la persona pide no ser contactada → agradece, confírmalo y cierra.
- Si es un número equivocado → discúlpate en una frase y cierra.
- Si pide hablar con una persona o hay una queja seria → usa la herramienta para pedir que un humano la contacte.{extra_guard}

# Herramientas
Usa las herramientas del agente para dejar registro de lo que pasó:
- registrar_resultado({{ "outcome": "confirmado|no_contesta|reagendado|no_interesado|equivocado", "notas": "resumen breve" }})
- crear_tarea({{ "descripcion": "qué debe hacer una persona del equipo" }}) — solo si hace falta seguimiento humano.
- transferir_a_humano({{ "telefono": "número del cliente", "razon": "motivo" }}) — cuando pidan hablar con una persona.
"""


async def _generate_generic(payload: PromptGenerateIn, org_id: str, profile: dict) -> dict:
    """Generador para cualquier negocio: usa el perfil; sin Sofía ni reglas COD."""
    empresa = profile.get("empresa") or "nuestro equipo"
    meta = GENERATE_META_GENERIC.format(
        empresa=empresa, sector=profile.get("sector") or "—",
        pais=payload.country or profile.get("pais") or "—",
        idioma=profile.get("idioma") or "es",
        descripcion=(profile.get("descripcion") or "—"),
        product=payload.product, beneficios=payload.beneficios or "—",
        objeciones=payload.objeciones or "—", tono=payload.tono,
        objetivo=_objetivo_generico(payload, profile),
        customer_first_name="{customer_first_name}", product_name="{product_name}",
        city="{city}", total_to_pay="{total_to_pay}")
    llm_ok, llm_err, text, model = True, None, "", "template-fallback"
    try:
        text, model = await llm_router.call(
            system=("Eres un redactor de guiones para agentes de voz. Sigue los requisitos al "
                    "pie de la letra y escribe el system prompt COMPLETO con los 6 bloques."),
            messages=[{"role": "user", "content": meta}],
            tier="default", override=payload.model,
            session_id="prompt-generate", org_id=org_id)
    except Exception as e:  # noqa: BLE001
        llm_ok, llm_err = False, str(e)
    low = text.lower()
    valid = llm_ok and all(h in low for h in ("# personalidad", "# tono", "# guardrails"))
    if not valid:
        text = _template_generic_script(payload, profile)
        model = f"{model} (template-repaired)" if llm_ok else "template-fallback"
    return {
        "system_prompt": text.strip(),
        "first_message": ("Hola, ¿hablo con {customer_first_name}? "
                          f"Te llamo de {empresa}."),
        "model_used": model,
        "llm_error": llm_err,
        "flujo": "generico",
    }


@router.post("/generate",
             summary="Genera el guion de un agente de voz. Usa el PERFIL del negocio. Solo si el "
                     "cliente tiene instalado el paquete «cod_colombia» aplica el flujo COD de "
                     "reclamo en oficina (Sofía). Devuelve { system_prompt, first_message, "
                     "model_used, flujo }. Si el LLM falla o se salta requisitos, cae a una "
                     "plantilla para que la salida SIEMPRE sea válida.")
async def generate_prompt(payload: PromptGenerateIn, request: Request):
    org_id = org_from_request(request)   # fuera del try: una 401 debe responder 401
    from routes.org_profile import get_profile
    from packs import installed_packs
    profile = await get_profile(org_id)
    if "cod_colombia" not in await installed_packs(org_id):
        return await _generate_generic(payload, org_id, profile)

    # ---- Flujo COD (paquete cod_colombia instalado en ESTE cliente) ----
    meta = GENERATE_META.format(
        tono=payload.tono, product=payload.product,
        regla_producto=_REGLA_ANTIFLUIDO if _usa_antifluido(payload) else "",
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
    empresa = profile["empresa"] or "nuestro equipo"
    antifluido = _usa_antifluido(payload)
    llm_ok = True
    llm_err: str | None = None
    text = ""
    model = "template-fallback"
    try:
        text, model = await llm_router.call(
            system=("Eres un redactor de scripts de call-center e-commerce COD en LATAM. "
                    "Sigue las REGLAS DURAS al pie de la letra. "
                    + ("SIEMPRE dices 'antifluido', NUNCA 'impermeable'. " if antifluido else "")
                    + "Escribe el system prompt COMPLETO con las 6 etapas del FLUJO."),
            messages=[{"role": "user", "content": meta}],
            tier="default", override=payload.model,
            session_id="prompt-generate",
            org_id=org_id,
        )
    except Exception as e:  # noqa: BLE001
        llm_ok = False
        llm_err = str(e)

    # Validation: the output MUST have (either the 6-block structure or the
    # FLUJO wording OR be substantially long). Si el producto es antifluido,
    # además debe decir 'antifluido' y nunca 'impermeable'.
    txt_low = text.lower()
    has_blocks = all(h in txt_low for h in ("# personalidad", "# tono", "# guardrails"))
    is_valid = (
        llm_ok
        and (not antifluido or ("antifluido" in txt_low and "impermeable" not in txt_low))
        and (has_blocks or "flujo" in txt_low or len(text.strip()) >= 1200)
    )
    if not is_valid:
        text = _template_sofia_script(payload, empresa)
        model = f"{model} (template-repaired)" if llm_ok else "template-fallback"

    first_message = (
        "Hola, ¿hablo con {customer_first_name}? "
        f"Soy Sofía, de {empresa}. " "Te llamo por tu pedido de {product_name} "
        "que está en la oficina de {carrier_name} en {city}."
    )
    return {
        "system_prompt": text.strip(),
        "first_message": first_message,
        "model_used": model,
        "llm_error": llm_err,
        "flujo": "cod_colombia",
    }


def _template_sofia_script(p: PromptGenerateIn, empresa: str = "nuestro equipo") -> str:
    """Deterministic Sofía script generator — used when the LLM output is
    invalid. Emits the ElevenLabs 6-block structure (Personalidad · Entorno ·
    Tono · Objetivo · Guardrails · Herramientas)."""
    bene = (p.beneficios or "").strip() or "producto de calidad"
    regla = ("""- SIEMPRE di "antifluido" al referirte al producto (NUNCA otras palabras como "im-per-meable").
- SIEMPRE di "antifluido" — es la palabra correcta para nuestro material. (Regla repetida a propósito.)
""" if _usa_antifluido(p) else "")
    obj  = (p.objeciones or "").strip() or "precio, tiempos de entrega, dudas de calidad"
    carrier = (p.transportadora or "el carrier asignado").strip()
    tono = (p.tono or "cálido y directo").strip()
    return f"""# Personalidad
Eres Sofía, asesora de {empresa}. Mujer joven, profesional, servicial y muy natural. Hablas con cercanía y calidez sin perder eficacia. Trabajas en el equipo de reclamos en oficina.

# Entorno
Estás en una llamada telefónica saliente a un cliente cuyo pedido de {p.product} está represado en la oficina de {carrier or '{carrier_name}'} en {{city}} — {{office_address}}. El paquete se devuelve si no se recoge en {{days_left}} días ({{deadline_text}}). Total contra entrega: {{total_to_pay}}. Guía: {{guia}}.

# Tono
{tono}. Español natural. Frases cortas, ritmo pausado, contacto humano. Duración objetivo < 60 segundos. Nunca sonar robótica.

# Objetivo
Ayudar al cliente a recoger su pedido en oficina antes del vencimiento. Sigue estos pasos EN ORDEN:
1. Saluda y verifica identidad: "Hola, ¿hablo con {{customer_first_name}}?".
2. Presenta el motivo: "Te llamo de {empresa}. Tu pedido de {{product_name}} está represado en la oficina de {{carrier_name}} en {{city}} — {{office_address}}."
3. Da la urgencia: "Tienes {{days_left}} días ({{deadline_text}}) para reclamarlo antes de que se devuelva."
4. Pregunta la fecha EXACTA de recogida: "¿Qué día exacto puedes pasar a recogerlo?".
5. Comparte guía + total: "El número de guía es {{guia}}. Total contra entrega: {{total_to_pay}}."
6. Si el cliente NO puede en el plazo, ofrece un ticket de extensión Dropi (máximo 10 días) y confirma día exacto. Si aplica una promoción activa, menciónala como {{promo_name}} a {{promo_price}}.

# Guardrails
{regla}- No inventes descuentos, promociones ni fechas que no estén en las variables.
- No pidas datos sensibles (contraseñas, números de tarjeta).
- Si el cliente pide dejar de ser contactado (opt-out) → agradece, confírmalo y cierra educada.
- Si el número es equivocado → discúlpate breve y cuelga con educación.
- No hables por más de 60 segundos seguidos sin dar espacio a la respuesta del cliente.
- Producto y beneficios clave: {bene}. Objeciones comunes: {obj}.

# Herramientas
Usa las herramientas del agente para registrar cada resultado. Formato de parámetros:
- registrar_resultado({{ "outcome": "confirmado|no_contesta|extension|cancelado|equivocado|ya_recogio", "fecha_recogida": "YYYY-MM-DD | null", "notas": "resumen breve en español" }})
- crear_tarea({{ "titulo": "string", "prioridad": "alta|media|baja", "notas": "string" }}) — solo si hay algo que un humano debe seguir.
- transferir_humano({{ "razon": "string" }}) — usar cuando el cliente pide expresamente hablar con una persona o cuando detectes un problema grave (reclamo, queja formal).

Manejo rápido de respuestas frecuentes:
- "Sí, hoy/mañana lo recojo" → registrar_resultado outcome=confirmado + fecha. Cierra: "Perfecto, te esperan con la guía {{guia}}."
- "Otro día" → si cabe en {{days_left}} confirma; si no, ofrece extensión y registra outcome=extension.
- "Estoy de viaje" → ofrece extensión Dropi 10d, registra outcome=extension.
- "Ya no lo quiero" → indaga razón; menciona {{promo_name}} si aplica; si insiste, registra outcome=cancelado.
- "Ya lo recogí" → confirma la guía {{guia}}, registra outcome=ya_recogio.
- Silencio / voicemail → deja un mensaje corto de 12 segundos con la guía y el deadline.
"""


# ---------------------------------------------------------------------------
# Test voice — synthesize a preview via ElevenLabs.
# ---------------------------------------------------------------------------
class _TestVoiceIn(dict):
    pass


@router.post("/test-voice",
             summary="Synthesize a short audio preview via ElevenLabs so the operator "
                     "can hear how Sofía will say the opening line.")
async def test_voice(payload: dict, org: str = Depends(get_org)):
    eleven = await eleven_for(org)   # llave y voz por defecto de ESTE cliente
    voice_id = (payload.get("voice_id") or eleven.default_voice_id or "").strip()
    text = (payload.get("text") or "").strip()
    if not voice_id:
        raise HTTPException(400, "Falta voice_id. Elige una voz o define una voz por defecto en Conexiones > ElevenLabs.")
    if not text:
        raise HTTPException(400, "Falta text.")
    audio, err = await eleven.synthesize(voice_id=voice_id, text=text[:400])
    if err:
        raise HTTPException(502, f"ElevenLabs TTS falló: {err}")
    return Response(content=audio or b"", media_type="audio/mpeg",
                    headers={"Content-Disposition": 'inline; filename="sofia-preview.mp3"'})
