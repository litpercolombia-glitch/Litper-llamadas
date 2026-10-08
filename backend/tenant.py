"""Resolución única y segura del cliente (tenant) de una petición. v3

Reglas (en este orden):
  1. JWT válido (cookie de sesión; si la cookie no es válida, Authorization:
     Bearer): el cliente es SIEMPRE su claim "org". X-Org-Id se IGNORA.
     Un JWT válido SIN claim "org" -> 401 (nunca cae al cajón "default").
  2. Sin JWT válido pero con la X-API-Key de plataforma (servidor-a-servidor,
     n8n): el cliente se indica con X-Org-Id.
  3. Cualquier otro caso: "default" (las rutas ya exigen auth con
     deps.require_api_key; "default" NO debe tener llaves tras la migración).

Usar SIEMPRE esta función. No leer X-Org-Id directo en las rutas.
"""
import hmac
import os

from fastapi import HTTPException, Request

DEFAULT_ORG = "default"


def _jwt_claims(request: Request) -> dict | None:
    from routes.auth import _decode, COOKIE_NAME
    cookie = request.cookies.get(COOKIE_NAME)
    claims = _decode(cookie) if cookie else None
    if claims:
        return claims
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return _decode(auth[7:])
    return None


def org_from_request(request: Request) -> str:
    claims = _jwt_claims(request)
    if claims:
        org = claims.get("org")
        if not org:
            raise HTTPException(401, "Sesión sin organización. Vuelve a iniciar sesión.")
        return str(org)
    expected = os.environ.get("PUBLIC_API_KEY", "")
    given = request.headers.get("X-API-Key", "") or ""
    if expected and given and hmac.compare_digest(given, expected):
        return (request.headers.get("X-Org-Id") or "").strip() or DEFAULT_ORG
    return DEFAULT_ORG
