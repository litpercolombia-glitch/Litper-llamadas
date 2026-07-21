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
