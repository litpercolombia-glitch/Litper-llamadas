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


_JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-not-secret")
_JWT_ALG = "HS256"
_COOKIE_NAME = "litper_session"


def _valid_jwt(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALG])
    except jwt.PyJWTError:
        return None


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
