# Desplegar Zynex fuera de Emergent (Render + MongoDB Atlas, gratis) - checklist 10 min

Rama a desplegar: `deploy-render` (o `staging-fuera-emergent`). No es produccion.
Detalle y limitaciones: `DEPLOY_STAGING.md`. Variables: `backend/.env.example`.

## 1. MongoDB Atlas (3 min)
1. https://cloud.mongodb.com -> crear proyecto `zynex-staging`.
2. Create cluster -> **M0 Free**, AWS, `us-east-1`.
3. Database Access -> usuario `zynex_staging` + contrasena generada (guardala en tu gestor).
4. Network Access -> Add IP -> `0.0.0.0/0` (Render free no tiene IP fija).
5. Connect -> Drivers -> Python -> copiar `mongodb+srv://...`, reemplazar `<password>` = **MONGO_URL**.

## 2. Generar 2 llaves (1 min, en tu PC)
- JWT_SECRET: `python3 -c "import secrets;print(secrets.token_urlsafe(48))"`
- ENCRYPTION_KEY: `python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`

## 3. Render Blueprint (4 min)
1. https://dashboard.render.com -> **New -> Blueprint**.
2. Conectar GitHub -> repo `Litper-llamadas`, rama `deploy-render`. Render lee `render.yaml`.
3. Pegar solo estas variables (el resto se deja vacio):
   - `MONGO_URL` (paso 1), `JWT_SECRET` y `ENCRYPTION_KEY` (paso 2)
   - `CORS_ORIGINS` y `APP_PUBLIC_URL` = `https://zynex-staging-web.onrender.com`
4. **Apply**. Crea `zynex-staging-api` (Python) y `zynex-staging-web` (estatico).
5. Si la URL del backend no es `https://zynex-staging-api.onrender.com`, editar en
   `zynex-staging-web -> Redirects/Rewrites` el destino de `/api/*`.

## 4. Verificar (2 min)
- `https://zynex-staging-api.onrender.com/api/health` -> `{"ok": true, ...}`
- `https://zynex-staging-web.onrender.com/api/health` -> igual (prueba el reenvio).
- Abrir el frontend -> registrarse con email + contrasena (Google login NO funciona fuera de Emergent).

## 5. Para las 50 llamadas (M2)
- Agregar luego `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `TWILIO_*` / `OPENROUTER_API_KEY` en Render -> Environment.
- Plan free se duerme a los 15 min y pausa el scheduler: para cadencias reales usar Starter.
- Medicion: `python backend/scripts/medir_llamadas_vs_dropi.py` con el CSV de Dropi.
