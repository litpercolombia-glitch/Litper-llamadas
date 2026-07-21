# Litper Connect Hub — PRD

## Original Problem Statement
Production-ready FastAPI integration hub + public REST API with a React admin
dashboard for a COD e-commerce call-center operation in LATAM (Colombia / Ecuador
/ Chile). Orchestrates AI phone calls + WhatsApp to confirm COD orders sitting
at carrier offices ("llamadas a oficina") before they get returned.

## User Personas
- **Call-center Operator** — monitors queue, registers call outcomes.
- **Ops Manager** — watches metrics, resolves customer tickets, tests integrations.
- **Copilot User** — chats with Marcus (the AI agent) to run operations autonomously.
- **External AI Agent (Claude)** — consumes the REST API via `X-API-Key`.

## Core Requirements (static)
Same as v1.0 plus:
- Real Chatea Pro API wired (confirmed endpoints: /me, /subscriber/get-info,
  /subscriber/create, /subscriber/send-text, /subscriber/send-whatsapp-template).
- ElevenLabs voice-picker with per-country default (max 6 voices).
- Twilio Verified Caller IDs (self-service verification flow).
- Novedades reference table (carrier status → action).
- **Agentic AI Console ("Marcus") as landing page**, with tool-calling loop,
  15+ tools mapped to the Hub's own endpoints, seeded skills, and file upload
  → bulk import.

## Implementation Status

### v1.3 (2026-02-21) — Silver Matrix + Real ElevenLabs + Full Metrics
- **ElevenLabs wired (real key)** — 6 voices auto-seeded on boot (Sofía CO,
  Sofía EC, Voz 3-6). New `POST /voices/preview` synthesizes TTS via
  `POST /text-to-speech/{voice_id}` and returns `audio/mpeg`. Voces page has a
  "Probar voz" button that plays the sample line. `GET /voices/elevenlabs/available`
  now returns 38 real voices from the account.
- **Full KPI dashboard** at `/metrics`: 5 groups (NORTE / Embudo / WhatsApp /
  Operación / Costos) with target chips + traffic-light coloring, Recharts
  visualisations, funnel, semaphore bars, cost stacked bars, 14-day trend
  lines for Recovery Rate and CPR. Filters: date range, country, carrier.
  Cost model env-driven (`TWILIO_COST_PER_MIN`, `ELEVENLABS_COST_PER_MIN`,
  `WHATSAPP_COST_PER_MSG`, `LLM_COST_PER_1K`, `USD_TO_COP`, `RTO_BASELINE_PCT`,
  `COD_MARGIN_PCT`).
- **"Silver Matrix" full-app redesign**: iPhone 17 Pro Max silver/titanium
  palette (light + dark modes), day/night toggle (persisted in localStorage),
  glassmorphism cards with metallic borders + dual 3D shadows, KPI card tilt
  animation on hover (rotateX/rotateY perspective:800px), silver/cyan Matrix
  rain canvas background, Inter + IBM Plex Mono fonts, rounded 10-16px, all
  applied globally via CSS variable overrides — no per-component changes.

### v1.0 (2026-02-21) — DONE
- FastAPI + APScheduler + Chatea Pro (abstraction) + optional Supabase mirror.
- 12 carriers + 7 demo orders seeded.
- Frontend: 7 pages (Métricas, Cola, Cadencia, Tickets, Mensajes, Transportadoras, Conectores).
- 25/25 backend tests passing.

### v1.1 (2026-02-21) — DONE
- **Chatea Pro real endpoints wired** — `/me` returns real workspace ("jeferson moreno").
  Send flow now does subscriber lookup → create-if-missing → send.
- **ElevenLabs voice picker** — 6-voice cap, per-country default, dropdown of
  account voices when API key present, else free-text voice_id.
- **Twilio Verified Caller IDs** — /numbers/verify/start returns validation_code
  to display; /verify/confirm polls Twilio; import existing verified numbers.
- **Novedades reference** — 18-row seed with 6 categories + endpoint + page.
- Connectors page auto-discovers ElevenLabs + Twilio test buttons.

### v1.2 (2026-02-21) — DONE (Agentic Copilot)
- New **Copilot ("Marcus") as landing page** — Claude-style chat UI with
  streaming tool-call cards, markdown rendering, threads sidebar, skill picker,
  auto-mode toggle.
- Real **agent loop** in `agent/loop.py` — Claude Sonnet 4.6 via
  Emergent Universal Key, JSON tool-call protocol, max 6 iterations.
- **15 tools** registered: get_queue, get_orders, get_carriers,
  get_carrier_novedades, schedule_cadence, register_attempt_result,
  send_whatsapp (real Chatea Pro), list_whatsapp_templates, create_task,
  list_tasks, get_metrics, translate, list_voices, list_numbers,
  import_orders_from_file.
- **Skills** — CRUD + 4 seeded (`revisar-cola`, `recuperar-rojos`,
  `redactar-whatsapp`, `novedades-carrier`).
- **Files** — CSV/XLSX upload with pandas parsing (up to 500 rows preview);
  agent tool `import_orders_from_file` bulk-imports rows as COD orders.
- Threads + messages persisted in Mongo with full tool-call trace.

### Testing (v1.2)
- v1.0: 25/25 backend tests passing (report iteration_1.json).
- v1.1+v1.2 smoke tests via curl all green:
  Chatea /me → 200 (ws: jeferson moreno) · 18 novedades · 4 skills seeded ·
  12 queue items · agent run returns full markdown table with tool trace.

## Prioritized Backlog

### P1
- Load full 426-row novedades dataset (owner has it).
- Streaming tokens in the Copilot chat (currently non-streaming send_message).
- Skill "auto" mode UI polish (currently runs but doesn't visualise progress).
- Dropi connector — real endpoints when documented.
- VAPI outbound dial trigger with the selected voice_id + verified caller_id.

### P2
- Full multi-tenant support (org_id).
- Per-user auth on the dashboard.
- Signature verification on webhooks.
- LLM-based translation provider fully implemented.
- Full "Archivos" management page (currently upload happens via API only).

## Deferred
- Push notifications.
- SLA/dashboards per carrier over time (novedad recovery rates).

## 2026-02-21 — ZYNEX v2 Design Alignment
- Full palette refactor: Silver iPhone 17 base (brushed light silver day / dark titanium night, never pure black).
- Accent = ZYNEX gradient (#00D8FF → #0A84FF → #7C5CFF → #C04BFF) with strong neon bloom.
- New reusable components:
  - `WireframePolyhedron` — SVG icosahedron hero centerpiece (rotating, cyan→magenta wireframe, drop-shadow bloom).
  - `Constellation` — canvas dot-network background with drifting nodes, connecting lines, and ~18% sparkling "destellos". Auto-fades in day mode.
- Funnel landing rebuilt to ZYNEX.PRO layout: top marquee ticker · gradient logo nav (Funciones/Diagnóstico/Precios/Ingresar) · split-line headline with gradient accent · 3D wireframe on right · connector pills row (Dropi/Meta Ads/Shopify/WhatsApp/Excel-CSV/Chatea Pro/n8n) · Hormozi value stack + guarantee + scarcity + bonuses + VIP capture form.
- Silver base + gradient neon glow applied consistently to Copilot mascot ring, Login mascot, and all internal pages via Layout constellation background.
- Screenshots verified: funnel (day + night) + Copilot home (day + night).
- Tests: iteration_6 = 100% pass. No functionality regression (all data-testids retained + new ones added: `hero-wireframe`, `funnel-marquee`, `funnel-connector-pills`, `connector-pill-*`).

## 2026-02-21 — Completion Round: Prompts + Telnyx + WhatsApp Rules
- **Prompts module** (Task 2): full CRUD `/api/prompts`, hierarchy resolver (campaign > product > global with country + priority tiebreaker), `POST /prompts/generate` meta-prompt via LLM router (Groq default) that authors a complete Sofía script following the LIT-LOG-RO flow, `POST /prompts/test-voice` returns MP3 via ElevenLabs. Frontend `/app/prompts` with Pegar/Generar tabs, variable chips, live preview. Seeded 2 defaults (Sofía CO + EC).
- **Telnyx connector** (Task 1): env vars TELNYX_API_KEY / TELNYX_CONNECTION_ID / TELNYX_PHONE_NUMBER / TELNYX_SIP_USERNAME / TELNYX_SIP_PASSWORD / TELNYX_SIP_DOMAIN. `POST /api/numbers/telnyx/register` registers the trunk in ElevenLabs. `GET /api/numbers/telnyx/config` returns masked config. Frontend Conexiones page rewritten with a per-connector "Cómo conectar" step-by-step guide in Spanish + env var chips + Probar button, for: Chatea Pro, Telnyx, ElevenLabs, Twilio, Supabase, Dropi, Groq, Gemini, Claude, Mistral, Cerebras.
- **WhatsApp template rules** (Task 4): `WhatsappRule` model + `/api/whatsapp/rules` CRUD + `/api/whatsapp/templates` (proxies Chatea Pro). Scheduler wires the rule based on days_left (0–3 → "Reclamo en Oficina", +3 → "No Oficina"). UI: WhatsappRulesPanel embedded on Messages page.
- Existing combo-safe Dropi import + promotions matching verified live.

## 2026-02-21 — v3 Go-To-Market Round
- **Multi-tenant credentials**: encrypted-at-rest per-org store (`org_credentials` collection with Fernet ciphertext + ENCRYPTION_KEY env). Endpoints `/api/config/providers` (schema), `/api/config/credentials` (status, never leaks plaintext), `PUT /api/config/credentials/{provider}`, `DELETE`, `POST /test`. Frontend `/app/config` with per-provider cards, show/hide secrets, origin badges (org/env/none), masked hint.
- **WhatsApp 24h window**: `whatsapp_contacts` collection, updated on Chatea inbound webhook. `/api/whatsapp/window/{phone}` returns open/closed + remaining_seconds + allowed_send_types. Scheduler enforces template-only outside window. `/api/whatsapp/contacts/mark-inbound` helper for testing.
- **Prompts 6-block ElevenLabs structure**: seeded Sofía CO/EC + _template_sofia_script emit `# Personalidad / # Entorno / # Tono / # Objetivo / # Guardrails / # Herramientas`. Antifluido rule repeated twice. Validation requires the 3 core headers. On boot, existing legacy prompts are force-migrated to the new structure (idempotent).
- **Landing Pricing + Features + FAQ**: 3 plans (Starter $297 / Growth $497 highlighted / Scale·Fundador $997) with monthly/annual toggle (annual = ×10 = 2 free months); 6-item feature grid; 6-question FAQ accordion. All in ZYNEX Silver design.
- **Fixes on iteration_10**: (1) Seed migration replaces legacy 'Eres Sofía...' with new 6-block via $set. (2) Config toast Probar conexión now stringifies detail objects.
