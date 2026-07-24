# Auth Testing Playbook — Litper Connect Hub / Zynex OS

Two auth flows coexist and share the same `litper_session` cookie (HttpOnly JWT):

1. Email + password (bcrypt) via `POST /api/auth/register` and `POST /api/auth/login`.
2. Emergent-managed Google OAuth via `POST /api/auth/google/session` (backend
   fetches profile from `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data`
   with header `X-Session-ID: <session_id>`).

## 1) Email + password flow
```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)

# Register
curl -s -c /tmp/c.txt -X POST "$API/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"qa@litper.co","password":"Litper!2026","nombre":"QA","org_name":"Litper QA"}'

# Login (fresh cookie jar)
curl -s -c /tmp/c.txt -X POST "$API/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"qa@litper.co","password":"Litper!2026"}'

# Me
curl -s -b /tmp/c.txt "$API/api/auth/me"

# Logout
curl -s -b /tmp/c.txt -X POST "$API/api/auth/logout"
```

## 2) Google OAuth flow (Emergent-managed)
- Frontend triggers `window.location.href = "https://auth.emergentagent.com/?redirect=" + encodeURIComponent(window.location.origin + "/app")`.
- After success the browser lands at `<origin>/app#session_id=xxxx`.
- Frontend's `AppRouter` detects `location.hash.includes("session_id=")` synchronously,
  renders `AuthCallback`, which POSTs the id to `/api/auth/google/session`:

```bash
curl -s -c /tmp/c.txt -X POST "$API/api/auth/google/session" \
  -H "X-Session-ID: <session_id>"
```

Response sets the `litper_session` cookie and returns:
```json
{ "ok": true, "user": {"id":"...", "email":"...", "nombre":"...", "org_id":"...", "role":"owner"}}
```

## Frontend gating
- `App.js` uses a `Gate` component that hits `GET /api/auth/me` on mount.
- While loading it returns `null` (splash) — do NOT flash the funnel.
- On 401 it redirects to `/login`. On 200 it renders the protected page.

## Playwright bootstrap
```js
await page.request.post('https://litper-hub.preview.emergentagent.com/api/auth/login', {
  data: { email: 'qa@litper.co', password: 'Litper!2026' }
});
await page.goto('https://litper-hub.preview.emergentagent.com/app');
```

## Credentials for tests
See `/app/memory/test_credentials.md`.
