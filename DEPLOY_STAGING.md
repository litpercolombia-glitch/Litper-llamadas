# Despliegue a STAGING fuera de Emergent (Render + MongoDB Atlas, gratis)

Rama: `staging-fuera-emergent` (basada en `fase0-openrouter-byok`). No toca `main` ni producción.

Probado localmente (fuera de Emergent): backend FastAPI arranca con Mongo local,
`GET /api/health` → 200, registro + login + lectura de datos → 200, y el frontend compila (`yarn build`).

## 1. MongoDB Atlas (cluster gratis)
1. Entra a https://cloud.mongodb.com y crea un proyecto `zynex-staging`.
2. **Create cluster → M0 (Free)**, proveedor AWS, región cercana (p. ej. `us-east-1`).
3. **Database Access → Add New Database User**: usuario `zynex_staging`, contraseña generada (guárdala en tu gestor de contraseñas, no en el repo).
4. **Network Access → Add IP Address → `0.0.0.0/0`** (Render free no tiene IP fija; es solo staging).
5. **Connect → Drivers → Python** y copia la cadena `mongodb+srv://zynex_staging:<password>@.../?retryWrites=true&w=majority`. Reemplaza `<password>`. Esa es tu `MONGO_URL`.

## 2. Render (Blueprint)
1. Entra a https://dashboard.render.com → **New → Blueprint**.
2. Conecta GitHub y elige el repo `Litper-llamadas`, rama **`staging-fuera-emergent`**. Render detecta `render.yaml`.
3. Render te pedirá los valores marcados `sync: false`. Mínimos para que funcione:
   - `MONGO_URL`: la cadena de Atlas del paso 1.
   - `JWT_SECRET`: texto aleatorio largo. Puedes generarlo con `python3 -c "import secrets;print(secrets.token_urlsafe(48))"`.
   - `ENCRYPTION_KEY`: llave Fernet. Genérala con `python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`.
   - `CORS_ORIGINS` y `APP_PUBLIC_URL`: `https://zynex-staging-web.onrender.com` (o la URL que Render asigne al frontend).
   - El resto (OpenRouter, ElevenLabs, Twilio, Chatea, Supabase, SMTP, `PUBLIC_API_KEY`) déjalo vacío hasta que quieras probar esa integración.
4. **Apply**. Se crean 2 servicios: `zynex-staging-api` (Python) y `zynex-staging-web` (sitio estático).
5. Si Render le da al backend una URL distinta a `https://zynex-staging-api.onrender.com`, ve a `zynex-staging-web → Redirects/Rewrites` y cambia el destino de la regla `/api/*`.

## 3. Verificar
- `https://zynex-staging-api.onrender.com/api/health` → `{"ok":true,...}`
- `https://zynex-staging-web.onrender.com/api/health` → lo mismo (prueba que la regla de reenvío funciona).
- Abre el frontend, **Regístrate con email y contraseña** y entra.

## Cambios hechos para salir de Emergent
- `frontend/public/index.html`: quitado el script `assets.emergent.sh/scripts/emergent-main.js` y el bloque de analítica PostHog que enviaba datos a `ap.emergent.sh`.
- `frontend/.env.production` (forzado en git): `REACT_APP_BACKEND_URL` vacía, así el build llama a `/api` en el mismo dominio, y el static site lo reenvía al backend. Así la cookie de sesión (`SameSite=Lax`) funciona sin CORS.
- Backend: la rama base ya había quitado `emergentintegrations` y `litellm` del CDN de Emergent; todas las dependencias se instalan desde PyPI.

## Limitaciones conocidas (staging)
- **Login con Google** usa `auth.emergentagent.com`; fuera de Emergent no funcionará. Usar email + contraseña.
- **Plan free de Render se duerme** tras 15 min sin tráfico (el primer request tarda ~1 min) y el scheduler interno (cadencias, reporte CEO) no corre mientras duerme. Para pruebas reales de llamadas programadas, usar plan Starter.
- `allow_origin_regex` del backend sigue apuntando a `*.preview.emergentagent.com`; no afecta porque el frontend usa el mismo dominio vía reenvío.
- Las llamadas, WhatsApp e IA necesitan sus credenciales; sin ellas esas funciones responden error pero el resto de la app funciona.
