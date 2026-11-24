"""Cliente MCP propio (Model Context Protocol) — transporte Streamable HTTP.

Sin dependencias nuevas: solo httpx + JSON-RPC 2.0. (El SDK `mcp` 2.x choca
con uvicorn 0.25.)

    tools  = await list_tools(server)
    result = await call_tool(server, "nombre", {"arg": 1})

`server` = {"url", "auth_type": "none"|"bearer"|"header", "secret", "header_name"}
(el secreto llega YA descifrado desde routes/mcp_servers.py y nunca sale de aquí).

Funciona con servidores:
  * con sesión: `initialize` → `notifications/initialized`; si el servidor
    devuelve la cabecera `Mcp-Session-Id` se reenvía en cada petición;
  * sin estado: si `initialize` no está soportado (HTTP 400/404/405/501 o
    JSON-RPC -32601) se llama directo al método pedido.
Respuestas `application/json` o `text/event-stream` (se leen los eventos
`data:` hasta encontrar la respuesta con el id pedido).

SEGURIDAD
  * solo https (http solo con ALLOW_INSECURE_MCP=1);
  * solo puertos 443 y 8443 (cualquier otro solo con ALLOW_INSECURE_MCP=1):
    un conector no sirve para sondear puertos de terceros;
  * anti-SSRF: se resuelve el host y se rechaza cualquier IP privada, loopback,
    link-local, de metadatos, multicast o reservada. La conexión se FIJA a la
    IP validada (Host + SNI con el nombre original) para que un cambio de DNS
    entre la comprobación y la conexión no sirva de nada;
  * no se siguen redirecciones (ni al mismo host: un 3xx es un error);
  * 20 s por petición; respuesta máx. 200 KB (lo que exceda se trunca);
  * ningún secreto aparece en errores ni logs.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import re
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

log = logging.getLogger("mcp.client")

PROTOCOL_VERSION = "2025-06-18"
TIMEOUT_S = 20
MAX_BYTES = 200 * 1024
MAX_TOOLS = 200
MAX_PAGES = 5
CLIENT_INFO = {"name": "zynex-os", "version": "1.0"}

_HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]{1,64}$")
# Cabeceras que el cliente NO puede usar como "cabecera personalizada".
_FORBIDDEN_HEADERS = {"host", "content-length", "content-type", "accept", "connection",
                      "transfer-encoding", "upgrade", "te", "trailer", "cookie",
                      "mcp-session-id", "mcp-protocol-version", "mcp-method", "mcp-name",
                      "proxy-authorization", "x-forwarded-for", "x-forwarded-host"}
_NO_INIT_STATUS = {400, 404, 405, 501}
_METADATA_HOSTS = {"metadata.google.internal", "metadata", "instance-data"}


class McpError(RuntimeError):
    """Error del cliente MCP. El mensaje ya viene SIN secretos."""


# ------------------------------------------------------------------ seguridad
def insecure_allowed() -> bool:
    return os.environ.get("ALLOW_INSECURE_MCP", "").strip() == "1"


def _scrub(text: str, secrets: list[str] | None = None) -> str:
    """Quita secretos de un texto (llaves conocidas + patrones de llaves)."""
    out = str(text)
    for s in secrets or []:
        if s:
            out = out.replace(s, "***")
    try:
        from agent.router import _KEY_PATTERNS
        out = _KEY_PATTERNS.sub("***", out)
    except Exception:  # noqa: BLE001
        pass
    return out[:400]


def _safe(e: Exception, secrets: list[str] | None = None) -> str:
    if isinstance(e, McpError):
        return _scrub(str(e), secrets)
    try:
        from agent.router import _safe_err
        return _scrub(_safe_err(e, secrets), secrets)
    except Exception:  # noqa: BLE001
        return _scrub(f"{type(e).__name__}: {e}", secrets)


def validate_header_name(name: str) -> str:
    name = (name or "").strip()
    if not _HEADER_NAME_RE.match(name) or name.lower() in _FORBIDDEN_HEADERS:
        raise McpError("Nombre de cabecera no permitido.")
    return name


ALLOWED_PORTS = frozenset({443, 8443})


def validate_url(url: str) -> tuple[str, str, int, str]:
    """Valida la FORMA de la URL (sin red). Devuelve (esquema, host, puerto, ruta)."""
    try:
        u = urlsplit((url or "").strip())
        port = u.port
    except ValueError:
        raise McpError("La dirección del servidor no es válida.")
    scheme = (u.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise McpError("La dirección debe empezar por https://")
    if scheme == "http" and not insecure_allowed():
        raise McpError("Solo se permiten servidores https://")
    if u.username or u.password:
        raise McpError("La dirección no puede llevar usuario ni contraseña.")
    host = (u.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise McpError("La dirección del servidor no es válida.")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".internal") \
            or host.endswith(".local") or host in _METADATA_HOSTS:
        raise McpError("Dirección no permitida (red interna).")
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    port = port or (443 if scheme == "https" else 80)
    if port not in ALLOWED_PORTS and not insecure_allowed():
        raise McpError("Puerto no permitido: usa el 443 (o el 8443).")
    return scheme, host, port, path


def _ip_blocked(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return True
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast
            or a.is_reserved or a.is_unspecified or not a.is_global
            or a in ipaddress.ip_network("100.64.0.0/10")           # CGNAT
            or a in ipaddress.ip_network("169.254.0.0/16"))         # metadatos / link-local


async def _resolve(host: str, port: int) -> list[str]:
    """IPs del host (función aparte para poder simularla en pruebas)."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(i[4][0] for i in infos))


async def check_target(url: str) -> dict[str, Any]:
    """Valida la URL y resuelve el host. Rechaza si CUALQUIER IP es interna.
    Devuelve el destino fijado: {scheme, host, port, path, ip}."""
    scheme, host, port, path = validate_url(url)
    try:
        ipaddress.ip_address(host)
        ips = [host]
    except ValueError:
        try:
            ips = await asyncio.wait_for(_resolve(host, port), timeout=TIMEOUT_S)
        except McpError:
            raise
        except Exception:  # noqa: BLE001
            raise McpError("No se pudo resolver la dirección del servidor.")
    if not ips:
        raise McpError("No se pudo resolver la dirección del servidor.")
    if any(_ip_blocked(ip) for ip in ips):
        raise McpError("Dirección no permitida: apunta a una red interna o privada.")
    return {"scheme": scheme, "host": host, "port": port, "path": path, "ip": ips[0]}


# ------------------------------------------------------------------ transporte
def _auth_headers(server: dict) -> dict[str, str]:
    kind = (server.get("auth_type") or "none").lower()
    secret = server.get("secret") or ""
    if kind == "bearer" and secret:
        return {"Authorization": f"Bearer {secret}"}
    if kind == "header" and secret:
        return {validate_header_name(server.get("header_name") or ""): secret}
    return {}


def _parse_sse(buf: str, want_id: Any) -> dict | None:
    """Busca en los eventos SSE completos la respuesta JSON-RPC con `want_id`."""
    for event in re.split(r"\r?\n\r?\n", buf):
        data = [ln[5:].lstrip(" ") for ln in event.splitlines() if ln.startswith("data:")]
        if not data:
            continue
        try:
            msg = json.loads("\n".join(data))
        except ValueError:
            continue
        for m in (msg if isinstance(msg, list) else [msg]):
            if isinstance(m, dict) and m.get("id") == want_id and ("result" in m or "error" in m):
                return m
    return None


class _Session:
    """Una conversación con un servidor MCP (un AsyncClient, una sesión)."""

    def __init__(self, server: dict, target: dict):
        self.server = server
        self.t = target
        self.secrets = [server.get("secret") or ""]
        self.session_id: str | None = None
        self.protocol = PROTOCOL_VERSION
        self._id = 0
        ip = target["ip"]
        netloc = f"[{ip}]" if ":" in ip else ip
        default_port = 443 if target["scheme"] == "https" else 80
        if target["port"] != default_port:
            netloc += f":{target['port']}"
        # Conexión FIJADA a la IP validada; Host y SNI llevan el nombre real.
        self.url = f"{target['scheme']}://{netloc}{target['path']}"
        self.host_header = target["host"] if target["port"] == default_port \
            else f"{target['host']}:{target['port']}"
        self.cli = httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_S), follow_redirects=False)

    async def close(self):
        if self.session_id:          # cierre cortés de la sesión (best-effort)
            try:
                await asyncio.wait_for(self.cli.request(
                    "DELETE", self.url, headers=self._headers(None, None),
                    extensions=self._ext()), timeout=5)
            except Exception:  # noqa: BLE001
                pass
        await self.cli.aclose()

    def _ext(self) -> dict:
        return {"sni_hostname": self.t["host"]} if self.t["scheme"] == "https" else {}

    def _headers(self, method: str | None, name: str | None) -> dict[str, str]:
        h = {"Host": self.host_header,
             "Accept": "application/json, text/event-stream",
             "Content-Type": "application/json",
             "MCP-Protocol-Version": self.protocol,
             **_auth_headers(self.server)}
        if method:
            h["Mcp-Method"] = method
        if name:
            h["Mcp-Name"] = re.sub(r"[^\x21-\x7e]", "_", name)[:128]
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    async def _post(self, payload: dict, name: str | None = None) -> dict:
        """Un POST JSON-RPC. Devuelve {"status", "msg" (respuesta JSON-RPC o None),
        "truncated", "raw"}."""
        want_id = payload.get("id")

        async def go() -> dict:
            async with self.cli.stream("POST", self.url, json=payload,
                                       headers=self._headers(payload.get("method"), name),
                                       extensions=self._ext()) as r:
                if 300 <= r.status_code < 400:
                    raise McpError("El servidor respondió con una redirección; no se siguen "
                                   "redirecciones. Usa la dirección final del servidor.")
                sid = r.headers.get("mcp-session-id")
                if sid and re.fullmatch(r"[\x21-\x7e]{1,256}", sid):
                    self.session_id = sid
                if want_id is None:          # notificación: no se espera cuerpo
                    return {"status": r.status_code, "msg": None, "truncated": False, "raw": ""}
                ctype = (r.headers.get("content-type") or "").lower()
                sse = "text/event-stream" in ctype
                buf = bytearray()
                truncated = False
                msg = None
                async for chunk in r.aiter_bytes():
                    room = MAX_BYTES - len(buf)
                    if len(chunk) > room:
                        buf += chunk[:max(room, 0)]
                        truncated = True
                    else:
                        buf += chunk
                    if sse and want_id is not None:
                        msg = _parse_sse(buf.decode("utf-8", "replace"), want_id)
                        if msg:
                            break
                    if truncated:
                        break
                text = buf.decode("utf-8", "replace")
                if msg is None and not sse and text.strip():
                    try:
                        j = json.loads(text)
                        for m in (j if isinstance(j, list) else [j]):
                            if isinstance(m, dict) and (want_id is None or m.get("id") == want_id
                                                        or "error" in m):
                                msg = m
                                break
                    except ValueError:
                        msg = None
                elif msg is None and sse:
                    msg = _parse_sse(text + "\n\n", want_id)
                return {"status": r.status_code, "msg": msg, "truncated": truncated, "raw": text}

        try:
            return await asyncio.wait_for(go(), timeout=TIMEOUT_S)
        except McpError:
            raise
        except asyncio.TimeoutError:
            raise McpError(f"El servidor no respondió en {TIMEOUT_S} segundos.")
        except Exception as e:  # noqa: BLE001
            raise McpError("No se pudo conectar con el servidor: " + _safe(e, self.secrets))

    async def request(self, method: str, params: dict | None = None,
                      name: str | None = None) -> dict:
        self._id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        return await self._post(payload, name)

    async def notify(self, method: str) -> None:
        try:
            await self._post({"jsonrpc": "2.0", "method": method})
        except McpError:
            pass                     # una notificación fallida no impide trabajar

    async def initialize(self) -> None:
        """Abre sesión si el servidor la usa; si no soporta `initialize`, sigue."""
        r = await self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO})
        msg, status = r["msg"], r["status"]
        if status in (401, 403):
            raise McpError(f"El servidor rechazó las credenciales (HTTP {status}).")
        err = (msg or {}).get("error") if isinstance(msg, dict) else None
        if err or status in _NO_INIT_STATUS or (status < 400 and not msg):
            code = (err or {}).get("code") if isinstance(err, dict) else None
            if code in (-32601, None) or status in _NO_INIT_STATUS:
                self.session_id = None           # servidor sin estado: llamadas directas
                return
            raise McpError("El servidor rechazó la conexión: " + self._err_text(err))
        if status >= 400:
            raise McpError(f"El servidor respondió HTTP {status} al iniciar.")
        ver = ((msg or {}).get("result") or {}).get("protocolVersion")
        if isinstance(ver, str) and re.fullmatch(r"[0-9A-Za-z.\-]{4,32}", ver):
            self.protocol = ver
        await self.notify("notifications/initialized")

    def _err_text(self, err: Any) -> str:
        if isinstance(err, dict):
            return _scrub(str(err.get("message") or err.get("code") or "error"), self.secrets)[:200]
        return _scrub(str(err), self.secrets)[:200]

    def result_of(self, r: dict, what: str) -> dict:
        msg, status = r["msg"], r["status"]
        if status in (401, 403):
            raise McpError(f"El servidor rechazó las credenciales (HTTP {status}).")
        if isinstance(msg, dict) and msg.get("error"):
            raise McpError(f"El servidor devolvió un error en {what}: " + self._err_text(msg["error"]))
        if status >= 400:
            raise McpError(f"El servidor respondió HTTP {status} en {what}.")
        if not isinstance(msg, dict) or not isinstance(msg.get("result"), dict):
            if r["truncated"]:
                raise McpError(f"La respuesta de {what} supera el máximo de {MAX_BYTES // 1024} KB.")
            raise McpError(f"El servidor no devolvió una respuesta MCP válida en {what}.")
        return msg["result"]


async def _open(server: dict) -> _Session:
    try:
        _auth_headers(server)                       # valida la cabecera personalizada
        target = await check_target(server.get("url") or "")
    except McpError as e:
        raise McpError(_scrub(str(e), [server.get("secret") or ""]))
    s = _Session(server, target)
    try:
        await s.initialize()
    except BaseException:
        await s.close()
        raise
    return s


# ------------------------------------------------------------------ API pública
async def list_tools(server: dict) -> list[dict[str, Any]]:
    """Herramientas del servidor: [{name, description, input_schema}]."""
    s = await _open(server)
    try:
        tools: list[dict[str, Any]] = []
        cursor = None
        for _ in range(MAX_PAGES):
            r = await s.request("tools/list", {"cursor": cursor} if cursor else {})
            res = s.result_of(r, "tools/list")
            for t in res.get("tools") or []:
                if not isinstance(t, dict) or not isinstance(t.get("name"), str) or not t["name"]:
                    continue
                schema = t.get("inputSchema")
                tools.append({"name": t["name"][:128],
                              "description": str(t.get("description") or "")[:2000],
                              "input_schema": schema if isinstance(schema, dict) else {}})
            cursor = res.get("nextCursor")
            if not cursor or len(tools) >= MAX_TOOLS:
                break
        return tools[:MAX_TOOLS]
    finally:
        await s.close()


def _content_text(result: dict) -> str:
    parts: list[str] = []
    for c in result.get("content") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "text":
            parts.append(str(c.get("text") or ""))
        elif c.get("type") == "resource" and isinstance(c.get("resource"), dict):
            parts.append(str(c["resource"].get("text") or c["resource"].get("uri") or ""))
        else:
            parts.append(f"[contenido {c.get('type') or 'desconocido'} omitido]")
    if not parts and result.get("structuredContent") is not None:
        parts.append(json.dumps(result["structuredContent"], ensure_ascii=False, default=str))
    return "\n".join(p for p in parts if p)


def _hide(text: str, secrets: list[str]) -> str:
    """Si el servidor devuelve nuestro propio secreto, no llega al modelo."""
    for sec in secrets:
        if sec:
            text = text.replace(sec, "***")
    return text


async def call_tool(server: dict, name: str, args: dict | None = None) -> dict[str, Any]:
    """Ejecuta una herramienta. Devuelve {"text", "is_error", "truncated"}.
    El texto es DATO EXTERNO: quien lo use debe tratarlo como no confiable."""
    s = await _open(server)
    try:
        r = await s.request("tools/call", {"name": name, "arguments": args or {}}, name=name)
        if r["truncated"] and not (isinstance(r["msg"], dict) and "result" in r["msg"]):
            if r["status"] < 400:
                # Respuesta más grande que el máximo: se entrega truncada, marcada.
                return {"text": _hide(r["raw"][:MAX_BYTES], s.secrets),
                        "is_error": False, "truncated": True}
        res = s.result_of(r, "tools/call")
        text = _content_text(res)
        truncated = bool(r["truncated"]) or len(text.encode("utf-8", "ignore")) > MAX_BYTES
        if truncated:
            text = text.encode("utf-8", "ignore")[:MAX_BYTES].decode("utf-8", "ignore")
        return {"text": _hide(text, s.secrets), "is_error": bool(res.get("isError")),
                "truncated": truncated}
    finally:
        await s.close()


def safe_error(e: Exception, server: dict | None = None) -> str:
    """Mensaje de error apto para mostrar al cliente (sin secretos)."""
    return _safe(e, [(server or {}).get("secret") or ""])
