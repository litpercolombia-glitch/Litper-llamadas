"""Pydantic models for Litper Connect Hub."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


# ---------- ORDER ----------
class Product(BaseModel):
    name: str
    qty: int = 1
    price: float = 0


class OrderIn(BaseModel):
    external_ref: Optional[str] = Field(None, description="External order ID (Dropi/Shopify)")
    customer_name: str
    customer_phone: str = Field(..., description="E.164 or local. Used for WhatsApp/AI call.")
    customer_email: Optional[str] = None
    address: Optional[str] = ""
    city: Optional[str] = ""
    country: Literal["CO", "EC", "CL"] = "CO"
    total_amount: float = 0
    currency: str = "COP"
    carrier_slug: str = Field(..., description="Slug of the carrier (see /carriers)")
    tracking_number: Optional[str] = None
    products: list[Product] = []
    office_arrival_date: Optional[str] = Field(
        None, description="ISO date the parcel arrived at the office. Defaults to today.")
    metadata: dict[str, Any] = {}


class Order(OrderIn):
    id: str = Field(default_factory=_uid)
    status: Literal["imported", "in_queue", "resolved", "escalated"] = "imported"
    created_at: str = Field(default_factory=_now_iso)


class OrderBulkIn(BaseModel):
    orders: list[OrderIn]


# ---------- QUEUE ----------
class QueueItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=_uid)
    order_id: str
    carrier_slug: str
    office_arrival_date: str  # ISO date
    office_claim_max_days: Optional[int] = None
    country: str = "CO"
    status: Literal[
        "pending", "in_progress", "confirmado", "rechazado",
        "ya_recogio", "extension", "escalado", "detenido"
    ] = "pending"
    current_attempt: int = 0
    next_attempt_at: Optional[str] = None
    updated_at: str = Field(default_factory=_now_iso)
    created_at: str = Field(default_factory=_now_iso)


class QueueItemPublic(QueueItem):
    days_left: Optional[int] = None
    semaphore: Literal["rojo", "amarillo", "verde", "gris"] = "gris"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    carrier_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    tracking_number: Optional[str] = None


# ---------- CADENCE ----------
class Attempt(BaseModel):
    attempt_number: int
    channel: Literal["call", "whatsapp"]
    window: Literal["manana", "mediodia", "tarde", "noche"]
    scheduled_at: str
    status: Literal["pending", "dispatched", "done", "skipped"] = "pending"
    result: Optional[str] = None
    executed_at: Optional[str] = None
    notes: Optional[str] = None


class CallSchedule(BaseModel):
    id: str = Field(default_factory=_uid)
    queue_id: str
    attempts: list[Attempt]
    created_at: str = Field(default_factory=_now_iso)


class ScheduleRequest(BaseModel):
    queue_id: str


class AttemptResult(BaseModel):
    queue_id: str
    attempt_number: int
    result: Literal[
        "confirmado", "extension", "rechaza",
        "ya_recogio", "no_contesta", "numero_incorrecto"
    ]
    notes: Optional[str] = None


# ---------- WHATSAPP / MESSAGE ----------
class WhatsAppSend(BaseModel):
    phone: str
    text: Optional[str] = None
    template_name: Optional[str] = None
    template_params: dict[str, Any] = {}
    queue_id: Optional[str] = None
    order_id: Optional[str] = None


class Message(BaseModel):
    id: str = Field(default_factory=_uid)
    order_id: Optional[str] = None
    queue_id: Optional[str] = None
    direction: Literal["outbound", "inbound"] = "outbound"
    channel: Literal["whatsapp", "call"] = "whatsapp"
    phone: str
    template_name: Optional[str] = None
    body: str = ""
    provider: str = "chatea_pro"
    provider_message_id: Optional[str] = None
    status: Literal["sent", "delivered", "failed", "received"] = "sent"
    error: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


# ---------- TASKS ----------
TASK_TYPES = ["cambio_direccion", "factura", "mas_dias", "cambio_oficina", "otro"]


class TaskIn(BaseModel):
    order_id: Optional[str] = None
    queue_id: Optional[str] = None
    type: Literal["cambio_direccion", "factura", "mas_dias", "cambio_oficina", "otro"] = "otro"
    description: str
    source: Literal["customer", "agent", "ai", "webhook"] = "agent"
    assigned_to: Optional[str] = None
    due_at: Optional[str] = None


class Task(TaskIn):
    id: str = Field(default_factory=_uid)
    status: Literal["open", "in_progress", "resolved", "closed"] = "open"
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class TaskUpdate(BaseModel):
    status: Optional[Literal["open", "in_progress", "resolved", "closed"]] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_at: Optional[str] = None
    type: Optional[Literal["cambio_direccion", "factura", "mas_dias", "cambio_oficina", "otro"]] = None


# ---------- CARRIER ----------
class Carrier(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    slug: str
    coverage_points: int
    max_recaudo_cop: int
    office_claim_allowed: bool
    office_claim_max_days: Optional[int]
    max_delivery_attempts: int
    accepts_nequi_daviplata: bool
    notes: str = ""


# ---------- CONNECTORS ----------
class Connector(BaseModel):
    id: str = Field(default_factory=_uid)
    key: str
    name: str
    status: Literal["connected", "disconnected", "error", "unconfigured"] = "unconfigured"
    last_checked_at: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = {}


# ---------- WEBHOOKS ----------
class VapiWebhook(BaseModel):
    queue_id: str
    attempt_number: int
    result: str  # one of the AttemptResult.result values
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None


class ChateaWebhook(BaseModel):
    phone: str
    text: Optional[str] = None
    template_name: Optional[str] = None
    provider_message_id: Optional[str] = None
    raw: dict[str, Any] = {}


# ---------- TRANSLATION ----------
class TranslateRequest(BaseModel):
    text: str
    source: str = "auto"
    target: Literal["es", "en", "pt"] = "es"


class TranslateResponse(BaseModel):
    text: str
    source: str
    target: str
    provider: str
