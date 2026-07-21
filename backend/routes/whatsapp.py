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
