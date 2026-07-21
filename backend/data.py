"""Seed data + reference tables for Litper Connect Hub."""
from datetime import date

# 12 Colombian carriers seed data
CARRIERS_SEED = [
    {"name": "Interrapidísimo", "slug": "interrapidisimo", "coverage_points": 1104,
     "max_recaudo_cop": 3000000, "office_claim_allowed": True, "office_claim_max_days": 4,
     "max_delivery_attempts": 2, "accepts_nequi_daviplata": True,
     "notes": "Nequi vía QR. Amplia cobertura."},
    {"name": "Envía", "slug": "envia", "coverage_points": 1423,
     "max_recaudo_cop": 2000000, "office_claim_allowed": True, "office_claim_max_days": 1,
     "max_delivery_attempts": 3, "accepts_nequi_daviplata": False,
     "notes": "Sólo oficinas autorizadas. Deadline 1 día → cadencia comprimida."},
    {"name": "Coordinadora", "slug": "coordinadora", "coverage_points": 1442,
     "max_recaudo_cop": 2000000, "office_claim_allowed": True, "office_claim_max_days": 8,
     "max_delivery_attempts": 2, "accepts_nequi_daviplata": False,
     "notes": "Reclamo hasta 8 días — cadencia distribuida."},
    {"name": "Jamv Drive", "slug": "jamv-drive", "coverage_points": 17,
     "max_recaudo_cop": 2000000, "office_claim_allowed": False, "office_claim_max_days": None,
     "max_delivery_attempts": 3, "accepts_nequi_daviplata": True,
     "notes": "Sin reclamo en oficina."},
    {"name": "Wiilog", "slug": "wiilog", "coverage_points": 45,
     "max_recaudo_cop": 1000000, "office_claim_allowed": True, "office_claim_max_days": 2,
     "max_delivery_attempts": 3, "accepts_nequi_daviplata": True,
     "notes": "Reclamo corto: 2 días."},
    {"name": "Domina", "slug": "domina", "coverage_points": 195,
     "max_recaudo_cop": 2500000, "office_claim_allowed": True, "office_claim_max_days": 6,
     "max_delivery_attempts": 3, "accepts_nequi_daviplata": False,
     "notes": "Sólo oficinas principales."},
    {"name": "TCC", "slug": "tcc", "coverage_points": 1307,
     "max_recaudo_cop": 1800000, "office_claim_allowed": True, "office_claim_max_days": 3,
     "max_delivery_attempts": 3, "accepts_nequi_daviplata": False,
     "notes": "Sólo oficinas principales."},
    {"name": "Veloces", "slug": "veloces", "coverage_points": 10,
     "max_recaudo_cop": 2500000, "office_claim_allowed": False, "office_claim_max_days": None,
     "max_delivery_attempts": 3, "accepts_nequi_daviplata": False,
     "notes": "Sin reclamo en oficina."},
    {"name": "99 Minutos", "slug": "99-minutos", "coverage_points": 47,
     "max_recaudo_cop": 800000, "office_claim_allowed": False, "office_claim_max_days": None,
     "max_delivery_attempts": 2, "accepts_nequi_daviplata": True,
     "notes": "Última milla urbana; sin oficina."},
    {"name": "Servientrega", "slug": "servientrega", "coverage_points": 1710,
     "max_recaudo_cop": 2000000, "office_claim_allowed": True, "office_claim_max_days": 8,
     "max_delivery_attempts": 2, "accepts_nequi_daviplata": False,
     "notes": "Máxima cobertura, reclamo largo (8 días)."},
    {"name": "Fleetex", "slug": "fleetex", "coverage_points": 9,
     "max_recaudo_cop": 3000000, "office_claim_allowed": True, "office_claim_max_days": 5,
     "max_delivery_attempts": 3, "accepts_nequi_daviplata": True,
     "notes": "Cobertura reducida."},
    {"name": "De Rocha", "slug": "de-rocha", "coverage_points": 4,
     "max_recaudo_cop": 2000000, "office_claim_allowed": True, "office_claim_max_days": 5,
     "max_delivery_attempts": 2, "accepts_nequi_daviplata": True,
     "notes": "Cobertura muy reducida."},
]

# Holidays (Colombia primary). Configurable — extend as needed.
HOLIDAYS_CO_2026 = {
    date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2),
    date(2026, 4, 3), date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8),
    date(2026, 6, 15), date(2026, 6, 29), date(2026, 7, 20), date(2026, 8, 7),
    date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 16),
    date(2026, 12, 8), date(2026, 12, 25),
}

COUNTRY_TIMEZONES = {
    "CO": "America/Bogota",
    "EC": "America/Guayaquil",
    "CL": "America/Santiago",
}

# Cadence windows (start_hour, end_hour) in local time.
WINDOWS = {
    "manana":   (9, 11),
    "mediodia": (12, 14),
    "tarde":    (15, 18),
    "noche":    (18, 20),
}


def semaphore_for(office_claim_max_days: int | None, days_left: int | None) -> str:
    """Return rojo/amarillo/verde/gris for the office-claim countdown."""
    if office_claim_max_days is None or days_left is None:
        return "gris"
    if days_left <= 1:
        return "rojo"
    if days_left <= max(1, office_claim_max_days // 2):
        return "amarillo"
    return "verde"


# Sample novedades seed (owner has 426 rows to load later — this is a bootstrap
# subset covering the main categories & carriers so the reference page + endpoint
# have real data to display).
NOVEDADES_SEED = [
    # ----- RECLAMO_EN_OFICINA -----
    {"carrier": "Interrapidísimo", "estatus_carrier": "EN OFICINA PARA RECLAMAR",
     "estatus_dropi": "En oficina",
     "significado": "Paquete en oficina esperando ser reclamado por el destinatario.",
     "accion": "Contactar al cliente por llamada + WhatsApp. Cadencia 5 intentos.",
     "categoria": "RECLAMO_EN_OFICINA"},
    {"carrier": "Envía", "estatus_carrier": "PARA RECLAMAR EN OFICINA",
     "estatus_dropi": "En oficina",
     "significado": "Deadline de 1 día. Alta prioridad — cadencia comprimida.",
     "accion": "Llamar HOY en ventanas manana/mediodia/tarde/noche + WhatsApp.",
     "categoria": "RECLAMO_EN_OFICINA"},
    {"carrier": "Servientrega", "estatus_carrier": "OFICINA PARA RECLAMAR",
     "estatus_dropi": "En oficina",
     "significado": "Deadline de 8 días. Cadencia distribuida en 3 días.",
     "accion": "Cadencia estándar de 5 intentos distribuida.",
     "categoria": "RECLAMO_EN_OFICINA"},
    {"carrier": "Coordinadora", "estatus_carrier": "DISPONIBLE EN OFICINA",
     "estatus_dropi": "En oficina",
     "significado": "Deadline 8 días. Distribuida.",
     "accion": "Cadencia estándar.",
     "categoria": "RECLAMO_EN_OFICINA"},
    {"carrier": "TCC", "estatus_carrier": "PARA RECLAMAR EN AGENCIA",
     "estatus_dropi": "En oficina",
     "significado": "Reclamo hasta 3 días. Media prioridad.",
     "accion": "Cadencia 2-3 días.",
     "categoria": "RECLAMO_EN_OFICINA"},

    # ----- DEVOLUCION -----
    {"carrier": "Interrapidísimo", "estatus_carrier": "DEVUELTO A REMITENTE",
     "estatus_dropi": "Devolución",
     "significado": "Paquete devuelto — cliente no reclamó ni recibió.",
     "accion": "Cerrar cadencia, notificar seller. Costo asumido.",
     "categoria": "DEVOLUCION"},
    {"carrier": "Envía", "estatus_carrier": "DEVOLUCION EN PROCESO",
     "estatus_dropi": "Devolución",
     "significado": "Paquete en proceso de retorno al seller.",
     "accion": "Ticket automático para el equipo de logística.",
     "categoria": "DEVOLUCION"},

    # ----- NOVEDAD -----
    {"carrier": "Servientrega", "estatus_carrier": "DIRECCION INCORRECTA",
     "estatus_dropi": "Novedad",
     "significado": "Dirección no encontrada. Reintentar entrega con nueva dirección.",
     "accion": "Crear ticket tipo `cambio_direccion` + contactar cliente.",
     "categoria": "NOVEDAD"},
    {"carrier": "Coordinadora", "estatus_carrier": "CLIENTE NO CONTACTADO",
     "estatus_dropi": "Novedad",
     "significado": "Repartidor no logró contactar al destinatario.",
     "accion": "Llamada AI + WhatsApp. Reprogramar entrega.",
     "categoria": "NOVEDAD"},
    {"carrier": "TCC", "estatus_carrier": "SIN COBERTURA",
     "estatus_dropi": "Novedad",
     "significado": "Zona sin cobertura del carrier.",
     "accion": "Cambiar a carrier con cobertura + notificar cliente.",
     "categoria": "NOVEDAD"},

    # ----- TRANSITO -----
    {"carrier": "Interrapidísimo", "estatus_carrier": "EN TRANSITO",
     "estatus_dropi": "En camino",
     "significado": "Paquete en tránsito hacia destino.",
     "accion": "Ninguna. Monitorear.",
     "categoria": "TRANSITO"},
    {"carrier": "Envía", "estatus_carrier": "EN RUTA",
     "estatus_dropi": "En camino",
     "significado": "Paquete asignado a repartidor.",
     "accion": "Ninguna.",
     "categoria": "TRANSITO"},
    {"carrier": "Servientrega", "estatus_carrier": "EN BODEGA",
     "estatus_dropi": "En camino",
     "significado": "Paquete recibido en bodega, pendiente de despacho.",
     "accion": "Ninguna.",
     "categoria": "TRANSITO"},

    # ----- ENTREGADO -----
    {"carrier": "Interrapidísimo", "estatus_carrier": "ENTREGADO",
     "estatus_dropi": "Entregado",
     "significado": "Paquete entregado exitosamente.",
     "accion": "Cerrar cadencia, marcar orden como resuelta.",
     "categoria": "ENTREGADO"},
    {"carrier": "Envía", "estatus_carrier": "ENTREGADO OK",
     "estatus_dropi": "Entregado",
     "significado": "Entrega confirmada por el cliente.",
     "accion": "Cerrar cadencia + solicitar reseña vía WhatsApp.",
     "categoria": "ENTREGADO"},
    {"carrier": "Servientrega", "estatus_carrier": "ENTREGA EXITOSA",
     "estatus_dropi": "Entregado",
     "significado": "Recaudo COD recibido.",
     "accion": "Cerrar orden.",
     "categoria": "ENTREGADO"},

    # ----- OTRO -----
    {"carrier": "99 Minutos", "estatus_carrier": "CANCELADO POR CLIENTE",
     "estatus_dropi": "Cancelado",
     "significado": "Cliente canceló el pedido.",
     "accion": "Ticket tipo `otro` + notificar seller.",
     "categoria": "OTRO"},
    {"carrier": "Domina", "estatus_carrier": "PENDIENTE VALIDACION",
     "estatus_dropi": "Pendiente",
     "significado": "Datos del envío pendientes de validación por el carrier.",
     "accion": "Contactar al operador del carrier.",
     "categoria": "OTRO"},
]


# Seed for Copilot skills — reusable prompts / workflows for Marcus.
import uuid as _uuid
from datetime import datetime as _dt, timezone as _tz


def _new_uid() -> str:
    return str(_uuid.uuid4())


def _iso_now() -> str:
    return _dt.now(_tz.utc).isoformat()


SKILLS_SEED = [
    {
        "id": _new_uid(),
        "name": "Revisar cola del día",
        "trigger": "revisar-cola",
        "description": "Resumen priorizado de la cola: rojos, amarillos, verdes.",
        "instructions": (
            "Llama get_queue para obtener toda la cola. Agrupa por semáforo y "
            "genera un resumen ejecutivo priorizado: primero los ROJOS (con nombre, "
            "carrier, ciudad, teléfono, días restantes), luego amarillos, luego verdes. "
            "Sugiere para cada rojo si conviene programar cadencia inmediatamente."),
        "steps": ["get_queue()", "Resumen por semáforo", "Recomendación por rojo"],
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
    {
        "id": _new_uid(),
        "name": "Recuperar pedidos en oficina (rojos)",
        "trigger": "recuperar-rojos",
        "description": "Para cada pedido en rojo, programa cadencia y envía WhatsApp inicial.",
        "instructions": (
            "1) Llama get_queue con semaphore='rojo'. "
            "2) Para cada pedido, llama schedule_cadence(queue_id). "
            "3) Redacta un WhatsApp cálido en español pidiendo confirmar recogida y "
            "envíalo con send_whatsapp(phone=customer_phone, text=..., queue_id=...). "
            "4) Al final, reporta cuántos programaste y cuántos WhatsApp enviaste."),
        "steps": ["get_queue(rojo)", "schedule_cadence per item",
                 "send_whatsapp per item", "reporte final"],
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
    {
        "id": _new_uid(),
        "name": "Redactar WhatsApp de recogida",
        "trigger": "redactar-whatsapp",
        "description": "Genera un mensaje WhatsApp personalizado para pedir recogida.",
        "instructions": (
            "El usuario te dirá el nombre del cliente, transportadora y ciudad. "
            "Redacta un WhatsApp corto, amable, en español neutro, que le pida "
            "confirmar si recogerá el pedido hoy. Máximo 3 líneas. NO envíes; sólo "
            "muestra el texto propuesto. Si el usuario dice 'envíalo' entonces "
            "llama send_whatsapp con el teléfono que te dio."),
        "steps": [],
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
    {
        "id": _new_uid(),
        "name": "Resumen de novedades por transportadora",
        "trigger": "novedades-carrier",
        "description": "Mapea estatus de un carrier a acciones operativas.",
        "instructions": (
            "El usuario mencionará un carrier (ej. 'Servientrega'). "
            "Llama get_carrier_novedades(carrier=<ese carrier>). "
            "Presenta la tabla agrupada por categoría: RECLAMO_EN_OFICINA, DEVOLUCION, "
            "NOVEDAD, TRANSITO, ENTREGADO, OTRO. Para cada, muestra estatus + acción."),
        "steps": ["get_carrier_novedades(carrier=…)", "Agrupar por categoría"],
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
]


# 6 preferred ElevenLabs voices seeded on boot (owner's confirmed voice_ids).
VOICES_SEED = [
    {"id": _new_uid(), "name": "Sofía CO", "elevenlabs_voice_id": "scn1gPWkdVd8FhODJoei",
     "language": "es-CO", "country": "CO", "is_default": True,
     "description": "Voz principal Colombia — cálida, cercana.",
     "created_at": _iso_now(), "updated_at": _iso_now()},
    {"id": _new_uid(), "name": "Sofía EC", "elevenlabs_voice_id": "wmXH34EF7LAsKTjOZWWt",
     "language": "es-EC", "country": "EC", "is_default": True,
     "description": "Voz principal Ecuador.",
     "created_at": _iso_now(), "updated_at": _iso_now()},
    {"id": _new_uid(), "name": "Voz 3", "elevenlabs_voice_id": "MqSrMUk8EHh32HBKytrG",
     "language": "es", "country": "OTHER", "is_default": False, "description": "",
     "created_at": _iso_now(), "updated_at": _iso_now()},
    {"id": _new_uid(), "name": "Voz 4", "elevenlabs_voice_id": "57D8YIbQSuE3REDPO6Vm",
     "language": "es", "country": "OTHER", "is_default": False, "description": "",
     "created_at": _iso_now(), "updated_at": _iso_now()},
    {"id": _new_uid(), "name": "Voz 5", "elevenlabs_voice_id": "86V9x9hrQds83qf7zaGn",
     "language": "es", "country": "OTHER", "is_default": False, "description": "",
     "created_at": _iso_now(), "updated_at": _iso_now()},
    {"id": _new_uid(), "name": "Voz 6", "elevenlabs_voice_id": "VmejBeYhbrcTPwDniox7",
     "language": "es", "country": "OTHER", "is_default": False, "description": "",
     "created_at": _iso_now(), "updated_at": _iso_now()},
]



# Catalog products with promotions (seeded on boot, idempotent by nombre).
PRODUCTS_SEED = [
    {
        "id": _new_uid(),
        "nombre": "Protector Antifluido Premium",
        "slug": "protector-antifluido-premium",
        "descripcion": ("Protector de colchón antifluido premium. NUNCA decir "
                        "'impermeable' — usamos 'antifluido'."),
        "instrucciones_llamada": (
            "Tono cálido, colombiano, cercano. Menciona la promo por "
            "{promo_name}. Si es combo, di 'tu pedido de {product_name}'. "
            "Recuerda al cliente que puede reclamar en oficina antes de que "
            "venza el plazo del carrier."),
        "promotions": [
            {
                "id": _new_uid(),
                "sku_pattern": "PROTECTOR MAS FUNDAS",
                "nombre_comercial": "Protector Antifluido Premium + 2 Fundas de regalo",
                "descripcion": "Protector antifluido + 2 fundas antifluido de regalo.",
                "precio_lista": 189000,
                "precio_promo": 149000,
                "bonos": ["2 fundas antifluido", "Envío contra entrega"],
                "activa": True,
            },
            {
                "id": _new_uid(),
                "sku_pattern": "PROTECTOR",
                "nombre_comercial": "Protector Antifluido Premium",
                "descripcion": "Protector de colchón antifluido premium.",
                "precio_lista": 129000,
                "precio_promo": 99000,
                "bonos": ["Envío contra entrega"],
                "activa": True,
            },
        ],
        "activo": True,
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
    {
        "id": _new_uid(),
        "nombre": "Colcha + Sábana King 600 hilos",
        "slug": "colcha-sabana-king-600",
        "descripcion": "Set de colcha y sábana king de 600 hilos.",
        "instrucciones_llamada": (
            "Menciona la textura suave, 600 hilos, tamaño king. Si el cliente "
            "duda del precio, recuérdale el ahorro vs comprar por separado."),
        "promotions": [
            {
                "id": _new_uid(),
                "sku_pattern": "COLCHA SABANA KING 600",
                "nombre_comercial": "Set Colcha + Sábana King 600 hilos",
                "descripcion": "Set completo colcha y sábana tamaño king de 600 hilos.",
                "precio_lista": 320000,
                "precio_promo": 229000,
                "bonos": ["Envío contra entrega", "Empaque de regalo"],
                "activa": True,
            },
        ],
        "activo": True,
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
]


# ---------- SOFIA DEFAULT PROMPT (LIT-LOG-RO) ----------
_SOFIA_SYSTEM = """Eres Sofía, la asesora del equipo Litper (Colombia). Llamas a un cliente cuyo pedido está represado en oficina y necesitas que lo reclame ANTES de que se devuelva. Tono colombiano cálido, cercano, seguro. Español natural. Duración objetivo < 60 segundos. Sé breve.

REGLAS DURAS
- NUNCA digas "impermeable" — SIEMPRE "antifluido".
- No prometas descuentos que no estén en {promo_name}.
- Confirma identidad ANTES de dar detalles del pedido.

FLUJO DE LA LLAMADA
1) Saludo + verifica identidad: "Hola, ¿hablo con {customer_first_name}?".
2) Presenta el tema: "Te llamo del equipo Litper. Tu pedido de {product_name} está represado en la oficina de {carrier_name} en {city} — {office_address}."
3) Urgencia: "Tienes {days_left} días para reclamarlo, {deadline_text}. Después el paquete se devuelve."
4) Pide fecha exacta de recogida: "¿Qué día exacto puedes ir a recogerlo?".
5) Guía + total: "El número de guía es {guia}. Total contra entrega: {total_to_pay}."
6) Si el cliente no puede en {days_left} días, ofrece ticket de EXTENSIÓN Dropi (hasta 10 días adicionales) y confirma el día exacto.

MANEJO DE OBJECIONES
- "Sí, lo recojo hoy/mañana" → confirma fecha + agradece + cierra: "Perfecto, te esperan con la guía {guia}."
- "En otro día" → pregunta cuál. Si cabe en {days_left} días → confirma. Si no → ofrece extensión Dropi (max 10 d) y agenda el día.
- "Estoy de viaje" → agenda extensión + confirma día exacto de regreso.
- "Ya no lo quiero" → pregunta la razón. Si es precio, menciona {promo_name} a {promo_price} si aplica. Si insiste, marca cancelación educada.
- "Número equivocado" → "Perdona la molestia, gracias por atender." Cierra.
- "Ya lo recogí" → "¡Perfecto! ¿Me confirmas la guía {guia}? Gracias."
- Silencio / voicemail → deja un mensaje corto de 12 segundos con guía y deadline.

CIERRE
- Confirma día + guía + agradece por nombre. "Gracias {customer_first_name}, cualquier cosa nos escribes por WhatsApp."
"""

_SOFIA_FIRST = ("Hola, ¿hablo con {customer_first_name}? Soy Sofía del equipo Litper, "
                "te llamo por tu pedido de {product_name} que está en la oficina de "
                "{carrier_name} en {city}.")

_ALLOWED_VARS = [
    "customer_first_name", "product_name", "carrier_name", "city",
    "office_address", "days_left", "deadline_text", "total_to_pay",
    "guia", "promo_name", "promo_price",
]

PROMPTS_SEED = [
    {
        "id":            _new_uid(),
        "name":          "Sofía CO — Reclamo en Oficina (por defecto)",
        "scope":         "global",
        "country":       "CO",
        "product_id":    None,
        "campaign_key":  None,
        "system_prompt": _SOFIA_SYSTEM,
        "first_message": _SOFIA_FIRST,
        "variables":     _ALLOWED_VARS,
        "voice_id":      None,
        "active":        True,
        "priority":      100,
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
    {
        "id":            _new_uid(),
        "name":          "Sofía EC — Reclamo en Oficina",
        "scope":         "global",
        "country":       "EC",
        "product_id":    None,
        "campaign_key":  None,
        "system_prompt": _SOFIA_SYSTEM.replace("colombiano", "ecuatoriano"),
        "first_message": _SOFIA_FIRST,
        "variables":     _ALLOWED_VARS,
        "voice_id":      None,
        "active":        True,
        "priority":      100,
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
]

# ---------- WHATSAPP RULES ----------
WHATSAPP_RULES_SEED = [
    {
        "id":                 _new_uid(),
        "rule_key":           "reclamo_oficina",
        "template_name":      "reclamo_en_oficina",
        "template_language":  "es",
        "days_min":           0,
        "days_max":           3,
        "media_url":          None,
        "active":             True,
        "notes":              "0–3 días: recordatorio + imagen de guía.",
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
    {
        "id":                 _new_uid(),
        "rule_key":           "no_oficina",
        "template_name":      "no_oficina_urgente",
        "template_language":  "es",
        "days_min":           4,
        "days_max":           99,
        "media_url":          None,
        "active":             True,
        "notes":              "+3 días: aviso urgente de devolución.",
        "created_at": _iso_now(), "updated_at": _iso_now(),
    },
]
