"""Paquetes opcionales de datos por cliente.

El arranque del servidor ya NO siembra datos de negocio: un cliente nuevo
empieza vacío. Lo específico de un vertical vive aquí y se instala a pedido,
SOLO en el org que lo solicita:

    await install_pack(org_id, "cod_colombia")
    POST /api/packs/{pack}/install     GET /api/packs

`cod_colombia` = call-center COD Colombia: transportadoras, novedades,
skills del copiloto, voces, prompts de Sofía y reglas de WhatsApp.
Idempotente: reinstalar no duplica (y actualiza catálogos de referencia).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from db import get_db

PACKS: dict[str, dict] = {
    "cod_colombia": {
        "key": "cod_colombia",
        "name": "COD Colombia",
        "description": ("Call-center de pedidos contra entrega en Colombia: "
                        "transportadoras y sus plazos de oficina, novedades, "
                        "skills del copiloto, voces, prompts de Sofía y reglas "
                        "de WhatsApp para reclamo en oficina."),
        # Texto extra para el prompt del agente cuando el paquete está instalado.
        "agent_prompt": (
            "Este negocio opera un call-center COD (pago contra entrega). Los "
            "\"semáforos\" de la cola son: rojo (≤1 día), amarillo (mitad del "
            "plazo), verde (más tiempo), gris (sin reclamo). Cuando pidan una "
            "acción masiva (ej. \"programa cadencias a los rojos\"), usa get_queue "
            "primero, luego schedule_cadence por cada uno, y resume qué hiciste."),
        # Plantillas de agentes de voz propias del vertical (wizard de custom-agents).
        "agent_templates": {
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
                    "razón real antes de aceptar. El protector es ANTIFLUIDO — nunca uses la "
                    "palabra prohibida (mantén 'antifluido'). ACCIONES: reagendar_entrega si acepta nueva fecha; confirmar_recogida si va "
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
        },
        # Perfil sugerido: solo se aplica si el cliente aún no tiene perfil.
        "profile_defaults": {"sector": "E-commerce contra entrega (COD)",
                             "pais": "CO", "moneda": "COP",
                             "zona_horaria": "America/Bogota", "idioma": "es"},
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _own(doc: dict, org_id: str) -> dict:
    """Copia de una semilla para un org: id propio (las semillas comparten id)."""
    return {**doc, "id": str(uuid.uuid4()), "org_id": org_id}


def _con_marca(texto: str, marca: str) -> str:
    """Sustituye la marca de la semilla por la del cliente (o un genérico)."""
    de = f"de {marca}" if marca else "de nuestro equipo"
    return (texto.replace("asesora del equipo Litper (Colombia)", f"asesora {de}")
                 .replace("del equipo Litper", de)
                 .replace("equipo Litper", marca or "nuestro equipo")
                 .replace("Litper", marca or "nuestro equipo"))


async def _install_cod_colombia(org_id: str) -> dict:
    from data import (CARRIERS_SEED, NOVEDADES_SEED, SKILLS_SEED, VOICES_SEED,
                      PROMPTS_SEED, WHATSAPP_RULES_SEED)
    db = get_db()
    for c in CARRIERS_SEED:
        await db.carriers.update_one({"org_id": org_id, "slug": c["slug"]},
                                     {"$set": {**c, "org_id": org_id}}, upsert=True)
    for n in NOVEDADES_SEED:
        await db.carrier_novedades.update_one(
            {"org_id": org_id, "carrier": n["carrier"],
             "estatus_carrier": n["estatus_carrier"]},
            {"$set": {**n, "org_id": org_id}}, upsert=True)
    for s in SKILLS_SEED:
        await db.copilot_skills.update_one(
            {"org_id": org_id, "trigger": s["trigger"]},
            {"$setOnInsert": {**_own(s, org_id), "is_seed": True}}, upsert=True)
    for v in VOICES_SEED:
        await db.voice_profiles.update_one(
            {"org_id": org_id, "elevenlabs_voice_id": v["elevenlabs_voice_id"]},
            {"$setOnInsert": _own(v, org_id)}, upsert=True)
    # La marca del guion sembrado es la del CLIENTE (perfil), nunca una fija.
    perfil = await db.org_profiles.find_one({"org_id": org_id}, {"_id": 0, "empresa": 1}) or {}
    marca = (perfil.get("empresa") or "").strip()
    for pr in PROMPTS_SEED:
        pr = {**pr, **{k: _con_marca(pr.get(k) or "", marca)
                       for k in ("system_prompt", "first_message")}}
        key = {"org_id": org_id, "name": pr["name"], "scope": pr["scope"],
               "country": pr.get("country")}
        existing = await db.prompts.find_one(key, {"_id": 0, "system_prompt": 1})
        if not existing:
            await db.prompts.insert_one(_own(pr, org_id))
            continue
        # Estructura antigua → se actualiza al guion vigente (como hacía el arranque).
        sp = existing.get("system_prompt") or ""
        if not sp.lstrip().startswith("# Personalidad") or "impermeable" in sp.lower():
            await db.prompts.update_one(key, {"$set": {
                "system_prompt": pr["system_prompt"], "first_message": pr["first_message"],
                "variables": pr["variables"], "updated_at": _now()}})
    for rule in WHATSAPP_RULES_SEED:
        await db.whatsapp_rules.update_one(
            {"org_id": org_id, "rule_key": rule["rule_key"]},
            {"$setOnInsert": {"id": str(uuid.uuid4()), "org_id": org_id,
                              "created_at": rule["created_at"],
                              "media_url": rule["media_url"], "active": rule["active"],
                              "notes": rule["notes"]},
             "$set": {"template_name": rule["template_name"],
                      "template_language": rule["template_language"],
                      "days_min": rule["days_min"], "days_max": rule["days_max"],
                      "updated_at": _now()}},
            upsert=True)
    return {"carriers": len(CARRIERS_SEED), "novedades": len(NOVEDADES_SEED),
            "skills": len(SKILLS_SEED), "voices": len(VOICES_SEED),
            "prompts": len(PROMPTS_SEED), "whatsapp_rules": len(WHATSAPP_RULES_SEED)}


_INSTALLERS = {"cod_colombia": _install_cod_colombia}


async def install_pack(org_id: str, pack: str) -> dict:
    """Instala `pack` SOLO en `org_id`. Idempotente."""
    if pack not in PACKS:
        raise ValueError(f"Paquete desconocido: {pack}")
    if not org_id:
        raise ValueError("org_id obligatorio")
    counts = await _INSTALLERS[pack](org_id)
    db = get_db()
    defaults = PACKS[pack].get("profile_defaults")
    if defaults and not await db.org_profiles.find_one({"org_id": org_id}, {"_id": 0}):
        await db.org_profiles.insert_one({**defaults, "org_id": org_id, "updated_at": _now()})
    await db.org_packs.update_one(
        {"org_id": org_id, "pack": pack},
        {"$set": {"org_id": org_id, "pack": pack, "installed_at": _now()}}, upsert=True)
    return {"ok": True, "pack": pack, "org_id": org_id, "installed": counts}


async def installed_packs(org_id: str) -> list[str]:
    docs = await get_db().org_packs.find({"org_id": org_id}, {"_id": 0, "pack": 1}).to_list(50)
    return [d["pack"] for d in docs]


async def agent_prompt_addendum(org_id: str) -> str:
    """Instrucciones extra del agente según los paquetes instalados del org."""
    return "\n".join(PACKS[p]["agent_prompt"] for p in await installed_packs(org_id)
                     if p in PACKS and PACKS[p].get("agent_prompt"))
