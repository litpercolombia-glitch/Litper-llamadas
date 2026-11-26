"""Lector de lo que devuelve el conector de Dropi → lista de pedidos.

El conector puede responder de tres formas y aquí se entienden las tres:

  1. JSON (una lista, o un objeto que trae la lista adentro).
  2. Tabla compacta:   items[2]{order_id,status,...}:   seguida de filas con comas.
  3. Lista con guiones:
         items[2]:
           - order_id: "981"
             status: GUIA_GENERADA
           - order_id: "982"
             ...

Todo lo que sale de aquí es dato de terceros. `forma()` describe una respuesta
que no se pudo leer SIN copiar datos de clientes (solo tamaño y el encabezado).
"""
from __future__ import annotations

import csv
import io
import json
import re

TABLA = re.compile(r"^\s*\w+\[(\d+)\]\{([^}]*)\}:\s*$")
LISTA = re.compile(r"^\s*\w+\[(\d+)\]:\s*$")
CAMPO = re.compile(r"^(\s*)(-\s+)?([A-Za-z_][\w.]*):\s?(.*)$")


def _valor(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1]
    return "" if v in ("null", "~") else v


def lista_de_pedidos(dato, nivel: int = 0) -> list[dict]:
    """Primera lista de objetos que aparezca en un JSON, esté al nivel que esté."""
    if isinstance(dato, list):
        return [o for o in dato if isinstance(o, dict)]
    if isinstance(dato, dict) and nivel < 4:
        for v in dato.values():
            if isinstance(v, (list, dict)):
                r = lista_de_pedidos(v, nivel + 1)
                if r:
                    return r
        if nivel == 0 and any(k in dato for k in ("order_id", "id", "pedido")):
            return [dato]
    return []


def _de_tabla(lineas: list[str], i: int, m) -> list[dict]:
    campos = [c.strip() for c in m.group(2).split(",")]
    filas = [x for x in lineas[i + 1:i + 1 + int(m.group(1))] if x.strip()]
    out = []
    for fila in csv.reader(io.StringIO("\n".join(x.strip() for x in filas)), skipinitialspace=True):
        if len(fila) == len(campos):
            out.append(dict(zip(campos, fila)))
    return out


def _de_lista(lineas: list[str], i: int) -> list[dict]:
    out: list[dict] = []
    actual: dict | None = None
    sangria = None            # sangría de los campos del pedido; lo más profundo se ignora
    for linea in lineas[i + 1:]:
        if not linea.strip():
            continue
        if not linea[0].isspace():
            break                              # terminó la lista (count:, applied_range:, …)
        m = CAMPO.match(linea)
        if not m:
            continue
        if m.group(2):                         # «- campo: valor» abre un pedido nuevo
            if sangria is None:
                sangria = len(m.group(1)) + len(m.group(2))
            if len(m.group(1)) + len(m.group(2)) != sangria:
                continue                       # guion de una lista interna (productos, etc.)
            actual = {}
            out.append(actual)
        elif actual is None or len(m.group(1)) != sangria:
            continue
        actual[m.group(3)] = _valor(m.group(4))
    return [o for o in out if o]


def pedidos_de_texto(texto: str) -> list[dict]:
    texto = (texto or "").strip()
    if not texto:
        return []
    if texto[0] in "[{":
        try:
            return lista_de_pedidos(json.loads(texto))
        except ValueError:
            pass
    lineas = texto.splitlines()
    for i, linea in enumerate(lineas):
        m = TABLA.match(linea)
        if m:
            return _de_tabla(lineas, i, m)
        if LISTA.match(linea):
            return _de_lista(lineas, i)
    return []


def forma(texto: str, truncado: bool) -> str:
    """Cómo viene una respuesta que no se pudo leer: tamaño y solo la primera línea, sin datos."""
    primera = re.sub(r"\d", "9", ((texto or "").strip().splitlines() or [""])[0][:40])
    return f"sin_leer largo={len(texto or '')} truncado={truncado} encabezado={primera}"
