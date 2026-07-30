"""POST /api/feedback — capture "sugerir función" from the floating button.

Persistence: always saved to `db.feedback` so we never lose a suggestion.
Email:      best-effort via SMTP if `SMTP_HOST` is configured. If not, we
            leave `emailed=false` and the record is still stored. The dest
            address is `FEEDBACK_EMAIL` (defaults to zynexproai@gmail.com).
"""
from __future__ import annotations
import os
import ssl
import smtplib
import uuid
import logging
from email.message import EmailMessage
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from db import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])
log = logging.getLogger("feedback")

FEEDBACK_EMAIL = os.environ.get("FEEDBACK_EMAIL", "zynexproai@gmail.com")


class FeedbackIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=140)
    description: str = Field(..., min_length=1, max_length=4000)
    email: EmailStr | None = None
    source: str = "app"


def _iso() -> str: return datetime.now(timezone.utc).isoformat()


def _try_send_email(subject: str, body: str, reply_to: str | None) -> tuple[bool, str | None]:
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        return False, "SMTP_HOST no configurado"
    port      = int(os.environ.get("SMTP_PORT", "587"))
    user      = os.environ.get("SMTP_USER", "").strip()
    password  = os.environ.get("SMTP_PASSWORD", "").strip()
    starttls  = os.environ.get("SMTP_STARTTLS", "true").lower() != "false"
    from_addr = os.environ.get("SMTP_FROM", user or "no-reply@zynex.app")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = FEEDBACK_EMAIL
    if reply_to: msg["Reply-To"] = reply_to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            if starttls:
                s.starttls(context=ssl.create_default_context())
            if user and password:
                s.login(user, password)
            s.send_message(msg)
        return True, None
    except Exception as e:
        log.warning("feedback SMTP send failed: %s", e)
        return False, str(e)


@router.post("", summary="Capture a feature request / bug report / suggestion.")
async def submit_feedback(payload: FeedbackIn, request: Request):
    # Best-effort org/user attribution from the JWT cookie or X-Org-Id header.
    org_id = request.headers.get("X-Org-Id", "").strip() or None
    user_email = None
    try:
        from routes.auth import _decode, COOKIE_NAME
        tok = request.cookies.get(COOKIE_NAME)
        claims = _decode(tok) if tok else None
        if claims:
            org_id = org_id or claims.get("org")
            user_email = claims.get("email")
    except Exception:
        pass

    fid = uuid.uuid4().hex[:12]
    reply_to = str(payload.email) if payload.email else user_email
    body = (
        f"[Zynex OS] Nueva sugerencia\n"
        f"----------------------------\n"
        f"ID:      {fid}\n"
        f"Título:  {payload.title}\n"
        f"Origen:  {payload.source}\n"
        f"Org:     {org_id or '—'}\n"
        f"Reply-to:{reply_to or '—'}\n"
        f"Fecha:   {_iso()}\n"
        f"\n"
        f"Descripción:\n{payload.description}\n"
    )
    emailed, error = _try_send_email(
        subject=f"[Zynex] Sugerencia: {payload.title[:80]}",
        body=body,
        reply_to=reply_to,
    )

    doc = {
        "id":          fid,
        "title":       payload.title.strip(),
        "description": payload.description.strip(),
        "email":       reply_to,
        "org_id":      org_id,
        "source":      payload.source,
        "destination": FEEDBACK_EMAIL,
        "emailed":     emailed,
        "email_error": error,
        "created_at":  _iso(),
    }
    await get_db().feedback.insert_one(doc)
    return {"ok": True, "id": fid, "emailed": emailed,
            "message": "¡Gracias! Recibimos tu idea." }


@router.get("/count", summary="Simple counter (used to show operator karma later).")
async def feedback_count():
    return {"total": await get_db().feedback.count_documents({})}
