"""Auth: email + password (bcrypt) + JWT (httponly cookie) + Google OAuth
(Emergent-managed). Both flows land in the same `users` collection and issue
the same `litper_session` cookie so the app has ONE session model."""
from __future__ import annotations
import os, re, uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, Request, Header
from pydantic import BaseModel, EmailStr, Field

from db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-not-secret")
JWT_ALG = "HS256"
JWT_TTL_HOURS = 24 * 14  # 14 days
COOKIE_NAME = "litper_session"


def _iso() -> str: return datetime.now(timezone.utc).isoformat()


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _verify(pw: str, hashed: str) -> bool:
    try: return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception: return False


def _issue_token(user_id: str, org_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": user_id, "org": org_id, "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_TTL_HOURS)).timestamp()),
    }, JWT_SECRET, algorithm=JWT_ALG)


def _decode(token: str) -> dict | None:
    try: return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError: return None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    nombre: str = Field(..., min_length=1)
    org_name: str = Field("Mi organización", min_length=1)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "org"


async def _set_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=COOKIE_NAME, value=token,
        httponly=True, samesite="lax", secure=True,
        max_age=JWT_TTL_HOURS * 3600, path="/",
    )


@router.post("/register", summary="Sign up + create org.")
async def register(payload: RegisterIn, response: Response):
    db = get_db()
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Email ya registrado. Inicia sesión.")
    org_id = _slug(payload.org_name) + "-" + uuid.uuid4().hex[:6]
    user_id = uuid.uuid4().hex
    now = _iso()
    await db.orgs.insert_one({"id": org_id, "name": payload.org_name,
                              "owner_user_id": user_id, "created_at": now})
    await db.users.insert_one({
        "id": user_id, "email": email, "nombre": payload.nombre,
        "password_hash": _hash(payload.password),
        "org_id": org_id, "role": "owner",
        "created_at": now, "provider": "email",
    })
    tok = _issue_token(user_id, org_id, email)
    await _set_cookie(response, tok)
    return {"ok": True, "user": {"id": user_id, "email": email, "nombre": payload.nombre,
                                  "org_id": org_id, "role": "owner"}}


@router.post("/login", summary="Log in with email + password.")
async def login(payload: LoginIn, response: Response):
    db = get_db()
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not _verify(payload.password, user.get("password_hash", "")):
        raise HTTPException(401, "Credenciales inválidas.")
    tok = _issue_token(user["id"], user["org_id"], email)
    await _set_cookie(response, tok)
    return {"ok": True, "user": {"id": user["id"], "email": email,
                                  "nombre": user.get("nombre"),
                                  "org_id": user["org_id"], "role": user.get("role")}}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


async def current_user(request: Request) -> dict:
    # Accept JWT via cookie OR Authorization: Bearer
    tok = request.cookies.get(COOKIE_NAME)
    if not tok:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            tok = auth[7:]
    if not tok:
        raise HTTPException(401, "No autenticado.")
    payload = _decode(tok)
    if not payload:
        raise HTTPException(401, "Sesión inválida o expirada.")
    return payload


@router.get("/me", summary="Return the current session user.")
async def me(request: Request):
    payload = await current_user(request)
    db = get_db()
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "Usuario no encontrado.")
    return {"user": user, "org_id": payload.get("org")}


# ---------- Emergent-managed Google OAuth ----------
# Frontend redirects the user to
#   https://auth.emergentagent.com/?redirect=<origin>/app
# The provider bounces back to `<origin>/app#session_id=xxx`. The React
# AuthCallback POSTs that id here — we exchange it server-side and set the
# same `litper_session` cookie used by the email/password flow.
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


@router.post("/google/session", summary="Exchange an Emergent OAuth session_id for a JWT cookie.")
async def google_session(response: Response,
                         x_session_id: str = Header(None, alias="X-Session-ID")):
    if not x_session_id:
        raise HTTPException(400, "Falta X-Session-ID.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": x_session_id})
        if r.status_code != 200:
            raise HTTPException(401, f"Sesión Google inválida ({r.status_code}).")
        data = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"No se pudo contactar Emergent Auth: {e}")

    email = (data.get("email") or "").lower().strip()
    name  = (data.get("name") or "").strip() or (email.split("@")[0] if email else "Usuario")
    picture = data.get("picture")
    if not email:
        raise HTTPException(400, "Perfil Google sin email.")

    db = get_db()
    now = _iso()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        # Upgrade an existing email-only user with Google metadata (idempotent)
        await db.users.update_one({"id": user["id"]}, {"$set": {
            "nombre":     user.get("nombre") or name,
            "picture":    picture or user.get("picture"),
            "provider":   "google" if user.get("provider") == "email" else user.get("provider", "google"),
            "last_login": now,
        }})
        user_id, org_id = user["id"], user["org_id"]
    else:
        # First-time Google sign-up → create the user AND their org.
        user_id = uuid.uuid4().hex
        org_id  = _slug(name or "org") + "-" + uuid.uuid4().hex[:6]
        await db.orgs.insert_one({"id": org_id, "name": name or "Mi organización",
                                  "owner_user_id": user_id, "created_at": now})
        await db.users.insert_one({
            "id": user_id, "email": email, "nombre": name,
            "picture": picture, "org_id": org_id, "role": "owner",
            "provider": "google", "created_at": now, "last_login": now,
        })

    tok = _issue_token(user_id, org_id, email)
    await _set_cookie(response, tok)
    return {"ok": True, "user": {"id": user_id, "email": email, "nombre": name,
                                  "picture": picture, "org_id": org_id, "role": "owner"}}


# ---------- Profile & account settings (Vercel/Linear/Stripe pattern) ----------
_AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


class ProfileIn(BaseModel):
    nombre: Optional[str] = None
    email:  Optional[EmailStr] = None
    org_name: Optional[str] = None


class PasswordChangeIn(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password:     str = Field(..., min_length=6)


class AvatarIn(BaseModel):
    data_url: str  # e.g. "data:image/webp;base64,...."


@router.put("/profile", summary="Update display name / email / org name.")
async def update_profile(payload: ProfileIn, request: Request):
    tok = await current_user(request)
    db = get_db()
    user = await db.users.find_one({"id": tok["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Usuario no encontrado.")

    updates = {}
    if payload.nombre is not None and payload.nombre.strip():
        updates["nombre"] = payload.nombre.strip()
    if payload.email is not None:
        new_email = payload.email.lower().strip()
        if new_email != user["email"]:
            # Google-linked accounts cannot change their primary email here.
            if user.get("provider") == "google":
                raise HTTPException(400, "El email de una cuenta Google se gestiona en Google.")
            clash = await db.users.find_one({"email": new_email, "id": {"$ne": user["id"]}}, {"_id": 0})
            if clash:
                raise HTTPException(409, "Ese email ya está en uso.")
            updates["email"] = new_email
    if updates:
        updates["updated_at"] = _iso()
        await db.users.update_one({"id": user["id"]}, {"$set": updates})

    if payload.org_name is not None and payload.org_name.strip():
        await db.orgs.update_one(
            {"id": user["org_id"]},
            {"$set": {"name": payload.org_name.strip(), "updated_at": _iso()}},
            upsert=True,
        )

    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    org   = await db.orgs.find_one({"id": user["org_id"]}, {"_id": 0}) or {}
    return {"ok": True, "user": fresh, "org": org}


@router.put("/password", summary="Change password (email accounts only).")
async def change_password(payload: PasswordChangeIn, request: Request):
    tok = await current_user(request)
    db = get_db()
    user = await db.users.find_one({"id": tok["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Usuario no encontrado.")
    if user.get("provider") == "google":
        raise HTTPException(400, "Tu contraseña la gestiona Google.")
    if not user.get("password_hash") or not _verify(payload.current_password, user["password_hash"]):
        raise HTTPException(401, "Contraseña actual incorrecta.")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": _hash(payload.new_password), "password_updated_at": _iso()}},
    )
    return {"ok": True}


@router.post("/avatar", summary="Upload a profile picture (base64 data-URL, ≤2MB, jpg/png/webp).")
async def upload_avatar(payload: AvatarIn, request: Request):
    tok = await current_user(request)
    db = get_db()
    m = re.match(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", payload.data_url or "")
    if not m:
        raise HTTPException(400, "Formato inválido. Usa PNG, JPG o WebP.")
    mime, b64 = m.group(1), m.group(2)
    # Estimate decoded size = len(b64) * 3/4  (fast, no full decode)
    est = int(len(b64) * 3 / 4)
    if est > _AVATAR_MAX_BYTES:
        raise HTTPException(413, "Imagen supera 2 MB. Recórtala antes de subirla.")
    await db.users.update_one(
        {"id": tok["sub"]},
        {"$set": {"picture": payload.data_url, "picture_updated_at": _iso()}},
    )
    return {"ok": True, "size_estimate_bytes": est, "mime": mime}


@router.delete("/avatar")
async def delete_avatar(request: Request):
    tok = await current_user(request)
    await get_db().users.update_one({"id": tok["sub"]}, {"$unset": {"picture": ""}})
    return {"ok": True}


@router.get("/org", summary="Return the current user's organization info.")
async def get_org(request: Request):
    tok = await current_user(request)
    org = await get_db().orgs.find_one({"id": tok["org"]}, {"_id": 0})
    if not org:
        # Legacy accounts: synthesize a minimal org doc
        org = {"id": tok["org"], "name": tok["org"], "owner_user_id": tok["sub"]}
    return {"org": org}
