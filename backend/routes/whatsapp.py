"""Routes: /whatsapp — send outbound messages via Chatea Pro."""
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException

from db import get_db
from deps import require_api_key
from models import WhatsAppSend, Message
from chatea import get_client as get_chatea

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"],
                   dependencies=[Depends(require_api_key)])


@router.post("/send", response_model=Message,
             summary="Send a WhatsApp message (free text or template) via Chatea Pro.")
async def send(payload: WhatsAppSend):
    if not payload.text and not payload.template_name:
        raise HTTPException(400, "Provide 'text' or 'template_name'.")
    chatea = get_chatea()
    if payload.template_name:
        res = await chatea.send_template(payload.phone, payload.template_name,
                                         payload.template_params)
        body = f"[template:{payload.template_name}] {payload.template_params}"
    else:
        res = await chatea.send_message(payload.phone, payload.text or "")
        body = payload.text or ""

    msg = Message(
        id=str(uuid.uuid4()),
        order_id=payload.order_id,
        queue_id=payload.queue_id,
        direction="outbound",
        channel="whatsapp",
        phone=payload.phone,
        template_name=payload.template_name,
        body=body,
        provider="chatea_pro",
        provider_message_id=res.get("provider_message_id"),
        status="sent" if res.get("ok") else "failed",
        error=res.get("error") or (None if res.get("ok") else f"HTTP {res.get('status_code')}"),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    await get_db().message_log.insert_one(msg.model_dump())
    return msg


@router.get("/messages", summary="List message log (WhatsApp sent/received).")
async def list_messages(limit: int = 100, queue_id: str | None = None):
    q = {}
    if queue_id:
        q["queue_id"] = queue_id
    docs = await get_db().message_log.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    return docs


# ---------------------------------------------------------------------------
# TEMPLATES (Chatea Pro) + RULES (0-3d "Reclamo en Oficina" / +3d "No Oficina")
# ---------------------------------------------------------------------------
from models import WhatsappRule, WhatsappRuleIn


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/templates",
            summary="Fetch approved WhatsApp templates from Chatea Pro.")
async def list_wa_templates():
    chatea = get_chatea()
    if not chatea.configured:
        return {"ok": False, "configured": False,
                "templates": [], "error": "CHATEA_PRO_API_KEY no configurada."}
    r = await chatea.list_templates()
    body = r.get("body") or {}
    templates: list[dict] = []
    if isinstance(body, list):
        templates = body
    elif isinstance(body, dict):
        for k in ("templates", "data", "result"):
            if isinstance(body.get(k), list):
                templates = body[k]; break
    return {"ok": r.get("ok"), "configured": True,
            "status_code": r.get("status_code"),
            "templates": templates}


@router.get("/rules", response_model=list[WhatsappRule],
            summary="List WhatsApp template rules.")
async def list_wa_rules():
    return await get_db().whatsapp_rules.find({}, {"_id": 0}) \
        .sort([("rule_key", 1), ("days_min", 1)]).to_list(50)


@router.post("/rules", response_model=WhatsappRule, status_code=201)
async def create_wa_rule(payload: WhatsappRuleIn):
    doc = WhatsappRule(**payload.model_dump())
    await get_db().whatsapp_rules.insert_one(doc.model_dump())
    return doc


@router.patch("/rules/{rule_id}", response_model=WhatsappRule)
async def update_wa_rule(rule_id: str, patch: dict):
    db = get_db()
    allowed = {k: v for k, v in patch.items()
               if k in ("rule_key", "template_name", "template_language",
                        "days_min", "days_max", "media_url", "active", "notes")}
    if not allowed:
        raise HTTPException(400, "Nada que actualizar.")
    allowed["updated_at"] = _iso()
    await db.whatsapp_rules.update_one({"id": rule_id}, {"$set": allowed})
    doc = await db.whatsapp_rules.find_one({"id": rule_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Rule not found")
    return doc


@router.delete("/rules/{rule_id}")
async def delete_wa_rule(rule_id: str):
    r = await get_db().whatsapp_rules.delete_one({"id": rule_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Rule not found")
    return {"ok": True}


async def resolve_rule_for_days_left(days_left: int) -> dict | None:
    """Return the matching active WA rule for a given days_left value."""
    db = get_db()
    async for r in db.whatsapp_rules.find({"active": True}, {"_id": 0}):
        dmin = int(r.get("days_min", 0)); dmax = int(r.get("days_max", 999))
        if dmin <= days_left <= dmax:
            return r
    return None


@router.get("/rules/resolve",
            summary="Debug helper — return which rule applies for days_left.")
async def resolve_rule_endpoint(days_left: int):
    r = await resolve_rule_for_days_left(days_left)
    if not r:
        return {"matched": False, "days_left": days_left}
    return {"matched": True, "days_left": days_left, "rule": r}


# ---------------------------------------------------------------------------
# 24-HOUR CUSTOMER-CARE WINDOW (Meta rule)
# ---------------------------------------------------------------------------
async def window_open(phone: str) -> tuple[bool, dict | None]:
    """Return (is_open, contact_doc). Window opens on every inbound message
    and closes 24h later — Meta requires TEMPLATES for proactive sends after
    that. A template reply from the customer reopens the window."""
    if not phone:
        return False, None
    doc = await get_db().whatsapp_contacts.find_one({"phone": phone}, {"_id": 0})
    if not doc or not doc.get("last_inbound_at"):
        return False, doc
    try:
        last = datetime.fromisoformat(doc["last_inbound_at"].replace("Z", "+00:00"))
    except Exception:
        return False, doc
    delta = datetime.now(timezone.utc) - last
    return (delta.total_seconds() < 24 * 3600), doc


@router.get("/window/{phone}",
            summary="Return the 24h window status for a contact (open/closed + remaining).")
async def window_status(phone: str):
    from datetime import datetime as _dt, timezone as _tz
    is_open, doc = await window_open(phone)
    remaining_seconds = 0
    last_iso = None
    if doc and doc.get("last_inbound_at"):
        try:
            last = _dt.fromisoformat(doc["last_inbound_at"].replace("Z", "+00:00"))
            last_iso = doc["last_inbound_at"]
            elapsed = (_dt.now(_tz.utc) - last).total_seconds()
            remaining_seconds = max(0, int(24 * 3600 - elapsed))
        except Exception:
            pass
    return {
        "phone": phone,
        "window_open": is_open,
        "last_inbound_at": last_iso,
        "remaining_seconds": remaining_seconds,
        "allowed_send_types": ["freeform", "template"] if is_open else ["template"],
        "notes": ("Ventana ABIERTA (24h). Puedes enviar texto libre O template."
                  if is_open else
                  "Ventana CERRADA. Solo templates aprobados por Meta pueden enviarse."),
    }


@router.get("/contacts",
            summary="List known WhatsApp contacts with their window status.")
async def list_contacts(limit: int = 200):
    from datetime import datetime as _dt, timezone as _tz
    docs = await get_db().whatsapp_contacts.find({}, {"_id": 0}) \
        .sort("last_inbound_at", -1).limit(limit).to_list(limit)
    now = _dt.now(_tz.utc)
    for d in docs:
        li = d.get("last_inbound_at")
        d["window_open"] = False
        d["remaining_seconds"] = 0
        if li:
            try:
                last = _dt.fromisoformat(li.replace("Z", "+00:00"))
                elapsed = (now - last).total_seconds()
                d["window_open"] = elapsed < 24 * 3600
                d["remaining_seconds"] = max(0, int(24 * 3600 - elapsed))
            except Exception:
                pass
    return docs


@router.post("/contacts/mark-inbound",
             summary="Manually mark a contact as having replied (opens the 24h window). "
                     "Useful for testing.")
async def mark_inbound(phone: str, body: str = ""):
    await get_db().whatsapp_contacts.update_one(
        {"phone": phone},
        {"$set": {"phone": phone, "last_inbound_at": _iso(),
                  "last_inbound_body": (body or "manual test")[:400]}},
        upsert=True)
    return await window_status(phone)


REQUIRED_TEMPLATE_NAMES = ["reclamo_oficina_whatsaap", "oficina_7_dias", "no__oficina__"]


@router.post("/templates/sync",
             summary="Fetch templates from Chatea Pro and confirm the 3 required "
                     "office-cadence templates exist. Returns per-template presence.")
async def sync_templates():
    chatea = get_chatea()
    if not chatea.configured:
        return {"ok": False, "configured": False,
                "found": [], "missing": REQUIRED_TEMPLATE_NAMES,
                "detail": "CHATEA_PRO_API_KEY no configurada — no se pudo consultar la lista."}
    r = await chatea.list_templates()
    body = r.get("body") or {}
    live: list[str] = []
    if isinstance(body, list):
        live = [x.get("name") or x.get("template_name") or "" for x in body if isinstance(x, dict)]
    elif isinstance(body, dict):
        for k in ("templates", "data", "result"):
            if isinstance(body.get(k), list):
                live = [x.get("name") or x.get("template_name") or "" for x in body[k] if isinstance(x, dict)]
                break
    live = [n for n in live if n]
    found   = [n for n in REQUIRED_TEMPLATE_NAMES if n in live]
    missing = [n for n in REQUIRED_TEMPLATE_NAMES if n not in live]
    return {
        "ok":       len(missing) == 0,
        "configured": True,
        "live_count": len(live),
        "required": REQUIRED_TEMPLATE_NAMES,
        "found":    found,
        "missing":  missing,
        "detail":   ("Las 3 plantillas requeridas están aprobadas en Chatea Pro."
                     if not missing else
                     f"Faltan plantillas por aprobar en Chatea Pro: {', '.join(missing)}."),
    }
