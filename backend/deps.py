"""Shared FastAPI dependencies.

Every business route uses `require_api_key`. Historically that meant only the
static `PUBLIC_API_KEY` header. As of the Zynex OS auth rollout we ALSO
accept a valid `litper_session` JWT cookie (or `Authorization: Bearer <jwt>`)
so the React frontend no longer has to ship the operator key on every call.
External integrations that still send `X-API-Key` keep working — nothing
breaks — because we accept either.
"""
import os
from fastapi import Header, HTTPException, Request, status

# jwt module is already a dep for routes/auth.py — safe to import here.
import jwt


DEFAULT_JWT_SECRET = "dev-only-not-secret"
DEFAULT_ORG = "default"


def is_production() -> bool:
    """Producción = ENV/ENVIRONMENT == "production" o variable RENDER definida."""
    env = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    return env == "production" or bool(os.environ.get("RENDER"))


def is_development() -> bool:
    """Desarrollo SOLO si se declara explícitamente (ENV=development/dev/local)
    y no hay señales de producción."""
    env = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    return env in ("development", "dev", "local") and not os.environ.get("RENDER")


def _under_pytest() -> bool:
    import sys
    return "pytest" in sys.modules


def check_jwt_secret(under_pytest: bool | None = None) -> str:
    """Devuelve el secreto JWT. JWT_SECRET es OBLIGATORIO siempre: sin él (o con
    el valor por defecto) el servidor NO arranca, porque cualquiera podría
    firmar sesiones. Únicas excepciones: ENV=development explícito, o pytest."""
    secret = os.environ.get("JWT_SECRET", "").strip()
    if secret and secret != DEFAULT_JWT_SECRET:
        return secret
    if under_pytest is None:
        under_pytest = _under_pytest()
    if (is_development() or under_pytest) and not is_production():
        return DEFAULT_JWT_SECRET
    raise RuntimeError(
        "Arranque bloqueado: falta JWT_SECRET (o es el valor por defecto). "
        "Define JWT_SECRET con un valor largo y aleatorio. Solo para desarrollo "
        "local puedes arrancar sin él poniendo ENV=development.")


_JWT_SECRET = check_jwt_secret()
_JWT_ALG = "HS256"
_COOKIE_NAME = "litper_session"


def _valid_jwt(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALG])
    except jwt.PyJWTError:
        return None


def get_org(request: Request) -> str:
    """Cliente (tenant) de la petición. ÚNICA fuente: tenant.org_from_request
    (JWT > X-API-Key de plataforma + X-Org-Id > "default"). Toda ruta de
    negocio filtra sus lecturas por este org_id y lo guarda en sus escrituras."""
    from tenant import org_from_request
    return org_from_request(request)


def get_ctx(request: Request) -> dict:
    """Contexto para el agente/herramientas: {"org_id", "user_id"}."""
    from tenant import _jwt_claims
    claims = _jwt_claims(request) or {}
    return {"org_id": get_org(request), "user_id": claims.get("sub")}


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Accept EITHER a valid JWT session cookie/bearer OR the legacy X-API-Key."""
    # 1) JWT cookie (preferred, set by /auth/login and /auth/google/session)
    cookie_tok = request.cookies.get(_COOKIE_NAME)
    if _valid_jwt(cookie_tok):
        return True

    # 2) Authorization: Bearer <jwt>
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        if _valid_jwt(auth[7:]):
            return True

    # 3) Legacy static key (external agents / cURL)
    expected = os.environ.get("PUBLIC_API_KEY")
    if not expected:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="PUBLIC_API_KEY not configured on server")
    if x_api_key == expected:
        return True

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Sesión inválida o X-API-Key ausente/incorrecta.")
