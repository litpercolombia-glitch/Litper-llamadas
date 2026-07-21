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
