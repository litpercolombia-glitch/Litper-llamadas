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


class OrderItem(BaseModel):
    product: str = ""
    variation: str = ""
    sku: str = ""
    product_id: str = ""
    variation_id: str = ""
    qty: int = 1


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
    # Dropi combo/promo support: many rows per order collapse into one order
    # with a list of items. products_display renders it e.g.
    #   "Protector Antifluido (Verde Menta/Doble) + Protector Antifluido (Lila/Semi)"
    items: list[OrderItem] = []
    items_count: int = 0
    is_combo: bool = False
    products_display: str = ""
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
    # Populated by webhooks (Twilio + ElevenLabs)
    call_sid: Optional[str] = None
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None


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


# ---------- VOICE PROFILES ----------
class VoiceProfileIn(BaseModel):
    name: str = Field(..., description="Nombre corto, ej. 'Sofía CO'.")
    elevenlabs_voice_id: str
    language: Literal["es-CO", "es-EC", "es-CL", "es-MX", "es-AR", "es", "en", "pt"] = "es-CO"
    country: Literal["CO", "EC", "CL", "OTHER"] = "CO"
    is_default: bool = False
    description: str = ""


class VoiceProfile(VoiceProfileIn):
    id: str = Field(default_factory=_uid)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class VoiceProfileUpdate(BaseModel):
    name: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    language: Optional[str] = None
    country: Optional[Literal["CO", "EC", "CL", "OTHER"]] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


# ---------- CONNECTED NUMBERS (Twilio verified caller IDs) ----------
class NumberVerifyStart(BaseModel):
    phone_number: str = Field(..., description="Número en formato E.164, ej. +573001234567")
    country: Literal["CO", "EC", "CL", "OTHER"] = "CO"
    friendly_name: Optional[str] = None


class NumberVerifyConfirm(BaseModel):
    phone_number: str


class NumberImport(BaseModel):
    phone_number: str
    twilio_sid: Optional[str] = None
    friendly_name: Optional[str] = None
    country: Literal["CO", "EC", "CL", "OTHER"] = "CO"


class ConnectedNumber(BaseModel):
    id: str = Field(default_factory=_uid)
    phone_number: str
    friendly_name: Optional[str] = None
    country: str = "CO"
    provider: Literal["twilio", "manual", "didww_sip"] = "twilio"
    status: Literal["pending", "verified", "failed", "imported", "sip_registered"] = "pending"
    validation_code: Optional[str] = None
    call_sid: Optional[str] = None
    twilio_sid: Optional[str] = None
    elevenlabs_phone_number_id: Optional[str] = None
    sip_domain: Optional[str] = None
    caller_id_number: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class SipConnectionIn(BaseModel):
    sip_username: str
    sip_password: str
    sip_domain: str
    outbound_trunk_id: Optional[str] = None
    caller_id_number: str = Field(..., description="E.164 (ej +573001234567)")
    friendly_name: Optional[str] = None


class PlaceCallIn(BaseModel):
    queue_id: str
    to_number: Optional[str] = Field(None, description="Sólo para llamada de prueba (override).")


# ---------- NOVEDADES (carrier status reference) ----------
class Novedad(BaseModel):
    id: str = Field(default_factory=_uid)
    carrier: str
    estatus_carrier: str
    estatus_dropi: Optional[str] = None
    significado: str
    accion: str
    categoria: Literal[
        "RECLAMO_EN_OFICINA", "DEVOLUCION", "NOVEDAD",
        "TRANSITO", "ENTREGADO", "OTRO"
    ] = "OTRO"


# ---------- COPILOT / AGENT ----------
class ChatThread(BaseModel):
    id: str = Field(default_factory=_uid)
    title: str = "Nueva conversación"
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    skill_id: Optional[str] = None
    auto_mode: bool = False


class ChatMessage(BaseModel):
    id: str = Field(default_factory=_uid)
    thread_id: str
    role: Literal["user", "assistant", "tool", "system"]
    content: str = ""
    tool_calls: list[dict[str, Any]] = []
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    attachments: list[dict[str, Any]] = []
    created_at: str = Field(default_factory=_now_iso)


class SendMessageIn(BaseModel):
    thread_id: Optional[str] = None
    text: str
    skill_id: Optional[str] = None
    auto_mode: bool = False
    file_ids: list[str] = []
    model_override: Optional[str] = None


class SkillIn(BaseModel):
    name: str
    trigger: str = Field(..., description="Comando corto, ej. 'revisar-cola'.")
    description: str = ""
    instructions: str = Field(..., description="Prompt/instrucciones que se inyectan al agente.")
    steps: list[str] = []


class Skill(SkillIn):
    id: str = Field(default_factory=_uid)
    is_seed: bool = False
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class UploadedFile(BaseModel):
    id: str = Field(default_factory=_uid)
    filename: str
    content_type: str
    size: int
    kind: Literal["csv", "xlsx", "pdf", "image", "other"] = "other"
    rows_preview: list[dict[str, Any]] = []
    columns: list[str] = []
    row_count: int = 0
    thread_id: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


# ---------- PRODUCTS & PROMOTIONS ----------
class Promotion(BaseModel):
    id: str = Field(default_factory=_uid)
    sku_pattern: str = Field(..., description="SKU sustring/regex/keywords, ej. 'PROTECTOR MAS FUNDAS'")
    nombre_comercial: str = Field(..., description="Nombre bonito de la oferta que dirá Sofía")
    descripcion: str = ""
    precio_lista: float = 0
    precio_promo: float = 0
    bonos: list[str] = []
    activa: bool = True


class ProductIn(BaseModel):
    nombre: str = Field(..., description="Nombre técnico del producto")
    slug: Optional[str] = None
    descripcion: str = ""
    instrucciones_llamada: str = Field(
        "", description="Instrucciones para el prompt de llamada (variables permitidas: "
                       "{customer_name} {product_name} {tracking} {city} {references}).")
    promotions: list[Promotion] = []
    activo: bool = True


class ProductCatalog(ProductIn):
    id: str = Field(default_factory=_uid)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class ProductUpdate(BaseModel):
    nombre: Optional[str] = None
    slug: Optional[str] = None
    descripcion: Optional[str] = None
    instrucciones_llamada: Optional[str] = None
    promotions: Optional[list[Promotion]] = None
    activo: Optional[bool] = None


# ---------- VIP LEADS (funnel) ----------
class VipLeadIn(BaseModel):
    nombre: str
    whatsapp: str = Field(..., description="Ej. +573001234567")
    pais: Literal["CO", "EC", "CL", "MX", "PE", "AR", "OTRO"] = "CO"
    pedidos_semana: Optional[str] = Field(None, description="Rango: <50, 50-200, 200-500, 500+")
    email: Optional[str] = None
    utm: dict[str, Any] = {}


class VipLead(VipLeadIn):
    id: str = Field(default_factory=_uid)
    created_at: str = Field(default_factory=_now_iso)
    status: Literal["nuevo", "contactado", "unido", "descartado"] = "nuevo"
    welcome_sent: bool = False
    welcome_error: Optional[str] = None


# ---------- PROMPTS MODULE ----------
class PromptIn(BaseModel):
    name: str
    scope: Literal["global", "product", "campaign"] = "global"
    country: Optional[Literal["CO", "EC", "CL"]] = None
    product_id: Optional[str] = None
    campaign_key: Optional[str] = Field(
        None, description="Free-form key used to match a campaign (e.g. carrier slug or shopify campaign)")
    system_prompt: str = Field(..., description="Sofía's full system prompt (Colombian, <60s, antifluido).")
    first_message: str = Field("", description="Optional opening line.")
    variables: list[str] = Field(default_factory=list,
                                 description="Whitelist of allowed variables; UI-only reference.")
    voice_id: Optional[str] = None
    active: bool = True
    priority: int = Field(0, description="Higher wins ties within the same scope.")


class Prompt(PromptIn):
    id: str = Field(default_factory=_uid)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    scope: Optional[Literal["global", "product", "campaign"]] = None
    country: Optional[Literal["CO", "EC", "CL"]] = None
    product_id: Optional[str] = None
    campaign_key: Optional[str] = None
    system_prompt: Optional[str] = None
    first_message: Optional[str] = None
    variables: Optional[list[str]] = None
    voice_id: Optional[str] = None
    active: Optional[bool] = None
    priority: Optional[int] = None


class PromptGenerateIn(BaseModel):
    product: str
    beneficios: str = ""
    objeciones: str = ""
    transportadora: str = ""
    tono: str = Field("colombiano cálido y directo",
                      description="Adjective/style for Sofía's tone.")
    country: Literal["CO", "EC", "CL"] = "CO"
    model: Optional[str] = None  # forwarded to the LLM router


class PromptResolveIn(BaseModel):
    order_id: Optional[str] = None
    product_id: Optional[str] = None
    country: Optional[Literal["CO", "EC", "CL"]] = None
    carrier_slug: Optional[str] = None


# ---------- WHATSAPP TEMPLATE RULES ----------
class WhatsappRuleIn(BaseModel):
    rule_key: Literal["reclamo_oficina", "recordatorio_7d", "no_oficina"] = "reclamo_oficina"
    template_name: str = Field(..., description="Chatea Pro template name (as returned by /whatsapp-template/list)")
    template_language: str = "es"
    days_min: int = 0
    days_max: int = 3
    media_url: Optional[str] = Field(None, description="Optional image (guía) to attach.")
    active: bool = True
    notes: str = ""


class WhatsappRule(WhatsappRuleIn):
    id: str = Field(default_factory=_uid)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


# ---------- TELNYX ----------
class TelnyxRegisterIn(BaseModel):
    telnyx_phone_number: Optional[str] = None
    telnyx_connection_id: Optional[str] = None
    friendly_name: Optional[str] = None
