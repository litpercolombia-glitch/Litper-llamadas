import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from medir_llamadas_vs_dropi import clasificar_dropi, medir  # noqa: E402


def _q(i):
    return {"id": f"q{i}", "order_id": f"o{i}", "status": "pending"}


def test_clasificar_dropi():
    assert clasificar_dropi("ENTREGADO") == "entregado"
    assert clasificar_dropi("NO ENTREGADO") == "abierto"
    assert clasificar_dropi("DEVOLUCION") == "devuelto"
    assert clasificar_dropi("EN REPARTO") == "abierto"
    assert clasificar_dropi(None) == "sin_dato"


def test_medir_grupos_y_concordancia():
    queue = [_q(i) for i in range(4)]
    orders = [{"id": f"o{i}", "external_ref": str(100 + i)} for i in range(4)]
    real = {"channel": "call", "status": "done", "call_sid": "CA1", "result": "confirmado"}
    falsa = {"channel": "call", "status": "done", "result": "confirmado"}  # sin evidencia
    schedules = [
        {"queue_id": "q0", "attempts": [real]},
        {"queue_id": "q1", "attempts": [dict(real, result="rechaza")]},
        {"queue_id": "q2", "attempts": [falsa]},
    ]
    dropi = {"100": "ENTREGADO", "101": "ENTREGADO", "102": "DEVOLUCION", "103": "ENTREGADO"}
    r = medir(queue, schedules, orders, dropi)
    assert r["llamadas_reales"] == 2
    assert r["llamado"]["items"] == 2 and r["control"]["items"] == 2
    assert r["llamado"]["tasa_entrega_cerrados_pct"] == 100.0
    assert r["control"]["tasa_entrega_cerrados_pct"] == 50.0
    # q0 acierta (confirmado/entregado), q1 falla (rechaza/entregado)
    assert r["concordancia_llamada_vs_dropi_pct"] == 50.0
    assert r["hito_cumplido"] is False
