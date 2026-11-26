"""Asistente: carga las herramientas nativas y las de Logística y Clientes,
y suma al prompt las reglas de trato (entender lenguaje diario, no quedarse en «no hay»)."""
from agent import tools_logistica  # noqa: F401,E402
from agent import loop as _loop  # noqa: E402

_REGLAS_TRATO = """- Entiende el lenguaje de todos los días y los errores de tecleo: «sacaron»,
  «hicieron», «salieron», «entraron» o «vendieron» pedidos significa pedidos
  creados. Si la pregunta admite una lectura razonable, respóndela con datos y
  di en una frase qué asumiste; pregunta solo si de verdad no puedes avanzar.
- Si una consulta sale vacía, no te quedes en «no hay»: revisa el resumen o el
  grupo más cercano y cuenta lo que sí hay (por ejemplo, intentos de entrega
  cuando piden novedades). Di la hora del último corte de datos cuando el
  resultado la traiga, y avisa si los datos están atrasados.
"""
_ANCLA = "- Muestra números, fechas y montos literalmente"
if _REGLAS_TRATO not in _loop.SYSTEM_PROMPT_TEMPLATE and _ANCLA in _loop.SYSTEM_PROMPT_TEMPLATE:
    _loop.SYSTEM_PROMPT_TEMPLATE = _loop.SYSTEM_PROMPT_TEMPLATE.replace(_ANCLA, _REGLAS_TRATO + _ANCLA, 1)

# IA incluida con tope diario por cuenta (solo cuando usa la llave de la plataforma).
from agent import tope_ia as _tope  # noqa: E402
if not hasattr(_loop.llm_call, "__wrapped__"):
    _loop.llm_call = _tope.envolver(_loop.llm_call)
