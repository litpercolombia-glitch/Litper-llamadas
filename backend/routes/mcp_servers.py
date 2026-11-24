"""Routes: /mcp-servers — conectores MCP por cliente (org).

Colección `mcp_servers`:
  {id, org_id, nombre, slug, url, auth_type, header_name, secret_ct (Fernet),
   has_secret, tools: [{name, description, input_schema, hash, enabled,
   requires_confirm}], last_test_at, last_test_ok, last_error, created_at,
   updated_at}

Reglas de seguridad:
  * todo se filtra por el org de la sesión (deps.get_org); máx. 10 por org;
  * el secreto se guarda cifrado (org_credentials._fernet) y NUNCA se devuelve
    (solo `has_secret`);
  * una herramienta NUEVA o cuya definición cambió (hash sha256 distinto) queda
    `enabled:false, requires_confirm:true` hasta que el cliente la active;
  * cambiar la dirección o la autenticación desactiva todas las herramientas
    (hay que volver a probar la conexión).
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import mcp_client
from db import get_db
from deps import get_org, require_api_key

router = APIRouter(prefix="/mcp-servers", tags=["mcp"],
                   dependencies=[Depends(require_api_key)])

MAX_SERVERS_PER_ORG = 10
AUTH_TYPES = {"none", "bearer", "header"}
TOOL_PREFIX = "mcp__"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ nombres
def slugify(nombre: str) -> str:
    """Nombre del servidor apto para `mcp__<servidor>__<tool>` (sin `__`)."""
    s = re.sub(r"[^a-z0-9]+", "_", (nombre or "").lower()).strip("_")
    return (s or "servidor")[:24].strip("_") or "servidor"


def safe_tool_name(name: str) -> str:
    """Nombre de herramienta saneado (sin `__`, solo [A-Za-z0-9_-])."""
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", name or "")
    s = re.sub(r"_{2,}", "_", s).strip("_")
    return (s or "tool")[:64]


def full_tool_name(slug: str, tool: str) -> str:
    return f"{TOOL_PREFIX}{slug}__{safe_tool_name(tool)}"


def tool_hash(t: dict) -> str:
    """sha256 de la definición (nombre + descripción + esquema de entrada)."""
    canon = json.dumps({"name": t.get("name"), "description": t.get("description") or "",
                        "input_schema": t.get("input_schema") or {}},
                       sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


# ------------------------------------------------------------------ secreto
def _encrypt(secret: str) -> str:
    from org_credentials import _fernet
    return _fernet().encrypt(secret.encode()).decode()


def _decrypt(ct: str) -> str:
    from org_credentials import _fernet
    try:
        return _fernet().decrypt(ct.encode()).decode() if ct else ""
    except Exception:  # noqa: BLE001 — cifrado ilegible = sin secreto
        return ""


def connection_of(doc: dict) -> dict:
    """Datos de conexión para mcp_client (con el secreto en claro). SOLO backend."""
    return {"url": doc.get("url"), "auth_type": doc.get("auth_type") or "none",
            "header_name": doc.get("header_name") or "",
            "secret": _decrypt(doc.get("secret_ct") or "")}


def public(doc: dict) -> dict:
    """Lo que ve el cliente: nunca el secreto ni su cifrado."""
    return {
        "id": doc["id"], "nombre": doc.get("nombre"), "name": doc.get("nombre"),
        "slug": doc.get("slug"), "url": doc.get("url"),
        "auth_type": doc.get("auth_type") or "none",
        "header_name": doc.get("header_name") or "",
        "has_secret": bool(doc.get("secret_ct")),
        "tools": [{"name": t.get("name"), "description": t.get("description") or "",
                   "input_schema": t.get("input_schema") or {}, "hash": t.get("hash"),
                   "enabled": bool(t.get("enabled")),
                   "requires_confirm": t.get("requires_confirm") is not False,
                   "full_name": full_tool_name(doc.get("slug") or "", t.get("name") or "")}
                  for t in doc.get("tools") or []],
        "last_test_at": doc.get("last_test_at"), "last_test_ok": doc.get("last_test_ok"),
        "last_error": doc.get("last_error") or "",
        "created_at": doc.get("created_at"), "updated_at": doc.get("updated_at"),
    }


# ------------------------------------------------------------------ modelos
class McpServerIn(BaseModel):
    nombre:      str = Field(..., min_length=1, max_length=60)
    url:         str = Field(..., min_length=8, max_length=500)
    auth_type:   str = "none"
    secret:      Optional[str] = Field(None, max_length=4000)
    header_name: Optional[str] = Field(None, max_length=64)


class McpServerPatch(BaseModel):
    nombre:      Optional[str] = Field(None, min_length=1, max_length=60)
    url:         Optional[str] = Field(None, min_length=8, max_length=500)
    auth_type:   Optional[str] = None
    secret:      Optional[str] = Field(None, max_length=4000)
    header_name: Optional[str] = Field(None, max_length=64)


class ToolToggle(BaseModel):
    name: str
    enabled: bool = False
    requires_confirm: bool = True


class ToolsIn(BaseModel):
    tools: list[ToolToggle] = Field(default_factory=list)


def _check_conn(url: str, auth_type: str, header_name: str, has_secret: bool) -> None:
    if auth_type not in AUTH_TYPES:
        raise HTTPException(400, "Tipo de autenticación no válido.")
    try:
        mcp_client.validate_url(url)
        if auth_type == "header":
            mcp_client.validate_header_name(header_name)
    except mcp_client.McpError as e:
        raise HTTPException(400, str(e))
    if auth_type != "none" and not has_secret:
        raise HTTPException(400, "Falta el secreto para ese tipo de autenticación.")


async def _get(server_id: str, org: str) -> dict:
    doc = await get_db().mcp_servers.find_one({"id": server_id, "org_id": org}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Conector no encontrado.")
    return doc


async def _name_taken(org: str, nombre: str, slug: str, skip_id: str | None = None) -> bool:
    docs = await get_db().mcp_servers.find({"org_id": org}, {"_id": 0}).to_list(50)
    return any(d["id"] != skip_id and (d.get("nombre", "").strip().lower() == nombre.lower()
                                       or d.get("slug") == slug) for d in docs)


# ------------------------------------------------------------------ rutas
@router.get("", summary="Conectores MCP del cliente actual (sin secretos).")
async def list_servers(org: str = Depends(get_org)):
    docs = await get_db().mcp_servers.find({"org_id": org}, {"_id": 0}) \
        .sort("created_at", 1).to_list(50)
    return {"servers": [public(d) for d in docs], "max": MAX_SERVERS_PER_ORG}


@router.post("", status_code=201, summary="Añade un conector MCP (secreto cifrado).")
async def create_server(payload: McpServerIn, org: str = Depends(get_org)):
    db = get_db()
    nombre = payload.nombre.strip()
    url = payload.url.strip()
    auth_type = (payload.auth_type or "none").lower()
    secret = (payload.secret or "").strip() if auth_type != "none" else ""
    header_name = (payload.header_name or "").strip() if auth_type == "header" else ""
    if not nombre:
        raise HTTPException(400, "Ponle un nombre al conector.")
    _check_conn(url, auth_type, header_name, bool(secret))
    if await db.mcp_servers.count_documents({"org_id": org}) >= MAX_SERVERS_PER_ORG:
        raise HTTPException(400, f"Máximo {MAX_SERVERS_PER_ORG} conectores por cuenta. "
                                 "Elimina uno para añadir otro.")
    slug = slugify(nombre)
    if await _name_taken(org, nombre, slug):
        raise HTTPException(409, "Ya tienes un conector con ese nombre.")
    doc = {"id": uuid.uuid4().hex[:12], "org_id": org, "nombre": nombre, "slug": slug,
           "url": url, "auth_type": auth_type, "header_name": header_name,
           "secret_ct": _encrypt(secret) if secret else "", "has_secret": bool(secret),
           "tools": [], "last_test_at": None, "last_test_ok": None, "last_error": "",
           "created_at": _now(), "updated_at": _now()}
    try:
        await db.mcp_servers.insert_one(dict(doc))
    except Exception as e:  # noqa: BLE001 — índice único (org_id, nombre)
        if "duplicate" in str(e).lower() or "E11000" in str(e):
            raise HTTPException(409, "Ya tienes un conector con ese nombre.")
        raise
    return {"ok": True, "server": public(doc), **public(doc)}


@router.patch("/{server_id}", summary="Edita un conector. Cambiar dirección o "
              "autenticación desactiva sus herramientas hasta volver a probar.")
async def patch_server(server_id: str, payload: McpServerPatch, org: str = Depends(get_org)):
    doc = await _get(server_id, org)
    ch = payload.model_dump(exclude_unset=True)
    upd: dict[str, Any] = {}
    if ch.get("nombre") is not None:
        nombre = ch["nombre"].strip()
        slug = slugify(nombre)
        if not nombre:
            raise HTTPException(400, "Ponle un nombre al conector.")
        if await _name_taken(org, nombre, slug, skip_id=server_id):
            raise HTTPException(409, "Ya tienes un conector con ese nombre.")
        upd.update(nombre=nombre, slug=slug)
    url = (ch.get("url") or doc["url"]).strip()
    auth_type = (ch.get("auth_type") or doc.get("auth_type") or "none").lower()
    header_name = (ch["header_name"] if ch.get("header_name") is not None
                   else doc.get("header_name") or "").strip() if auth_type == "header" else ""
    new_secret = (ch.get("secret") or "").strip()
    secret_ct = doc.get("secret_ct") or ""
    if auth_type == "none":
        secret_ct = ""
    elif new_secret:
        secret_ct = _encrypt(new_secret)
    _check_conn(url, auth_type, header_name, bool(secret_ct))
    conn_changed = (url != doc["url"] or auth_type != (doc.get("auth_type") or "none")
                    or header_name != (doc.get("header_name") or "") or bool(new_secret))
    upd.update(url=url, auth_type=auth_type, header_name=header_name,
               secret_ct=secret_ct, has_secret=bool(secret_ct), updated_at=_now())
    if conn_changed:
        # Otro destino u otras credenciales = otro servidor: nada queda activo.
        upd["tools"] = [{**t, "enabled": False, "requires_confirm": True}
                        for t in doc.get("tools") or []]
        upd.update(last_test_ok=None, last_error="")
    await get_db().mcp_servers.update_one({"id": server_id, "org_id": org}, {"$set": upd})
    fresh = await _get(server_id, org)
    return {"ok": True, "server": public(fresh), **public(fresh)}


@router.delete("/{server_id}", summary="Elimina un conector MCP.")
async def delete_server(server_id: str, org: str = Depends(get_org)):
    r = await get_db().mcp_servers.delete_one({"id": server_id, "org_id": org})
    if r.deleted_count == 0:
        raise HTTPException(404, "Conector no encontrado.")
    return {"ok": True}


def merge_tools(old: list[dict], fresh: list[dict]) -> list[dict]:
    """Une las herramientas recién listadas con el estado guardado. Nueva o con
    definición distinta → desactivada y con confirmación obligatoria."""
    prev = {t.get("name"): t for t in old or []}
    out, seen = [], set()
    for t in fresh:
        name = t["name"]
        if name in seen or any(safe_tool_name(name) == safe_tool_name(s) for s in seen):
            continue                                     # nombres que chocan al sanear
        seen.add(name)
        h = tool_hash(t)
        p = prev.get(name)
        same = bool(p) and p.get("hash") == h
        out.append({"name": name, "description": t.get("description") or "",
                    "input_schema": t.get("input_schema") or {}, "hash": h,
                    "enabled": bool(p.get("enabled")) if same else False,
                    "requires_confirm": (p.get("requires_confirm") is not False) if same else True,
                    "changed": bool(p) and not same})
    return out


@router.post("/{server_id}/test", summary="Prueba la conexión y lista sus herramientas.")
async def test_server(server_id: str, org: str = Depends(get_org)):
    doc = await _get(server_id, org)
    conn = connection_of(doc)
    db = get_db()
    try:
        fresh = await mcp_client.list_tools(conn)
    except Exception as e:  # noqa: BLE001 — el error NUNCA lleva el secreto
        err = mcp_client.safe_error(e, conn)
        await db.mcp_servers.update_one(
            {"id": server_id, "org_id": org},
            {"$set": {"last_test_at": _now(), "last_test_ok": False, "last_error": err}})
        return {"ok": False, "error": err, "tools": public(doc)["tools"]}
    tools = merge_tools(doc.get("tools") or [], fresh)
    await db.mcp_servers.update_one(
        {"id": server_id, "org_id": org},
        {"$set": {"tools": tools, "last_test_at": _now(), "last_test_ok": True,
                  "last_error": "", "updated_at": _now()}})
    saved = await _get(server_id, org)
    return {"ok": True, "error": "", "tools": public(saved)["tools"],
            "changed": [t["name"] for t in tools if t.get("changed")]}


@router.put("/{server_id}/tools", summary="Activa/desactiva herramientas y su confirmación.")
async def put_tools(server_id: str, payload: ToolsIn, org: str = Depends(get_org)):
    doc = await _get(server_id, org)
    want = {t.name: t for t in payload.tools}
    tools = []
    for t in doc.get("tools") or []:
        w = want.get(t.get("name"))
        if w:
            t = {**t, "enabled": bool(w.enabled), "requires_confirm": bool(w.requires_confirm),
                 "changed": False}
        tools.append(t)
    await get_db().mcp_servers.update_one(
        {"id": server_id, "org_id": org}, {"$set": {"tools": tools, "updated_at": _now()}})
    saved = await _get(server_id, org)
    return {"ok": True, "tools": public(saved)["tools"]}


# ------------------------------------------------------------------ para el agente
async def active_tools(org: str) -> list[dict]:
    """Herramientas MCP ACTIVAS de este cliente:
    [{full_name, name, description, input_schema, requires_confirm, server}]."""
    docs = await get_db().mcp_servers.find({"org_id": org}, {"_id": 0}) \
        .sort("created_at", 1).to_list(50)
    out = []
    for d in docs:
        for t in d.get("tools") or []:
            if t.get("enabled"):
                out.append({"full_name": full_tool_name(d.get("slug") or "", t.get("name") or ""),
                            "name": t.get("name"), "description": t.get("description") or "",
                            "input_schema": t.get("input_schema") or {},
                            "requires_confirm": t.get("requires_confirm") is not False,
                            "server": d})
    return out


async def find_active_tool(org: str, full_name: str) -> dict | None:
    """La herramienta `mcp__<servidor>__<tool>` si está ACTIVA para este org."""
    for t in await active_tools(org):
        if t["full_name"] == full_name:
            return t
    return None
