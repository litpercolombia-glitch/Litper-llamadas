# Litper Connect Hub

Production-ready FastAPI **integration hub + public REST API** with a React admin
dashboard, purpose-built for COD e-commerce call-center operations in LATAM
(Colombia / Ecuador / Chile). Orchestrates AI phone calls (VAPI) and WhatsApp
(Chatea Pro) to confirm COD orders sitting at carrier offices — *llamadas a
oficina* — before they get returned.

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
