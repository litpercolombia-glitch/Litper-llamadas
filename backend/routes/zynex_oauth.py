"""Inicio de sesión (OAuth 2.1) del conector de Claude.

Claude, al conectar un conector personalizado, busca un servidor de inicio de
sesión y registra su cliente. El acceso real al conector ya lo da la URL con su
token secreto (/api/mcp/{token}); este módulo solo completa el saludo de OAuth
para que Claude pueda marcar el conector como «conectado».

- No guarda nada: los códigos y tokens van firmados (HMAC) y expiran.
- Solo devuelve a direcciones de Claude o del propio equipo (localhost).
- Si Claude indica el conector (resource), su token debe ser válido.
- Exige PKCE con S256, como pide la especificación de MCP.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

import webhook_tokens
from routes import zynex_call as zc

router = APIRouter(tags=["claude-oauth"], include_in_schema=False)

CODIGO_S = 300
ACCESO_S = 30 * 24 * 3600
REFRESCO_S = 365 * 24 * 3600
HOSTS_CLAUDE = ("claude.ai", "claude.com")
MCP_RE = re.compile(r"/api/mcp/([A-Za-z0-9_\-]{8,200})/?$")


def _clave() -> bytes:
    return (os.environ.get("JWT_SECRET") or "dev-only-not-secret").encode() + b":zx-oauth"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def firmar(datos: dict) -> str:
    cuerpo = _b64(json.dumps(datos, separators=(",", ":")).encode())
    return cuerpo + "." + _b64(hmac.new(_clave(), cuerpo.encode(), hashlib.sha256).digest())


def leer(valor: str, tipo: str) -> dict | None:
    try:
        cuerpo, firma = (valor or "").split(".", 1)
        if not hmac.compare_digest(firma, _b64(hmac.new(_clave(), cuerpo.encode(), hashlib.sha256).digest())):
            return None
        d = json.loads(_unb64(cuerpo))
    except Exception:  # noqa: BLE001
        return None
    if d.get("t") != tipo or int(d.get("exp", 0)) < time.time():
        return None
    return d


def redireccion_valida(uri: str) -> bool:
    try:
        u = urlparse(uri or "")
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    if u.scheme == "https" and (host in HOSTS_CLAUDE or host.endswith(tuple("." + h for h in HOSTS_CLAUDE))):
        return True
    return u.scheme == "http" and host in ("localhost", "127.0.0.1")


def _base(request: Request) -> str:
    return webhook_tokens.public_base(request) or "https://api.zynexapp.com"


def _meta_servidor(base: str) -> dict:
    return {"issuer": base, "authorization_endpoint": f"{base}/authorize", "token_endpoint": f"{base}/token",
            "registration_endpoint": f"{base}/register", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post"], "scopes_supported": ["zynex"]}


@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/{resto:path}")
@router.get("/.well-known/openid-configuration")
async def meta_servidor(request: Request, resto: str = ""):
    return _meta_servidor(_base(request))


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/{resto:path}")
async def meta_recurso(request: Request, resto: str = ""):
    base = _base(request)
    return {"resource": f"{base}/{resto}".rstrip("/") if resto else base, "authorization_servers": [base],
            "bearer_methods_supported": ["header"], "scopes_supported": ["zynex"]}


@router.post("/register")
async def registrar(request: Request):
    try:
        d = await request.json()
    except ValueError:
        raise HTTPException(400, "JSON inválido")
    uris = [u for u in (d.get("redirect_uris") or []) if isinstance(u, str)][:10]
    if not uris or not all(redireccion_valida(u) for u in uris):
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)
    return JSONResponse({"client_id": "zx_cli_" + secrets.token_urlsafe(12), "client_id_issued_at": int(time.time()),
                         "redirect_uris": uris, "client_name": str(d.get("client_name") or "Claude")[:80],
                         "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
                         "token_endpoint_auth_method": "none"}, status_code=201)


async def _recurso_valido(resource: str) -> bool:
    if not resource:
        return True
    m = MCP_RE.search(urlparse(resource).path or "")
    return bool(m and await zc.org_por_token_mcp(m.group(1)))


@router.get("/authorize")
async def autorizar(request: Request):
    q = request.query_params
    ru, cc = q.get("redirect_uri", ""), q.get("code_challenge", "")
    if not redireccion_valida(ru):
        raise HTTPException(400, "Dirección de regreso no permitida.")
    def volver(**extra):
        sep = "&" if "?" in ru else "?"
        return RedirectResponse(ru + sep + urlencode({k: v for k, v in {**extra, "state": q.get("state")}.items() if v}), 302)
    if q.get("response_type") != "code" or q.get("code_challenge_method", "S256") != "S256" or not cc:
        return volver(error="invalid_request")
    if not await _recurso_valido(q.get("resource", "")):
        return volver(error="access_denied", error_description="Conector no válido: genera uno nuevo en Zynex.")
    code = firmar({"t": "code", "cc": cc, "ru": ru, "cid": q.get("client_id", ""), "exp": int(time.time()) + CODIGO_S})
    return volver(code=code)


def _tokens() -> dict:
    ahora = int(time.time())
    return {"access_token": firmar({"t": "acc", "n": secrets.token_hex(8), "exp": ahora + ACCESO_S}),
            "token_type": "Bearer", "expires_in": ACCESO_S, "scope": "zynex",
            "refresh_token": firmar({"t": "ref", "n": secrets.token_hex(8), "exp": ahora + REFRESCO_S})}


@router.post("/token")
async def token(request: Request):
    tipo = request.headers.get("content-type", "")
    d = dict(await request.form()) if "form" in tipo else (await request.json() if "json" in tipo else {})
    error = lambda e: JSONResponse({"error": e}, status_code=400)  # noqa: E731
    if d.get("grant_type") == "authorization_code":
        c = leer(str(d.get("code", "")), "code")
        if not c or c.get("ru") != d.get("redirect_uri"):
            return error("invalid_grant")
        verif = _b64(hashlib.sha256(str(d.get("code_verifier", "")).encode()).digest())
        if not d.get("code_verifier") or not hmac.compare_digest(verif, c.get("cc", "")):
            return error("invalid_grant")
        return _tokens()
    if d.get("grant_type") == "refresh_token":
        if not leer(str(d.get("refresh_token", "")), "ref"):
            return error("invalid_grant")
        return _tokens()
    return error("unsupported_grant_type")
