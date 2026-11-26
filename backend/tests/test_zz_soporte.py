"""Soporte en la app: aislamiento por cuenta, equipo apagado por defecto y entrada solo con permiso vigente."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from fake_mongo import DB as FakeDB
import pytest


def run(c):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(c)
    finally:
        loop.close()


class Req:
    def __init__(self, tok): self.cookies = {"litper_session": tok} if tok else {}; self.headers = {}


class Resp:
    def __init__(self): self.cookie = None
    def set_cookie(self, **k): self.cookie = k


def test_soporte_pregunta_respuesta_permiso_y_entrada(monkeypatch):
    from fastapi import HTTPException
    from routes import soporte as sp, auth
    db = FakeDB()
    monkeypatch.setattr(sp, "get_db", lambda: db)
    base = {"encendida": set()}

    async def en_base(org, correo): return org in base["encendida"]
    monkeypatch.setattr(sp, "_equipo_en_base", en_base)
    cli = Req(auth._issue_token("u1", "A", "dueno@a.co"))
    otro = Req(auth._issue_token("u2", "B", "dueno@b.co"))
    eq = Req(auth._issue_token("u9", "ZX", "ayuda@zynex.co"))
    falso = Req(auth._issue_token("u8", "B", "ayuda@zynex.co"))        # mismo correo, otra cuenta

    run(sp.escribir(sp.MensajeIn(texto="No me cargan los pedidos"), cli))
    assert [m["texto"] for m in run(sp.mis_mensajes(cli))["mensajes"]] == ["No me cargan los pedidos"]
    assert run(sp.mis_mensajes(otro))["mensajes"] == []                 # otra cuenta no ve nada

    # equipo apagado por defecto
    with pytest.raises(HTTPException) as e: run(sp.bandeja(eq))
    assert e.value.status_code == 404
    monkeypatch.setenv("SUPPORT_STAFF_EMAILS", "ayuda@zynex.co"); monkeypatch.setenv("SUPPORT_STAFF_ORG", "ZX")
    with pytest.raises(HTTPException): run(sp.bandeja(cli))
    with pytest.raises(HTTPException): run(sp.bandeja(falso))
    base["encendida"] = {"B"}                                            # encendido desde la base: vale para esa cuenta y solo esa
    assert run(sp.bandeja(falso))["cuentas"][0]["org_id"] == "A"
    base["encendida"] = set()
    with pytest.raises(HTTPException): run(sp.bandeja(falso))
    b = run(sp.bandeja(eq))["cuentas"]
    assert [(c["org_id"], c["pendientes"], c["permiso"]) for c in b] == [("A", 1, False)]

    run(sp.responder(sp.RespuestaIn(org_id="A", texto="Ya lo revisamos"), eq))
    assert run(sp.mis_mensajes(cli, marcar=False))["sin_leer"] == 1      # mirar el punto rojo no lo apaga
    v = run(sp.mis_mensajes(cli))
    assert [m["de"] for m in v["mensajes"]] == ["cliente", "equipo"] and v["sin_leer"] == 1
    assert run(sp.mis_mensajes(cli))["sin_leer"] == 0 and "correo" not in v["mensajes"][1]

    # sin permiso no se entra
    with pytest.raises(HTTPException) as e: run(sp.entrar(sp.EntrarIn(org_id="A"), eq, Resp()))
    assert e.value.status_code == 403
    with pytest.raises(HTTPException): run(sp.dar_permiso(sp.PermisoIn(horas=500), cli))
    run(sp.dar_permiso(sp.PermisoIn(horas=1), cli))
    r = Resp(); ok = run(sp.entrar(sp.EntrarIn(org_id="A"), eq, r))
    c = auth._decode(r.cookie["value"])
    assert ok["ok"] and c["org"] == "A" and c["soporte"] is True and c["exp"] - c["iat"] <= 30 * 60 and r.cookie["httponly"]
    ses = Req(r.cookie["value"])
    # la sesión de soporte no puede escribir como el cliente, ni darse permiso, ni actuar como equipo
    for intento in (sp.escribir(sp.MensajeIn(texto="x"), ses), sp.dar_permiso(sp.PermisoIn(horas=72), ses), sp.bandeja(ses)):
        with pytest.raises(HTTPException): run(intento)
    assert [f["que"] for f in run(sp.registro(cli))["registro"]][0] in ("soporte_entro", "permiso_dado")
    assert {f["que"] for f in run(sp.registro(cli))["registro"]} == {"soporte_entro", "permiso_dado"}
    assert run(sp.registro(otro))["registro"] == []

    run(sp.quitar_permiso(cli))
    with pytest.raises(HTTPException): run(sp.entrar(sp.EntrarIn(org_id="A"), eq, Resp()))
    with pytest.raises(HTTPException) as e: run(sp.mis_mensajes(Req(None)))
    assert e.value.status_code == 401
