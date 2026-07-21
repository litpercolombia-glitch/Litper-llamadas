# Litper Connect Hub — PRD

## Original Problem Statement
Production-ready FastAPI backend (integration hub + public API) + React admin dashboard
for a COD e-commerce call-center operation in LATAM (Colombia / Ecuador / Chile).
Orchestrates AI phone calls (VAPI) + WhatsApp (Chatea Pro) to confirm COD orders
sitting at carrier offices ("llamadas a oficina") before they get returned.

Stack: FastAPI + React + MongoDB (Hub's own state). Optional mirror to Supabase Postgres.
Auto-generated OpenAPI at /docs and /redoc. All business endpoints protected by
`X-API-Key`.

## User Personas
- **Call-center Operator** — logs into the dashboard, monitors queue, registers call outcomes.
- **Ops Manager** — watches the metrics dashboard, resolves customer tickets, tests integrations.
- **External AI Agent (Claude)** — consumes the REST API via `X-API-Key` to pick calls, register results, send WhatsApp fallbacks.

## Core Requirements (static)
- REST API with OpenAPI docs + `X-API-Key` header auth on business endpoints.
- Cadence engine: up to 5 attempts across up to 3 days, rotating windows
  (manana/mediodia/tarde/noche), no back-to-back same-window, respecting the
  carrier's `office_claim_max_days` (1-day → compressed same day; 8-day → spread;
  none → default 3-day). Skip Colombian holidays.
- Attempts 1-4 = call. Attempt 5 = WhatsApp. Extra WhatsApp fallback after 3
  consecutive `no_contesta`. Stop cadence on `rechaza` / `numero_incorrecto`.
  Escalate after 5 exhausted attempts.
- Chatea Pro WhatsApp connector with fully configurable URL/paths via env,
  test-connection endpoint, and message log.
- 12 Colombian carriers seeded with office-claim rules + semaphore
  (`rojo`/`amarillo`/`verde`/`gris`).
- Endpoints: orders (single + bulk), queue with semaphore + days_left, cadence
  schedule + attempt-result, whatsapp send, tasks CRUD, metrics, webhooks
  (Chatea + VAPI), translate (es/en/pt), health, connectors.
- Optional Supabase sync (env-driven, no-op when SUPABASE_SERVICE_KEY blank).
- React dashboard in Spanish: Metrics · Cola · Cadencia · Tickets · Mensajes ·
  Transportadoras · Conectores.

## Implementation Status (2026-02-21 · v1.0)

### Backend — DONE
- FastAPI app (`server.py`) with lifespan, CORS, auto-seed 12 carriers +
  4 connectors on boot, Mongo indexes.
- APScheduler `AsyncIOScheduler` dispatcher (`scheduler.py`) — ticks every 2 min,
  auto-sends WhatsApp attempts, marks call attempts as `dispatched`.
- All 11 route modules under `/api`: health, carriers, orders, queue, cadence,
  whatsapp, tasks, metrics, webhooks (Chatea+VAPI), translate, connectors.
- Chatea Pro client with configurable base URL / paths + connection test.
- Cadence engine (`cadence.py`) with compressed/spread logic + holiday skip.
- Translation provider abstraction (library default; LLM stub swappable via env).
- Optional Supabase mirror via PostgREST.
- Seed script (`seed.py`) — 12 carriers + 7 demo orders across different
  deadlines (Envía 1-day, Servientrega 8-day, Interrapidísimo 4-day,
  Coordinadora 8-day, TCC 3-day, 99-minutos no-office, Wiilog 2-day).

### Frontend — DONE
- React 19 + React Router 7 + Tailwind + shadcn/ui + Phosphor Icons + Sonner.
- Dark tactical Command Center theme (Work Sans + IBM Plex Sans/Mono fonts).
- 7 pages: Métricas, Cola, Cadencia, Tickets, Mensajes, Transportadoras,
  Conectores. All Spanish, all with `data-testid` on interactive elements.
- Queue table with semaphore chips, filters, search, prices formatted in COP.
- Cadence timeline view with per-attempt result buttons (6 outcomes).
- Tasks CRUD with type/status filters + create/resolve modal.
- Messages page with sent/received distinction, send-new dialog.
- Connectors page with "Probar conexión" buttons for Chatea Pro & Supabase.
- Carriers page listing all 12 with rules + inline semaphore for reclamo days.

### Testing — 25/25 backend tests passing (iteration 1)
- Report: `/app/test_reports/iteration_1.json`

## Prioritized Backlog

### P1 — Nice-to-have
- Multi-tenant support (org_id already present in Supabase schema).
- Dropi connector — import orders directly from Dropi fulfillment.
- VAPI outbound-call trigger (currently only inbound webhook is wired; the
  external AI orchestrator dials via VAPI itself).
- Cadence edge-case: when both day-0 and day-1 land on the same holiday, bump
  each offset independently so spread plans always yield distinct dates.

### P2 — Later
- Per-user auth on the dashboard (currently a shared trusted API key).
- Chart visualisations on Metrics page (Recharts is already installed).
- CSV export of queue + tickets.
- LLM-based translation provider fully implemented (currently stubs → library).
- Signature verification on webhooks.

## Deferred
- Full multi-tenancy → depends on Supabase org_id propagation.
- Push notifications for agents.
