"""Conectar Dropi sin API: lectura de la tabla del conector, aislamiento por cuenta y código de un solo uso (sin red)."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from fake_mongo import DB as FakeDB


def run(c):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(c)
    finally:
        loop.close()


def test_dropi_directo_lee_la_tabla_compacta_y_guarda_solo_en_su_cuenta(monkeypatch):
    from cryptography.fernet import Fernet
    from datetime import datetime, timedelta, timezone
    from routes import dropi_conexion as dc, zynex_motor
    import mcp_client
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    db = FakeDB()
    monkeypatch.setattr(dc, "get_db", lambda: db)
    tabla = ('items[2]{order_id,status,customer_name,customer_phone,city,total,currency,shipping_company,created_at,tracking_code}:\n'
             '  "981",GUIA_GENERADA,Ana Paz,"3001112233",CALI,219900,COP,ENVIA,"2026-11-26T08:31:21","G1"\n'
             '  "982",PENDIENTE CONFIRMACION,"Luz, M","3002223344",BOGOTA,89900,COP,"","2026-11-26T09:00:00",""\n'
             'count: 2')
    assert [p["order_id"] for p in dc.pedidos_de_texto(tabla)] == ["981", "982"]
    assert dc.pedidos_de_texto('{"objects":[{"id":5,"status":"X"}]}') == [{"id": 5, "status": "X"}]
    assert dc.pedidos_de_texto("sin pedidos") == []
    vence = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    run(db.dropi_conexiones.insert_one({"org_id": "A", "conectado": True, "client_id": "c", "vence": vence,
                                        "acceso_ct": dc._cifrar("permiso-de-A")}))
    usados, guardado = [], []

    async def call_tool(servidor, nombre, args):
        usados.append((servidor["secret"], nombre, args["start"]))
        return {"text": tabla, "is_error": False, "truncated": False}
    monkeypatch.setattr(mcp_client, "call_tool", call_tool)

    async def rpc(fn, args):
        guardado.append(args)
        return {"ok": True, "guardados": len(args["p_filas"])}
    monkeypatch.setattr(zynex_motor, "rpc", rpc)
    r = run(dc.sincronizar("A"))
    assert r == {"ok": True, "leidos": 2, "guardados": 2}
    assert usados == [("permiso-de-A", "list_orders", 0)] and guardado[0]["p_org"] == "A"
    f = guardado[0]["p_filas"][0]
    assert (f["pedido"], f["estado"], f["telefono"], f["guia"], f["creado"]) == ("981", "GUIA_GENERADA", "3001112233", "G1", "2026-11-26")
    assert run(dc.sincronizar("B")) == {"ok": False, "error": "reconectar"} and len(usados) == 1
    doc = run(db.dropi_conexiones.find_one({"org_id": "A"}))
    assert "permiso-de-A" not in str(doc) and doc["ultimo_guardados"] == 2


def test_dropi_directo_la_vuelta_exige_codigo_de_un_solo_uso(monkeypatch):
    from cryptography.fernet import Fernet
    from datetime import datetime, timedelta, timezone
    from routes import dropi_conexion as dc
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    db = FakeDB()
    monkeypatch.setattr(dc, "get_db", lambda: db)
    canjes = []

    async def post(url, json_body=None, form=None):
        canjes.append(form)
        return {"access_token": "tok-secreto-1", "refresh_token": "tok-secreto-2", "expires_in": 3600}
    monkeypatch.setattr(dc, "_post", post)
    r = run(dc.vuelta(code="x", state="inventado"))
    assert r.headers["location"].endswith("dropi=vencido") and not canjes
    run(db.dropi_oauth_estados.insert_one({"estado": "s1", "org_id": "A", "verificador_ct": dc._cifrar("v"), "client_id": "c",
                                           "redirect": "https://api/vuelta", "usado": False,
                                           "vence": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}))
    r = run(dc.vuelta(code="x", state="s1"))
    assert r.headers["location"].endswith("dropi=conectado") and canjes[0]["code_verifier"] == "v"
    doc = run(db.dropi_conexiones.find_one({"org_id": "A"}))
    assert doc["conectado"] and "tok-secreto" not in str(doc) and dc._descifrar(doc["acceso_ct"]) == "tok-secreto-1"
    r = run(dc.vuelta(code="x", state="s1"))                      # el mismo código no sirve dos veces
    assert r.headers["location"].endswith("dropi=vencido") and len(canjes) == 1
