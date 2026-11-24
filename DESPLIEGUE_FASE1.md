# Despliegue — Fase 1 (agente universal, multi-cliente)

Rama `fase1-agente-universal`. Este documento lista lo que hay que configurar,
en qué orden desplegar y qué **no** se ha verificado contra servicios reales.

## 1. Variables de entorno del backend

### Obligatorias (sin ellas no arranca o no funciona)

| Variable | Por defecto | Qué pasa si falta |
|---|---|---|
| `MONGO_URL`, `DB_NAME` | — | No hay base de datos. |
| `JWT_SECRET` | — | **El servidor no arranca** (salvo `ENV=development`). Valor largo y aleatorio. |
| `ENCRYPTION_KEY` | — | Clave Fernet. Sin ella no se pueden guardar ni leer las credenciales de los clientes. **Usar la misma de siempre**: si cambia, lo ya guardado queda ilegible. |
| `PUBLIC_API_KEY` | — | Las llamadas sin sesión responden 500. |
| `PUBLIC_BASE_URL` | vacío | URL pública https del backend. Sin ella los agentes de voz se registran **sin herramientas ni webhook de resultados**, y las direcciones de webhook se deducen de la petición. |
| `CORS_ORIGINS` | vacío | Orígenes del frontend, separados por coma. Sin ella (y sin la siguiente) solo se acepta `http://localhost:<puerto>`. |

### Nuevas en esta fase (opcionales, con su valor por defecto)

| Variable | Por defecto | Efecto |
|---|---|---|
| `ENV` / `ENVIRONMENT` | vacío | `production` = modo producción; `development` permite arrancar sin `JWT_SECRET`. `RENDER` definida también cuenta como producción. |
| `PLATFORM_KEYS_ORGS` | sin definir = **nadie** | Qué clientes pueden usar las llaves del servidor (`org1,org2` o `*`). Sin definir, cada cliente debe conectar las suyas. Para conservar el comportamiento del cliente actual: poner su `org_id`. |
| `CORS_ORIGIN_REGEX` | `http://localhost:\d+` | Orígenes por patrón (p. ej. previews). |
| `RETELL_WEBHOOK_SECRET` | vacío | Solo para la ruta antigua `/api/calls/webhook` (cabecera `X-Webhook-Secret`). Vacío → esa ruta responde 503. La ruta con token no lo necesita. |
| `CHATEA_WEBHOOK_SECRET`, `ELEVENLABS_WEBHOOK_SECRET` | vacío | Igual, para las rutas antiguas `/api/webhooks/chatea` y `/elevenlabs`. Vacío → 503. |
| `GOOGLE_LOGIN` | vacío = apagado | `1` enciende `POST /api/auth/google/session`. Apagado → 404. |
| `GOOGLE_SESSION_URL` | vacío | URL https del servicio que intercambia la sesión de Google. Hace falta junto con `GOOGLE_LOGIN=1`; si falta → 404. |
| `VIP_LEADS_PUBLIC` | vacío = apagado | `1` enciende el formulario público `POST /api/vip-leads` (y `/config`). Apagado → 404. Máx. 5 envíos por hora por IP; solo guarda el lead, no envía WhatsApp. |
| `VIP_LEADS_ORG` | `default` | Cliente al que se asignan esos leads. |
| `VIP_GROUP_URL` | vacío | Enlace que devuelve `/api/vip-leads/config`. |
| `ALLOW_INSECURE_MCP` | vacío = apagado | `1` permite conectores MCP por http o por puertos distintos de 443/8443. **No activar en producción.** |
| `TRUSTED_PROXY_HOPS` | `1` | Cuántos proxies propios hay delante (para leer la IP real de `X-Forwarded-For` en los límites de frecuencia). |
| `DAILY_REPORT_HOUR` | `8` | Hora **local de cada negocio** del reporte diario. |
| `SCHEDULER_TICK_MINUTES` | `2` | Frecuencia del despachador. |
| `USD_TO_<MONEDA>` | `USD_TO_COP=4200` | Tipo de cambio para las métricas. Sin el de la moneda del perfil, las cifras salen en USD y se avisa. |
| `COD_MARGIN_PCT`, `RTO_BASELINE_PCT` | `30`, `30` | Supuestos del retorno estimado. |
| `TWILIO_COST_PER_MIN`, `ELEVENLABS_COST_PER_MIN`, `WHATSAPP_COST_PER_MSG`, `LLM_COST_PER_1K` | `0.014`, `0.30`, `0.005`, `0.003` | Costos unitarios en USD de los costos estimados. |
| `OPENROUTER_MODEL_DEFAULT`, `OPENROUTER_MODEL_REASONING` | `google/gemini-2.5-flash`, `anthropic/claude-sonnet-4.5` | Modelos del asistente. |
| `SEED_ORG_ID` | `default` | Cliente que recibe los datos de arranque. |

Llaves de proveedores a nivel servidor (`OPENROUTER_API_KEY`, `RETELL_API_KEY`,
`CHATEA_PRO_API_KEY`, `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`, `ELEVENLABS_API_KEY`…):
solo las usan los clientes listados en `PLATFORM_KEYS_ORGS`.

### Frontend (se fijan al compilar)

| Variable | Por defecto | Efecto |
|---|---|---|
| `REACT_APP_BACKEND_URL` | — | Obligatoria: URL del backend. |
| `REACT_APP_GOOGLE_LOGIN` | apagado | `1` muestra el botón de Google (necesita además `REACT_APP_GOOGLE_AUTH_URL` https y el backend encendido). |

## 2. Orden de despliegue

1. **Respaldo** de la base de datos (`mongodump`) y copia del `.env` actual.
2. **Migración**, desde `backend/`, con el `org_id` real del cliente actual
   (sale de `GET /api/auth/me`):
   - Simulación (solo cuenta): `python scripts/migrar_org_id.py --org <ORG>`
   - Revisar los números y aplicar: `python scripts/migrar_org_id.py --org <ORG> --apply`

   Es idempotente y no borra nada. Debe correr **antes** de arrancar la versión
   nueva: un documento sin `org_id` no lo ve nadie.
3. **Desplegar** backend (con las variables de arriba) y frontend. Comprobar
   `GET /api/health` y que se puede iniciar sesión.
4. **Reapuntar los webhooks**: en Conexiones → Conectores, copiar «Tus direcciones
   de webhook» y pegarlas en el panel de cada proveedor (WhatsApp/Chatea Pro,
   Twilio, ElevenLabs, Retell). Las rutas antiguas sin token responden 503 si no
   tienen secreto.
5. **Volver a guardar los agentes publicados** (abrir cada uno y «Publicar en
   vivo»): así se envían al proveedor de voz sus herramientas, su token y su
   webhook nuevos.

Si se pulsa «Rotar direcciones», repetir los pasos 4 y 5.

## 3. Cambios de comportamiento que conviene saber

- `POST /custom-agents/{id}/test-call` sin telefonía conectada responde
  `ok:false, dialed:false, error` (antes `ok:true`).
- `/auth/login` y `/auth/register`: 10 fallos por IP+correo en 15 min → 429.
- Herramienta de voz `enviar_whatsapp`: solo escribe al número del cliente de
  esa llamada o pedido.
- `/metrics`: claves neutras (`norte.cpr`, `norte.roi`, `costos.totals.llamadas`…).
  Las antiguas `*_cop` siguen como alias.
- Los límites de frecuencia viven **en memoria**: valen para un solo proceso.
  Con varias réplicas o workers hay que moverlos a Mongo o Redis.

## 4. Lo que NO está verificado

Todo lo siguiente está probado solo con dobles de prueba (base en memoria y
respuestas HTTP simuladas), nunca contra el servicio real:

- **Retell real**: el formato de crear/actualizar agente, de las herramientas
  personalizadas, de las variables dinámicas y del webhook de fin de llamada
  sigue la documentación pública tal como la entendimos. No se ha hecho ninguna
  llamada real. Por eso la pantalla de Agentes dice «Llamadas telefónicas: en
  beta». Si Retell rechaza el formato, se corrige en `backend/retell_service.py`.
  En concreto, que el sobre de la herramienta traiga `call.to_number` (lo usa
  `enviar_whatsapp`) está sin confirmar; con `pedido_id` funciona igual.
- **Servidor MCP real de terceros**: el cliente MCP se probó contra un servidor
  simulado; no contra ninguno público.
- **IA real**: ninguna prueba llama a un modelo (OpenRouter u otro). La calidad
  de las respuestas y el uso de herramientas por el modelo no están medidos.
- **Navegador con sesión**: el frontend compila sin avisos y pasa su prueba de
  textos, pero nadie ha recorrido las pantallas con una sesión iniciada.
- **WhatsApp (Chatea Pro), Twilio y ElevenLabs reales**: envíos y firmas de
  webhook probados solo con respuestas simuladas.
- **Inicio de sesión con Google**: probado con un servicio de intercambio simulado.
- **Migración**: probada sobre la base en memoria, no sobre una copia de producción.
- Las pruebas de servidor vivo (`tests/test_iteration*.py`, `test_hub*.py`,
  `test_launch_round.py`) no se ejecutaron; varias describen el comportamiento
  anterior (p. ej. formulario público abierto) y fallarían sin actualizarse.
