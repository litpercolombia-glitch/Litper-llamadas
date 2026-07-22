# Litper Connect Hub

Production-ready FastAPI **integration hub + public REST API** with a React admin
dashboard, purpose-built for COD e-commerce call-center operations in LATAM
(Colombia / Ecuador / Chile). Orchestrates AI phone calls (VAPI) and WhatsApp
(Chatea Pro) to confirm COD orders sitting at carrier offices — *llamadas a
oficina* — before they get returned.

## Route layout

- `/`               — public **Funnel** landing (Hormozi Grand Slam Offer,
  Grupo VIP capture).
- `/funnel`         — alias to `/`.
- `/login`          — operator login (validates the `PUBLIC_API_KEY`).
- `/app/*`          — internal Command Center (Copilot, Cola, Cadencia, Métricas,
  Tickets, Mensajes+WA rules, Voces, Números, Transportadoras, Novedades,
  Importar, Productos & Promociones, **Prompts**, Leads VIP, **Conexiones**
  con instrucciones paso a paso). Every internal route is gated by the
  operator token stored in `localStorage`.

## Onboarding wizard (BYOK)

New customers land on `/app/onboarding` — a 5-step guided flow (Chatea Pro →
ElevenLabs → Telnyx → Dropi → LLM). Each step has real portal links, paste
fields for the secret, a "Probar" button that hits `/api/config/credentials/{provider}/test`
and a "Guardar & siguiente" that persists via
`PUT /api/config/credentials/{provider}` and advances. Progress bar shows
`n/5 conectado`. Backend endpoint `GET /api/config/onboarding` computes the
state and marks `minimum_ok = chatea_pro && any(llm)` — once true a "Listo
para operar" CTA appears and the wizard hands the operator off to the
Copilot.

## Pricing (BYOK)

Public landing at `/` shows 5 tiers with an explicit **BYOK vs Managed**
banner on every card:

- **Prueba 14 días** — Gratis, hasta 50 pedidos/mes, sin tarjeta.
- **Starter** — $19 USD/mes (~$78.000 COP), hasta 500 pedidos/mes.
- **Growth** — $39 USD/mes (~$160.000 COP), hasta 2.000 pedidos/mes.
- **Agencia · Scale** — $79 USD/mes (~$324.000 COP), pedidos ilimitados + multi-marca.
- **Hecho por ti · Managed** — $149 USD/mes (~$611.000 COP), llaves incluidas.

Prices are placeholders — edit the array in `pages/Funnel.jsx` → `PricingSection`.
Annual toggle applies a ×10 multiplier (2 free months). USD → COP conversion
uses `COP_PER_USD = 4100` (edit inline).

## Multi-tenant credentials (Configuración → Credenciales)

Every organization stores its OWN provider keys — encrypted at rest with
Fernet (`ENCRYPTION_KEY` in `backend/.env`). The frontend never receives
plaintext; only status (`origin: org | env | none`) and a masked hint like
`cp_t…3456`.

Endpoints:
- `GET /api/config/providers` — schema (field names, labels, secret flags,
  matching env vars).
- `GET /api/config/credentials` — per-org non-sensitive status of every
  provider.
- `PUT /api/config/credentials/{provider}` — upsert (empty string = clear).
- `DELETE /api/config/credentials/{provider}` — remove org override (falls
  back to `.env`).
- `POST /api/config/credentials/{provider}/test` — live health-check using
  the effective credentials (org > env > empty).

Multi-tenant hook: an operator can send an `X-Org-Id` header; today every
request defaults to `org_id="default"` so single-tenant behaviour still works.

Providers supported: `chatea_pro`, `telnyx`, `elevenlabs`, `twilio`, `groq`,
`gemini`, `mistral`, `cerebras`, `claude`.

## WhatsApp 24h window (Meta rule)

Meta closes the customer-care window 24h after the last inbound message.
Litper tracks it automatically:

- Chatea webhook updates `whatsapp_contacts.last_inbound_at` on every inbound.
- `GET /api/whatsapp/window/{phone}` returns
  `{window_open, remaining_seconds, allowed_send_types}`.
- The scheduler REFUSES to send free-form messages when the window is
  closed — it forces a Meta-approved TEMPLATE send via Chatea Pro. If no
  matching rule (`reclamo_oficina` 0–3d / `no_oficina` +3d) is configured
  for the days_left value, the attempt is marked `skipped` with
  `wa_window_closed_no_template`.
- `POST /api/whatsapp/contacts/mark-inbound?phone=...&body=...` opens the
  window manually (used for testing).

## Prompts module (Sofía)

`/api/prompts` CRUD + `/api/prompts/resolve` picks the best-matching prompt
using the hierarchy **campaign > product > global** (with country + priority
tiebreaker). `/api/prompts/generate` calls the LLM router (Groq default) with
a meta-prompt that produces a full Sofía script following the official
LIT-LOG-RO flow (verify identity → office claim in {carrier}/{city}/{office_address}
→ urgency {days_left}/{deadline_text} → ask exact pickup date → offer Dropi
extension up to 10 days → close with {guia}). Colombian tone, &lt;60s,
**"antifluido" NEVER "impermeable"**. `/api/prompts/test-voice` returns an
MP3 preview via ElevenLabs. Frontend `/app/prompts` has Pegar and Generar
con IA tabs plus a live variable preview.

Allowed variables: `{customer_first_name} {product_name} {carrier_name}
{city} {office_address} {days_left} {deadline_text} {total_to_pay} {guia}
{promo_name} {promo_price}`.

## Telnyx SIP (primary) · DIDWW / Twilio (secondary)

Env vars: `TELNYX_API_KEY`, `TELNYX_CONNECTION_ID`, `TELNYX_PHONE_NUMBER`,
`TELNYX_SIP_USERNAME`, `TELNYX_SIP_PASSWORD`, `TELNYX_SIP_DOMAIN` (defaults
to `sip.telnyx.com`). `POST /api/numbers/telnyx/register` registers the
Telnyx trunk into ElevenLabs and stores the returned
`elevenlabs_phone_number_id`. `GET /api/numbers/telnyx/config` returns masked
env config for the UI.

## WhatsApp template rules

`/api/whatsapp/templates` proxies Chatea Pro's approved template list.
`/api/whatsapp/rules` CRUD lets the operator map:
* **0–3 días** en oficina → template `reclamo_oficina` (+ imagen guía).
* **+3 días** → template `no_oficina` (urgente + aviso devolución).
The scheduler picks the matching rule via
`resolve_rule_for_days_left(days_left)` and fires
`chatea.send_template(...)` when Chatea Pro is configured.

## Route layout (LEGACY — kept for reference)

Old flat URLs (`/copilot`, `/queue`, `/metrics`, …) redirect to `/app/*`
automatically so existing links keep working.

## Products & Promotions

`/api/products` is a catalog of Litper products. Each product has an
`instrucciones_llamada` string (variables `{customer_name} {product_name}
{promo_name} {promo_price} {tracking} {references}`) and a list of
`Promotion`s. Each promotion has a `sku_pattern` — when an imported order's
SKUs / product names contain the pattern tokens, that promo is auto-matched
and Sofía's script renders the *commercial* name and price instead of the
technical SKU. Seed: "Protector Antifluido Premium + 2 Fundas",
"Colcha + Sábana King 600 hilos".

`POST /api/products/match` returns the best-matching promotion for any
SKU / product name / items list. `GET /api/orders/{id}/prompt-vars` now also
returns `promo_name`, `promo_price`, `promo_bonuses`.

**Never say "impermeable"** — Litper products are "antifluido".

## Funnel & VIP capture

`POST /api/vip-leads` is public (no API key) — the landing page uses it
directly. Optional Chatea Pro welcome WhatsApp is sent to the lead if the
integration is configured. `VIP_GROUP_URL` env var provides the WhatsApp
group invite that appears in the thank-you screen. Admins can list, patch,
delete and export XLSX at `/api/vip-leads` (with API key).

## Design system — Silver Matrix + ZYNEX v2 (neon gradient + 3D)

Base palette is iPhone 17 **Silver** — brushed titanium light silver in day,
dark titanium in night (never pure black). Accent is the ZYNEX gradient:
`cyan #00D8FF → azure #0A84FF → violet #7C5CFF → magenta #C04BFF` — used on
gradient headlines (`.grad-text`), primary CTAs (`.btn-cta-grad`), pill
borders (`.pill-grad`), the 3D wireframe hero, and the mascot ring.

Signature elements from ZYNEX.PRO landing:

- **Top marquee ticker** with stat highlights (`.marquee`).
- **Nav** with gradient logo mark, Funciones · Diagnóstico · Precios · Ingresar.
- **3D wireframe icosahedron** hero centerpiece (`<WireframePolyhedron />`)
  — rotating SVG with cyan→magenta gradient stroke and dual drop-shadow bloom.
- **Constellation dot-network background** (`<Constellation />`) — canvas of
  drifting points connected by fading lines, ~18% sparkling "destellos".
  Visible in night, subtle in day.
- **Glowing 3D mascot** on Copilot & Login (`.mascot-ring` — animated pulse +
  slow spin + gradient halo).
- **Connector chips** (Dropi · Meta Ads · Shopify · WhatsApp · Excel/CSV ·
  Chatea Pro · n8n) as glassy pills that glow on hover.
- **4 suggestion cards** on Copilot home (Semáforo · Vencimientos · Novedades ·
  Recuperación) that navigate to the underlying pages.
- **Skill chips** for "SKILLS — HAZ CLIC PARA USAR".

Toggle day/night via the sun/moon button top-right.

## Dropi import (Excel / CSV) — combo-safe

Real Dropi "Reclamos en Oficina" exports store **one order as multiple rows**:
each product/variation inside a combo/promo appears on its own line but
repeats the customer + tracking + total. Naive row-by-row import triples the
queue count and inflates the recaudo.

The `/api/dropi/*` endpoints (and the "Importar" page in the UI) implement
the correct rules:

1. **Group** rows by `ID` (or `NÚMERO GUIA` if ID is missing) → 1 order per group.
2. **Recaudo** (total_amount) = column **`TOTAL DE LA ORDEN`** taken **once**
   per group. Never summed across rows. `PRECIO PROVEEDOR` is supplier cost
   and is **never** used for recaudo.
3. **Combos**: every row's `PRODUCTO` + `VARIACION` is collapsed into an
   `items[]` list and a display string like
   `"Protector Antifluido (Verde Menta/Doble) + Protector Antifluido (Lila/Semi)"`,
   with `is_combo = true` when `items > 1`.
4. **References**: `SKU`, `PRODUCTO ID`, `VARIACION ID`, `VARIACION` are kept
   per item.
5. **Carrier normalization**: `TRANSPORTADORA` is mapped to the carrier slugs
   in `/api/carriers` (INTERRAPIDISIMO→interrapidisimo, SERVIENTREGA→servientrega, …).
6. **Preview first, import second**: preview shows the *consolidated* view
   (1 row per order, combos flagged) plus a heuristic warning if any
   multi-row order is detected. The user picks which orders to import and can
   override carriers per row.

Endpoints:

- `POST /api/dropi/sheets` (multipart) → list workbook sheet names.
- `POST /api/dropi/preview` (multipart, form field `sheet` optional) → parses
  the file, returns `preview_id`, the column map, the consolidated orders,
  and warnings.
- `POST /api/dropi/import` (JSON `{ preview_id, order_keys?, carrier_overrides?, default_carrier_slug?, country }`)
  → commits the selected orders to `orders` + `call_queue`; dedupes by
  `external_ref` / `tracking_number`.
- `GET /api/orders/{id}/prompt-vars` → renders Sofía's call variables
  (`product_name`, `items_count`, `references`, `is_combo`, …) — for combos
  `product_name` is the full combo string so the AI mentions it naturally.

Tests: `backend/tests/test_dropi_import.py` (4 raw rows → 2 orders, correct
$235,000 vs naive $535,000).

## Stack

- **Backend:** FastAPI (Python 3.11+), Motor (async MongoDB), APScheduler,
  deep-translator, httpx.
- **Frontend:** React 19 + React Router 7 + Tailwind + shadcn/ui + Phosphor
  Icons + Sonner.
- **Storage:** MongoDB (Hub's own orchestration state) + optional Supabase
  Postgres mirror.

---

## Quick start

```bash
# One-shot: seed 12 carriers + demo COD orders across different deadlines
cd backend && python seed.py

# Backend is managed by supervisor:
sudo supervisorctl restart backend
```

Frontend: [https://litper-hub.preview.emergentagent.com](https://litper-hub.preview.emergentagent.com)
OpenAPI docs: `<BACKEND_URL>/docs` and `<BACKEND_URL>/redoc`

---

## Authentication — `X-API-Key`

Every business endpoint (everything except `/api/health` and `/api/webhooks/*`)
requires the header `X-API-Key: <PUBLIC_API_KEY>`.

The key lives in `backend/.env` under `PUBLIC_API_KEY`. Rotate it to invalidate
all clients.

```bash
curl -H "X-API-Key: $PUBLIC_API_KEY" $BACKEND_URL/api/queue
```

---

## Environment (`backend/.env`)

| Variable | Purpose |
|---|---|
| `MONGO_URL`, `DB_NAME` | MongoDB connection (already provisioned) |
| `PUBLIC_API_KEY` | Shared secret for every public endpoint |
| `EMERGENT_LLM_KEY` | Universal LLM key for the Copilot agent (Claude Sonnet 4.6) |
| `CHATEA_PRO_API_KEY` | Chatea Pro (WhatsApp) API key — confirmed working |
| `CHATEA_PRO_BASE_URL` | Default `https://chateapro.app/api` |
| `CHATEA_PRO_*_PATH` | Individual endpoint paths (all overridable) |
| `ELEVENLABS_API_KEY` | ElevenLabs voice-listing API key (leave blank until owner fills) |
| `ELEVENLABS_BASE_URL` | Default `https://api.elevenlabs.io/v1` |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Twilio credentials (leave blank until owner fills) |
| `TWILIO_STATUS_CALLBACK_BASE` | Public HTTPS base URL for Twilio verification callbacks (optional) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` | Optional Postgres mirror |
| `TRANSLATION_PROVIDER` | `library` (default) or `llm` |
| `DEFAULT_TIMEZONE` | Fallback tz for cadence scheduling |
| `SCHEDULER_TICK_MINUTES` | APScheduler cadence dispatcher interval |

**Never commit `.env`. Never expose these values to the frontend.**

---

## Endpoints (all under `/api`)

### Health
- `GET /health` — liveness probe. *No auth.*

### Copilot (Agentic AI Console)
- `GET  /threads` · `POST /threads` · `PATCH /threads/{id}` · `DELETE /threads/{id}`
- `GET  /threads/{id}/messages`
- `POST /agent/run { thread_id?, text, skill_id?, auto_mode?, file_ids? }` —
  runs the agentic loop (LLM plans, calls tools, feeds results back, stops when
  done). Returns `{ thread_id, final_text, steps: [{ assistant_text, tool_calls }] }`.
- `GET  /skills` · `POST /skills` · `PUT /skills/{id}` · `DELETE /skills/{id}` —
  reusable prompts/workflows for the agent. 4 skills are seeded:
  `revisar-cola`, `recuperar-rojos`, `redactar-whatsapp`, `novedades-carrier`.
- `POST /files` (multipart) — upload CSV/XLSX/PDF/image; CSV/XLSX are parsed and
  columns + preview rows stored. `GET /files`, `GET /files/{id}`, `DELETE /files/{id}`.

**Agent tools registered:** `get_queue`, `get_orders`, `get_carriers`,
`get_carrier_novedades`, `schedule_cadence`, `register_attempt_result`,
`send_whatsapp` (real Chatea Pro), `list_whatsapp_templates`, `create_task`,
`list_tasks`, `get_metrics`, `translate`, `list_voices`, `list_numbers`,
`import_orders_from_file`.

LLM: `claude-sonnet-4-6` via the Emergent Universal Key (`EMERGENT_LLM_KEY`).
Falls back to `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` if set. Tool-call protocol
is JSON-in-fenced-`tool`-blocks; results feed back as `tool_result` blocks. Max
6 iterations per user turn.

### Carriers
- `GET /carriers` — 12 Colombian carriers with office-claim rules.
- `GET /carriers/{slug}` — one carrier.
- `GET /carriers/{slug}/office-status?office_arrival_date=YYYY-MM-DD` — computes
  `days_left` + semaphore (`rojo`/`amarillo`/`verde`/`gris`) for a given
  arrival date.

### Orders
- `POST /orders` — create one order and auto-enqueue it in the call queue.
- `POST /orders/bulk` — up to 500 orders per call.
- `GET /orders` (filters: `status`, `carrier_slug`, `skip`, `limit`).
- `GET /orders/{order_id}`.

### Queue
- `GET /queue` (filters: `status`, `semaphore`, `carrier_slug`, `limit`) —
  returns enriched queue items with **`days_left` + semaphore**.
- `GET /queue/{queue_id}`.

### Cadence (5-attempt plan)
- `POST /calls/schedule` — build/rebuild the plan for a queue item.
- `GET /calls/schedule/{queue_id}` — read the current plan.
- `POST /calls/attempt-result` — register the outcome of an attempt:
  `confirmado` / `extension` / `rechaza` / `ya_recogio` / `no_contesta` /
  `numero_incorrecto`. Automatically stops the cadence when a resolution is
  reached, escalates after 5 exhausted attempts, and triggers a WhatsApp
  fallback after 3 consecutive `no_contesta` results.

**Cadence rules (encoded in `cadence.py`):**
- Windows: `manana` 09-11 · `mediodia` 12-14 · `tarde` 15-18 · `noche` 18-20.
- Never two attempts in the same window back-to-back.
- Respect `office_claim_max_days`:
  - `1 day` → **compress** the whole cadence into that single day.
  - `2 days` → spread over 2 days.
  - `3+ days` (or `None`) → spread over 3 days.
- Attempts 1-4 = `call`. Attempt 5 = `whatsapp` (final).
- Skips Colombian holidays.

### WhatsApp (Chatea Pro — real endpoints wired)
- `POST /whatsapp/send` — free text (`text`) or template (`template_name` +
  `template_params`). Under the hood:
    1. `GET /subscriber/get-info?phone_number=…` → look up subscriber
    2. `POST /subscriber/create` if not found
    3. `POST /subscriber/send-text` or `POST /subscriber/send-whatsapp-template`
- `GET /whatsapp/messages` — log of everything sent/received.
- `POST /connectors/chatea_pro/test` — pings `GET /me` and stores the workspace
  name (visible in the Conectores UI).

Base URL and every path are env-overridable in `backend/.env` (`CHATEA_PRO_*`).

### Tasks (customer tickets)
- `POST /tasks` — types: `cambio_direccion`, `factura`, `mas_dias`,
  `cambio_oficina`, `otro`.
- `GET /tasks` (filters: `status`, `type`).
- `GET /tasks/{id}` · `PATCH /tasks/{id}` · `DELETE /tasks/{id}`.

### Metrics
- `GET /metrics` — dashboard KPIs (queue by status, attempts 24h, contact
  rate, tasks open, messages sent).

### Voices (ElevenLabs voice picker)
- `GET /voices` · `POST /voices` · `PUT /voices/{id}` · `DELETE /voices/{id}` —
  register up to **6 voice profiles** (`name`, `elevenlabs_voice_id`,
  `language`, `country`, `is_default`).
- `GET /voices/default/{country}` — the default voice for a country (falls back
  to any available).
- `GET /voices/elevenlabs/available` — passthrough of the ElevenLabs `/voices`
  endpoint (when `ELEVENLABS_API_KEY` is set); frontend uses this to render a
  dropdown of the account's voices.

### Numbers (Twilio Verified Caller IDs)
- `POST /numbers/verify/start { phone_number, country, friendly_name? }` —
  calls Twilio `POST /OutgoingCallerIds.json`; returns the 6-digit
  `validation_code` to show to the user. Twilio then places a verification call.
- `POST /numbers/verify/confirm { phone_number }` — polls Twilio's list and
  marks the local record as `verified` when it appears.
- `GET /numbers` — local list of connected caller IDs.
- `POST /numbers/import` — mark an already-verified Twilio number as connected.
- `GET /numbers/twilio/verified` — passthrough list of ALL verified caller IDs
  in the Twilio account.

### Carriers · Novedades (status → action reference)
- `GET /carriers/novedades?carrier=&categoria=` — reference table. Categories:
  `RECLAMO_EN_OFICINA`, `DEVOLUCION`, `NOVEDAD`, `TRANSITO`, `ENTREGADO`,
  `OTRO`. 18 rows seeded (owner has the full 426-row dataset to load later).

### Webhooks (no `X-API-Key` — providers can't inject custom headers)
- `POST /webhooks/chatea` — inbound WhatsApp events. Auto-classifies replies
  (`recogí`, `confirmo`, `cancelar`, …) and updates the matching queue item.
- `POST /webhooks/vapi` — VAPI (or any AI phone) call-ended webhook. Registers
  the outcome as an attempt result.

### Translation
- `POST /translate` — `{text, source, target}` where `target ∈ {es, en, pt}`.
  Backed by `deep-translator` (library) — swap to LLM via
  `TRANSLATION_PROVIDER=llm`.

### Connectors
- `GET /connectors` — status of Chatea Pro / Dropi / WhatsApp Business /
  Supabase / ElevenLabs / Twilio (from `integration_connectors`).
- `POST /connectors/chatea_pro/test` — GET `/me` (validates token, extracts
  workspace name).
- `POST /connectors/elevenlabs/test` — lists voices to verify the key.
- `POST /connectors/twilio/test` — lists verified caller IDs to verify creds.
- `POST /connectors/supabase/test` — reachability probe.

---

## Cadence example (Envía vs Servientrega)

**Envía** — `office_claim_max_days = 1` → compressed same-day cadence:
```
#1 [call]     manana   09:00 local
#2 [call]     mediodia 12:00 local
#3 [call]     tarde    15:00 local
#4 [call]     noche    18:00 local
#5 [whatsapp] mediodia 12:30 local (final fallback)
```

**Servientrega** — `office_claim_max_days = 8` → spread over 3 days:
```
Day 0 #1 [call] manana   · #2 [call] tarde
Day 1 #3 [call] mediodia · #4 [call] noche
Day 2 #5 [whatsapp] tarde (final fallback)
```

Holidays are automatically bumped to the next business day.

---

## Semaphore

Computed per queue item using `days_left` vs `office_claim_max_days`:

| Semaphore | Rule |
|---|---|
| `rojo`     | `days_left ≤ 1` |
| `amarillo` | `days_left ≤ office_claim_max_days / 2` |
| `verde`    | otherwise |
| `gris`     | carrier has no office-claim option |

---

## Supabase sync (optional)

When `SUPABASE_URL` + a key are set, every insert/update mirrors to the
Postgres tables (`orders`, `call_queue`, `customer_tasks`, `message_log`,
`carriers`, `integration_connectors`). If `SUPABASE_SERVICE_KEY` is blank
(default), sync silently no-ops so the Hub still works purely on MongoDB.

---

## Frontend routes

| Route | Page |
|---|---|
| `/`           | **Litper Copilot** — Marcus, the agentic AI console (chat + tool calls) |
| `/skills`     | Habilidades — CRUD for reusable agent workflows |
| `/metrics`    | Metrics dashboard |
| `/queue`      | Queue table with semaphore + filters |
| `/cadence`    | 5-attempt plan timeline + register results |
| `/tasks`      | Customer tickets CRUD |
| `/messages`   | WhatsApp message log |
| `/voices`     | ElevenLabs voice profiles (max 6) |
| `/numbers`    | Twilio verified caller IDs (self-service) |
| `/carriers`   | 12 carriers with rules |
| `/novedades`  | Carrier-status → action reference table |
| `/connectors` | Integration status + test buttons |

UI is Spanish (LATAM). Theme: dark tactical Command Center.

---

## Notes on Chatea Pro

Confirmed real endpoints (env-overridable):
```
GET  /me                                → token + workspace probe
GET  /subscriber/get-info?phone_number  → find subscriber
POST /subscriber/create                 → create if not found
POST /subscriber/send-text              → free-text WhatsApp
POST /subscriber/send-whatsapp-template → template WhatsApp
POST /whatsapp-template/list            → list templates
```

Auth: `Authorization: Bearer $CHATEA_PRO_API_KEY`.

Use `POST /api/connectors/chatea_pro/test` (or the "Probar conexión" button in
Conectores) to validate the token — it returns the workspace name from `/me`.
