"""Iteration 6 — Final launch round tests: products+promotions, VIP funnel, order prompt vars."""
import os
import io
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://litper-hub.preview.emergentagent.com"
API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H"

HDR = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
PUB = {"Content-Type": "application/json"}


# ---------- VIP LEADS ----------
class TestVipFunnel:
    created_id = None

    def test_public_config(self):
        r = requests.get(f"{BASE}/api/vip-leads/config")
        assert r.status_code == 200
        j = r.json()
        assert "vip_group_url" in j and "chatea_configured" in j

    def test_public_create_lead(self):
        payload = {
            "nombre": "TEST_Funnel User",
            "whatsapp": "+573001112233",
            "pais": "CO",
            "pedidos_semana": "50-100",
        }
        r = requests.post(f"{BASE}/api/vip-leads", json=payload, headers=PUB)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "id" in j and "created_at" in j and "welcome_sent" in j
        assert j["nombre"] == payload["nombre"]
        TestVipFunnel.created_id = j["id"]

    def test_admin_list_shows_lead(self):
        r = requests.get(f"{BASE}/api/vip-leads", headers=HDR)
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert TestVipFunnel.created_id in ids

    def test_admin_patch_status(self):
        r = requests.patch(f"{BASE}/api/vip-leads/{TestVipFunnel.created_id}",
                           json={"status": "unido"}, headers=HDR)
        assert r.status_code == 200
        assert r.json()["status"] == "unido"

    def test_admin_export_xlsx(self):
        r = requests.get(f"{BASE}/api/vip-leads/export.xlsx", headers=HDR)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "")
        assert "litper_vip_leads.xlsx" in r.headers.get("content-disposition", "")
        assert r.content[:2] == b"PK"  # valid xlsx zip magic

    def test_admin_delete_lead(self):
        r = requests.delete(f"{BASE}/api/vip-leads/{TestVipFunnel.created_id}", headers=HDR)
        assert r.status_code == 200
        # verify gone
        r2 = requests.get(f"{BASE}/api/vip-leads", headers=HDR)
        assert TestVipFunnel.created_id not in [x["id"] for x in r2.json()]


# ---------- PRODUCTS ----------
class TestProducts:
    def test_list_seeded(self):
        r = requests.get(f"{BASE}/api/products", headers=HDR)
        assert r.status_code == 200
        names = [p["nombre"] for p in r.json()]
        assert "Protector Antifluido Premium" in names
        assert "Colcha + Sábana King 600 hilos" in names
        # each has promotions
        for p in r.json():
            assert "promotions" in p and isinstance(p["promotions"], list)

    def test_match_protector(self):
        r = requests.post(f"{BASE}/api/products/match",
                          json={"sku": "PROTECTOR MAS FUNDAS Verde"}, headers=HDR)
        assert r.status_code == 200
        j = r.json()
        assert j["matched"] is True
        assert "Protector Antifluido Premium + 2 Fundas" in j["promotion"]["nombre_comercial"]

    def test_match_colcha(self):
        r = requests.post(f"{BASE}/api/products/match",
                          json={"product_name": "COLCHA + SABANA KING 600 HILOS"}, headers=HDR)
        assert r.status_code == 200
        j = r.json()
        assert j["matched"] is True
        assert j["promotion"]["precio_promo"] == 229000

    def test_crud_product(self):
        payload = {
            "nombre": "TEST_ProductX",
            "slug": "test-productx",
            "descripcion": "test",
            "promotions": [{
                "sku_pattern": "TESTX",
                "nombre_comercial": "Test X promo",
                "precio_lista": 100000,
                "precio_promo": 79000,
                "bonos": [], "activa": True,
            }],
        }
        r = requests.post(f"{BASE}/api/products", json=payload, headers=HDR)
        assert r.status_code == 201, r.text
        pid = r.json()["id"]

        r = requests.patch(f"{BASE}/api/products/{pid}",
                           json={"descripcion": "updated"}, headers=HDR)
        assert r.status_code == 200

        r = requests.get(f"{BASE}/api/products/{pid}", headers=HDR)
        assert r.status_code == 200 and r.json()["descripcion"] == "updated"

        r = requests.delete(f"{BASE}/api/products/{pid}", headers=HDR)
        assert r.status_code == 200

        r = requests.get(f"{BASE}/api/products/{pid}", headers=HDR)
        assert r.status_code == 404


# ---------- ORDER PROMPT VARS ----------
class TestOrderPromptVars:
    def test_prompt_vars_include_promo_fields(self):
        # Pick any order from queue
        r = requests.get(f"{BASE}/api/queue?limit=50", headers=HDR)
        assert r.status_code == 200
        items = r.json()
        if not items:
            pytest.skip("No orders in queue to check prompt vars")

        # Find an order whose product name matches a seeded promo (best-case: a Protector or Colcha combo)
        target = None
        for it in items:
            oid = it.get("order_id") or it.get("id")
            if not oid:
                continue
            target = oid
            # prefer combos
            pn = (it.get("product_name") or "").upper()
            if "PROTECTOR" in pn or "COLCHA" in pn:
                break

        r = requests.get(f"{BASE}/api/orders/{target}/prompt-vars", headers=HDR)
        assert r.status_code == 200, r.text
        j = r.json()
        # All 3 promo fields must exist
        for k in ("promo_name", "promo_price", "promo_bonuses"):
            assert k in j, f"prompt-vars missing {k}: keys={list(j.keys())}"


# ---------- CORS / public POST (no key) ----------
class TestPublicNoKey:
    def test_vip_leads_post_no_key(self):
        r = requests.post(f"{BASE}/api/vip-leads",
                          json={"nombre": "TEST_NoKey", "whatsapp": "+573000000000",
                                "pais": "CO", "pedidos_semana": "10"},
                          headers={"Content-Type": "application/json"})
        assert r.status_code == 200, r.text
        # cleanup
        lid = r.json()["id"]
        requests.delete(f"{BASE}/api/vip-leads/{lid}", headers=HDR)
