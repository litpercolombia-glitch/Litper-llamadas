# Litper Connect Hub

Production-ready FastAPI **integration hub + public REST API** with a React admin
dashboard, purpose-built for COD e-commerce call-center operations in LATAM
(Colombia / Ecuador / Chile). Orchestrates AI phone calls (VAPI) and WhatsApp
(Chatea Pro) to confirm COD orders sitting at carrier offices — *llamadas a
oficina* — before they get returned.

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
| `CHATEA_PRO_API_KEY` | Chatea Pro (WhatsApp) API key |
| `CHATEA_PRO_BASE_URL` | Base URL of the Chatea Pro API |
| `CHATEA_PRO_SEND_MESSAGE_PATH` | Path for free-text sends (overridable) |
| `CHATEA_PRO_SEND_TEMPLATE_PATH` | Path for template sends |
| `CHATEA_PRO_TEST_PATH` | Path used by `POST /connectors/chatea_pro/test` |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | Reachability probe |
| `SUPABASE_SERVICE_KEY` | Enables server-side writes (leave blank to disable sync) |
| `TRANSLATION_PROVIDER` | `library` (default) or `llm` |
| `LLM_API_KEY` | If provider=`llm`, LLM key (falls back to library if blank) |
| `DEFAULT_TIMEZONE` | Fallback tz for cadence scheduling |
| `SCHEDULER_TICK_MINUTES` | APScheduler cadence dispatcher interval |

**Never commit `.env`. Never expose these values to the frontend.**

---

## Endpoints (all under `/api`)

### Health
- `GET /health` — liveness probe. *No auth.*

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

### WhatsApp (Chatea Pro)
- `POST /whatsapp/send` — free text (`text`) or template (`template_name` +
  `template_params`).
- `GET /whatsapp/messages` — log of everything sent/received.

### Tasks (customer tickets)
- `POST /tasks` — types: `cambio_direccion`, `factura`, `mas_dias`,
  `cambio_oficina`, `otro`.
- `GET /tasks` (filters: `status`, `type`).
- `GET /tasks/{id}` · `PATCH /tasks/{id}` · `DELETE /tasks/{id}`.

### Metrics
- `GET /metrics` — dashboard KPIs (queue by status, attempts 24h, contact
  rate, tasks open, messages sent).

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
  Supabase (from `integration_connectors`).
- `POST /connectors/chatea_pro/test` — pings Chatea Pro and records the result.
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
| `/`           | Metrics dashboard |
| `/queue`      | Queue table with semaphore + filters |
| `/cadence`    | 5-attempt plan timeline + register results |
| `/tasks`      | Customer tickets CRUD |
| `/messages`   | WhatsApp message log |
| `/carriers`   | 12 carriers with rules |
| `/connectors` | Integration status + test buttons |

UI is Spanish (LATAM). Theme: dark tactical Command Center.

---

## Notes on Chatea Pro

Public API documentation for Chatea Pro is not openly discoverable at time of
build. This Hub therefore exposes the client behind a fully configurable
abstraction (`CHATEA_PRO_BASE_URL` + `CHATEA_PRO_SEND_MESSAGE_PATH` +
`CHATEA_PRO_SEND_TEMPLATE_PATH` + `CHATEA_PRO_TEST_PATH`). Correct the endpoint
paths in `.env` — no code changes required. The default payload shape follows
Meta's WhatsApp Cloud API convention.

Use `POST /api/connectors/chatea_pro/test` (or the "Probar conexión" button in
the Conectores page) to ping and confirm your configuration.
