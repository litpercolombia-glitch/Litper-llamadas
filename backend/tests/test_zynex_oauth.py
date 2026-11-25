"""Inicio de sesión del conector de Claude: metadatos, registro, PKCE y límites (sin red)."""
import os, sys, base64, hashlib, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from urllib.parse import urlparse, parse_qs
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import zynex_oauth as zo

app = FastAPI(); app.include_router(zo.router)
cli = TestClient(app, base_url="https://api.zynexapp.com")
RU = "https://claude.ai/api/mcp/auth_callback"

def _pkce():
    v = "v" * 50
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()

def _code(monkeypatch, valido=True, **extra):
    async def org(tok): return "org-x" if valido and tok == "zx_bueno123" else None
    monkeypatch.setattr(zo.zc, "org_por_token_mcp", org)
    v, cc = _pkce()
    p = {"response_type": "code", "client_id": "c1", "redirect_uri": RU, "code_challenge": cc, "code_challenge_method": "S256",
         "state": "s1", "resource": "https://api.zynexapp.com/api/mcp/zx_bueno123", **extra}
    r = cli.get("/authorize", params=p, follow_redirects=False)
    return r, v

def test_metadatos():
    m = cli.get("/.well-known/oauth-authorization-server").json()
    assert m["token_endpoint"].endswith("/token") and m["code_challenge_methods_supported"] == ["S256"]
    r = cli.get("/.well-known/oauth-protected-resource/api/mcp/zx_abc").json()
    assert r["resource"].endswith("/api/mcp/zx_abc") and r["authorization_servers"]

def test_registro_solo_claude_o_local():
    assert cli.post("/register", json={"redirect_uris": [RU]}).status_code == 201
    assert cli.post("/register", json={"redirect_uris": ["http://localhost:3334/cb"]}).status_code == 201
    for malo in [["https://evil.com/cb"], ["https://claude.ai.evil.com/cb"], ["http://claude.ai/cb"], []]:
        assert cli.post("/register", json={"redirect_uris": malo}).status_code == 400

def test_flujo_completo_y_refresco(monkeypatch):
    r, v = _code(monkeypatch)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["state"] == ["s1"] and "code" in q
    t = cli.post("/token", data={"grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": RU, "code_verifier": v, "client_id": "c1"})
    assert t.status_code == 200 and t.json()["token_type"] == "Bearer"
    t2 = cli.post("/token", data={"grant_type": "refresh_token", "refresh_token": t.json()["refresh_token"]})
    assert t2.status_code == 200 and t2.json()["access_token"] != t.json()["access_token"]

def test_rechazos(monkeypatch):
    r, v = _code(monkeypatch)
    code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
    base = {"grant_type": "authorization_code", "code": code, "redirect_uri": RU}
    assert cli.post("/token", data={**base, "code_verifier": "otro" * 12}).status_code == 400
    assert cli.post("/token", data={**base, "code_verifier": v, "redirect_uri": "https://claude.ai/otra"}).status_code == 400
    assert cli.post("/token", data={**base, "code_verifier": v, "code": code[:-2] + "xx"}).status_code == 400
    assert cli.post("/token", data={"grant_type": "refresh_token", "refresh_token": code}).status_code == 400
    assert cli.post("/token", data={"grant_type": "password"}).status_code == 400
    r, _ = _code(monkeypatch, valido=False)
    assert "error=access_denied" in r.headers["location"]
    r, _ = _code(monkeypatch, code_challenge_method="plain")
    assert "error=invalid_request" in r.headers["location"]
    assert cli.get("/authorize", params={"redirect_uri": "https://evil.com/cb", "response_type": "code", "code_challenge": "x"}, follow_redirects=False).status_code == 400

def test_codigo_vencido(monkeypatch):
    c = zo.firmar({"t": "code", "cc": "x", "ru": RU, "exp": int(time.time()) - 1})
    assert zo.leer(c, "code") is None and zo.leer(zo.firmar({"t": "acc", "exp": int(time.time()) + 60}), "code") is None
