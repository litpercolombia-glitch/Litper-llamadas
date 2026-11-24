"""Límite de frecuencia sencillo EN MEMORIA (ventana deslizante).

OJO — alcance: los contadores viven en la memoria de ESTE proceso. Con un solo
proceso/réplica basta. Con varias réplicas (o varios workers de uvicorn) cada
una lleva su cuenta y el límite real se multiplica: en ese caso hay que mover
el contador a Mongo (colección con índice TTL) o a Redis. Se reinicia al
reiniciar el servidor.
"""
from __future__ import annotations
import os
import time
from collections import defaultdict, deque

_hits: dict[str, deque] = defaultdict(deque)
_MAX_KEYS = 50_000          # tope de memoria: al pasarlo se purgan las claves vencidas


def client_ip(request) -> str:
    """IP del cliente. Detrás de un proxy se usa X-Forwarded-For contando
    TRUSTED_PROXY_HOPS saltos desde la derecha (por defecto 1: la IP que vio
    nuestro proxy, que el cliente no puede falsear). Sin esa cabecera, la IP
    de la conexión."""
    xff = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    if xff:
        try:
            hops = max(1, int(os.environ.get("TRUSTED_PROXY_HOPS", "1")))
        except ValueError:
            hops = 1
        return xff[-hops] if len(xff) >= hops else xff[0]
    return getattr(getattr(request, "client", None), "host", None) or "desconocida"


def _prune(q: deque, now: float, window: float) -> None:
    while q and q[0] <= now - window:
        q.popleft()


def count(key: str, window: float, now: float | None = None) -> int:
    """Eventos registrados para `key` dentro de la ventana (segundos)."""
    now = time.time() if now is None else now
    q = _hits.get(key)
    if not q:
        return 0
    _prune(q, now, window)
    if not q:
        _hits.pop(key, None)
        return 0
    return len(q)


def hit(key: str, window: float, now: float | None = None) -> int:
    """Registra un evento y devuelve cuántos hay en la ventana."""
    now = time.time() if now is None else now
    if len(_hits) > _MAX_KEYS:
        for k in [k for k, q in _hits.items() if not q or q[-1] <= now - window]:
            _hits.pop(k, None)
    q = _hits[key]
    _prune(q, now, window)
    q.append(now)
    return len(q)


def clear(key: str) -> None:
    _hits.pop(key, None)


def reset_all() -> None:
    """Solo para pruebas."""
    _hits.clear()
