"""Guardia de las pruebas "de servidor vivo" (test_hub*, test_iteration_*, …).

Esas pruebas hablan con un backend desplegado; NO llevan secretos escritos.
Necesitan en el entorno:
    REACT_APP_BACKEND_URL  URL base del backend
    PUBLIC_API_KEY         llave de plataforma
    QA_EMAIL / QA_PASSWORD credenciales de la cuenta de QA
Si falta alguna, el módulo entero se salta (no falla la recolección).
"""
import os

import pytest

REQUIRED = ("REACT_APP_BACKEND_URL", "PUBLIC_API_KEY", "QA_PASSWORD")


def require_live() -> None:
    missing = [k for k in REQUIRED if not os.environ.get(k, "").strip()]
    if missing:
        pytest.skip("prueba de servidor vivo: faltan " + ", ".join(missing),
                    allow_module_level=True)
