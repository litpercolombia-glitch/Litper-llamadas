"""Zynex Call + conector de Claude: unitarias con Mongo falso, sin red."""
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import test_byok_openrouter as banco
from fake_mongo import DB as RichDB
banco.FAKE.__class__ = RichDB
from datetime import datetime, timezone
from routes import zynex_call as zc, zynex_mcp as zm

ORG, OTRA = "org-zc", "org-otra"
def run(c): return asyncio.run(c)

CAMPOS = [{"var_ns": "f1", "name": "Nombre completo"}, {"var_ns": "f2", "name": "Valor de la compra"},
          {"var_ns": "f3", "name": "Productos escogidos"}, {"var_ns": "f4", "name": "[Logistica] Dirección para llamadas"},
          {"var_ns": "f5", "name": "Ciudad"}, {"var_ns": "f6", "name": "Último Estado recibido"},
          {"var_ns": "f7", "name": "[Logistica] ID de la orden"}, {"var_ns": "f8", "name": "Nombre"}]

def test_transformaciones():
    assert zc.transformar("MARTHA LILIANA perez", "nombre_corto") == "Martha Liliana"
    assert zc.transformar("MEDELLIN (Q), ANTIOQUIA", "ciudad") == "Medellin"
    assert zc.transformar("$ 89.900", "numero") == "89900"
    assert zc.tel_co("314 464 4054") == "+573144644054"
    assert zc.norm_resultado("3") == "YA_RECIBIDO"
    assert zc.norm_resultado("buzón o sin respuesta") == "BUZON_SIN_RESPUESTA"

def test_automapeo_con_respaldos():
    prop = {p["variable"]: p for p in zc.automapear(CAMPOS)}
    assert prop["cliente"]["ref"] == "f1" and prop["cliente"]["refs_alt"] == ["f8"]
    assert prop["estado_dropi"]["ref"] == "f6" and prop["dropi_order_id"]["ref"] == "f7"

def test_ventana_lunes_a_sabado():
    cfg = {"ventana_ini": "08:00", "ventana_fin": "10:00"}
    dom = datetime(2026, 11, 29, 14, 0, tzinfo=timezone.utc)  # domingo 9 a. m. Bogotá
    assert not zc.en_ventana(cfg, dom)
    lun = datetime(2026, 11, 30, 14, 0, tzinfo=timezone.utc)  # lunes 9 a. m.
    assert zc.en_ventana(cfg, lun)

def test_subir_pedidos_cola_bloqueo_y_aislamiento():
    async def go():
        await zc.asegurar(ORG); await zc.asegurar(OTRA)
        await banco.FAKE.zc_agentes.update_many({"org_id": ORG}, {"$set": {"activo": True}})
        r = await zc.subir_pedidos(ORG, [
            {"dropi_order_id": "1", "estado_dropi": "pendiente confirmacion", "cliente": "ana gomez", "telefono": "3001234567",
             "valor": "89.900", "producto": "protector", "direccion": "cra 1", "ciudad": "cali"},
            {"dropi_order_id": "2", "estado_dropi": "EN REPARTO", "cliente": "luis", "telefono": "", "valor": "50000"},
            {"dropi_order_id": "3", "estado_dropi": "ENTREGADO", "cliente": "x", "telefono": "3001112233", "valor": "1"},
            {"dropi_order_id": "1", "estado_dropi": "PENDIENTE CONFIRMACION", "cliente": "ana", "telefono": "3001234567",
             "valor": "89900", "producto": "p", "direccion": "d", "ciudad": "c"}])
        assert r == {"recibidos": 4, "encolados": 1, "bloqueados": 1, "sin_agente": 1, "duplicados": 1}
        assert await banco.FAKE.zc_llamadas.count_documents({"org_id": OTRA}) == 0
    run(go())

def test_mcp_token_y_herramientas():
    async def go():
        await banco.FAKE.zc_config.update_one({"org_id": ORG}, {"$set": {"mcp_token_hash": zc._sha("zx_t")}})
        assert await zc.org_por_token_mcp("zx_t") == ORG
        assert await zc.org_por_token_mcp("malo") is None
        names = [t["name"] for t in zm.TOOLS]
        assert "zynex_subir_pedidos" in names and "zynex_resultados" in names
        out = await zm._call(ORG, "zynex_cola", {})
        assert "bloqueada" in out["content"][0]["text"]
    run(go())

def test_modo_prueba_no_llama_a_clientes(monkeypatch):
    async def go():
        llamadas = []
        async def llave(org, prov, campo="api_key"): return "k"
        async def marcar(org, ll, cfg): llamadas.append(ll["telefono"]); return {"ok": True}
        monkeypatch.setattr(zc, "_llave", llave); monkeypatch.setattr(zc, "marcar", marcar)
        monkeypatch.setattr(zc, "en_ventana", lambda cfg, t=None: True)
        await banco.FAKE.zc_llamadas.update_many({"org_id": ORG}, {"$set": {"proxima_llamada": "2000-01-01"}})
        r = await zc.despachar(ORG)
        assert llamadas == [] and any("modo prueba" in str(x) for x in r["procesadas"])
    run(go())
