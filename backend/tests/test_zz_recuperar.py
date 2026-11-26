"""Recuperar contraseña: no revela cuentas, código de un solo uso con vencimiento y límite de intentos."""
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


def test_recuperar_clave_de_punta_a_punta(monkeypatch):
    from fastapi import HTTPException
    from routes import recuperar as rc, auth
    import ratelimit
    ratelimit.reset_all()
    db = FakeDB()
    monkeypatch.setattr(rc, "get_db", lambda: db)
    run(db.users.insert_one({"id": "u1", "email": "ana@tienda.co", "password_hash": auth._hash("vieja-clave"), "provider": "email"}))
    run(db.users.insert_one({"id": "u2", "email": "g@tienda.co", "provider": "google"}))
    enviados = []
    monkeypatch.setattr(rc, "_enviar", lambda destino, enlace: enviados.append((destino, enlace)) or True)

    # sin correo saliente: lo dice de frente y no crea códigos
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert run(rc.estado()) == {"por_correo": False}
    with pytest.raises(HTTPException) as e: run(rc.pedir(rc.PedirIn(email="ana@tienda.co")))
    assert e.value.status_code == 503 and not enviados and not db.clave_codigos.docs
    ratelimit.reset_all()

    monkeypatch.setenv("SMTP_HOST", "smtp.ejemplo.co")
    r1 = run(rc.pedir(rc.PedirIn(email="Ana@Tienda.co")))
    r2 = run(rc.pedir(rc.PedirIn(email="nadie@tienda.co")))
    r3 = run(rc.pedir(rc.PedirIn(email="g@tienda.co")))
    assert r1 == r2 == r3 == rc.RESPUESTA                    # misma respuesta exista o no
    assert [d for d, _ in enviados] == ["ana@tienda.co"]      # solo sale un correo
    enlace = enviados[0][1]
    codigo = enlace.split("clave=")[1]
    assert enlace.startswith("https://call.zynexapp.com/login?clave=") and codigo not in str(db.clave_codigos.docs)

    with pytest.raises(HTTPException): run(rc.cambiar(rc.CambiarIn(codigo="x" * 30, password="nueva-clave-1")))
    assert run(rc.cambiar(rc.CambiarIn(codigo=codigo, password="nueva-clave-1")))["ok"]
    u = run(db.users.find_one({"id": "u1"}))
    assert auth._verify("nueva-clave-1", u["password_hash"]) and not auth._verify("vieja-clave", u["password_hash"])
    with pytest.raises(HTTPException): run(rc.cambiar(rc.CambiarIn(codigo=codigo, password="otra-clave-22")))   # un solo uso

    # vencido
    run(rc.pedir(rc.PedirIn(email="ana@tienda.co")))
    c2 = enviados[-1][1].split("clave=")[1]
    run(db.clave_codigos.update_many({"usado": False}, {"$set": {"vence": "2000-01-01T00:00:00+00:00"}}))
    with pytest.raises(HTTPException): run(rc.cambiar(rc.CambiarIn(codigo=c2, password="otra-clave-22")))

    # límite: 3 por hora por correo
    run(rc.pedir(rc.PedirIn(email="ana@tienda.co")))
    with pytest.raises(HTTPException) as e: run(rc.pedir(rc.PedirIn(email="ana@tienda.co")))
    assert e.value.status_code == 429
    ratelimit.reset_all()
