# PILOTO 50 LLAMADAS — Rescate de novedades Litper (Zynex Connect v2)

> Versión 1 · 9-oct-2026 · Autor: especialista Zynex · Estado: **borrador para aprobación del CEO**
> Hito de misión: **50 contactos reales de Litper medidos contra Dropi al 31-oct-2026.**
> Nada en este documento se ha ejecutado: no se ha contactado a ningún cliente, no se han creado cuentas ni tablas y no se ha gastado dinero.

---

## 0. Resumen en 30 segundos

- **Qué:** contactar pedidos COD de Litper **en novedad** (no en frío) con la escalera v2: WhatsApp → llamada por WhatsApp con IA (con permiso) → 1 llamada desde número colombiano en horario legal → humano. Se guarda evidencia de cada contacto.
- **Cómo se mide:** experimento aleatorio. 50 pedidos tratados + 50 de control (gestión habitual, sin Zynex). Se compara la **tasa de entrega en Dropi a los 10 días**.
- **Qué podemos esperar ver:** con 50 por grupo solo se detecta con confianza un efecto **grande** (~**+27 puntos porcentuales**). Un efecto real de +10 pp **no** saldrá estadísticamente significativo. Para el hito no importa: lo que cuenta es tener **50 contactos medidos de verdad**, con su desenlace en Dropi y la estimación del efecto con su intervalo.
- **Riesgo n.º 1, el calendario:** para medir a 10 días antes del 31-oct, la **inscripción tiene que cerrar el 21-oct**. Hacen falta ~100 novedades elegibles entre hoy y esa fecha (hay ~29 abiertas al 8-oct). Ver §1.6.
- **Valor:** cada pedido rescatado vale ~COP 90.000. Al corte del 8-oct hay ~29 pedidos en novedad con ~COP 4,58M de recaudo detenido.

---

## 1. Objetivo, métrica verdad, hipótesis y tamaño

### 1.1 Objetivo
Medir si el contacto de Zynex sobre pedidos en novedad **aumenta la entrega real** (recaudo COD) frente a la gestión habitual, con Dropi como fuente de verdad. No se mide "llamadas hechas" ni "clientes que dijeron sí": se mide **pedido entregado según Dropi**.

### 1.2 Métrica verdad (primaria)
**Tasa de entrega a 10 días** = pedidos con estado final de entrega en Dropi a los 10 días calendario de la inscripción ÷ pedidos inscritos en el grupo.

- **Día 0** = fecha y hora en que el pedido entra al piloto (se detecta la novedad y se le asigna grupo).
- **Cuenta como entregado:** `ENTREGADO` (estado Dropi) o el equivalente de la transportadora (`ENTREGADA`, `ENTREGA EXITOSA`, `ENTREGA VERIFICADA`, `ENTREGADA DIGITALIZADA`, `DESPACHO EFECTIVO`, etc.).
- **Cuenta como NO entregado:** `DEVOLUCION`, `DEVOLUCION EN TRANSITO`, `DEVUELTO AL REMITENTE`, `DEVOLUCIÓN RATIFICADA`, etc., **y también todo pedido que siga en tránsito o en novedad el día 10** (criterio conservador). El desenlace del día 20 se registra aparte como métrica secundaria.
- **Análisis por intención de tratar (ITT):** un pedido del grupo tratado cuenta aunque el cliente no conteste. Así se mide el efecto real de *intentar* rescatar, que es lo que Litper pagaría.

**Métricas secundarias** (solo descriptivas): tasa de contacto efectivo, tasa de compromiso ("recibo el jueves"), cumplimiento del compromiso, días hasta la entrega, novedades falsas detectadas (el cliente dice "nunca vinieron") y COP recaudado por grupo.

### 1.3 Hipótesis
- **H1:** la tasa de entrega a 10 días del grupo tratado es mayor que la del control.
- **H0:** no hay diferencia.
- Prueba: diferencia de dos proporciones (z o exacta de Fisher si hay celdas pequeñas), α = 0,05 a dos colas. Se reporta la **diferencia en puntos porcentuales con IC 95 %**, no solo el valor p.

### 1.4 Tamaño y asignación
- **100 pedidos en novedad: 50 tratados + 50 control.**
- **Asignación aleatoria por el último dígito del ID de pedido de Dropi:**
  - dígito **par (0, 2, 4, 6, 8)** → **TRATADO** (Zynex contacta)
  - dígito **impar (1, 3, 5, 7, 9)** → **CONTROL** (gestión habitual, Zynex no contacta)
- La regla se fija **antes** de ver el pedido y no se cambia. Nadie elige a mano "a quién sí llamamos". Si un grupo llega a 50 antes que el otro, se sigue inscribiendo solo en el grupo que falta hasta completar los dos.
- **Control = gestión habitual, no abandono.** Lo que Litper ya hace hoy con las novedades (por ejemplo, la solución de novedad en el panel de Dropi) se aplica **igual a los dos grupos**. La única diferencia entre grupos es el contacto de Zynex. Si no, el experimento mide otra cosa.
- **Supuesto a verificar:** el último dígito del ID de Dropi no está correlacionado con la transportadora, la ciudad ni el producto. Antes de arrancar se revisa con los últimos ~200 pedidos que la mezcla de transportadoras y ciudades sea parecida entre pares e impares.

### 1.5 Por qué con 50 solo se ve un efecto grande (efecto mínimo detectable)

Fórmula del tamaño muestral por grupo para comparar dos proporciones:

```
n = [ z(1-α/2) · √(2·p̄·(1-p̄))  +  z(1-β) · √(p1·(1-p1) + p2·(1-p2)) ]²  /  (p2 - p1)²

p1 = tasa de entrega del control (rescate "solo")
p2 = tasa de entrega del tratado
p̄  = (p1 + p2) / 2
z(1-α/2) = 1,96   (α = 0,05, dos colas)
z(1-β)   = 0,84   (potencia 80 %)
```

Se despeja el menor `p2 − p1` que hace `n ≤ 50`:

| Supuesto de p1 (entrega del control a 10 días) | MDE con 50/50 | MDE con 100/100 | MDE con 29/29 |
|---|---|---|---|
| 30 % | **+27,5 pp** (→ 57,5 %) | +19,3 pp | +36,1 pp |
| **40 % (supuesto central)** | **+27,7 pp** (→ 67,7 %) | +19,7 pp | +35,7 pp |
| 50 % | **+26,7 pp** (→ 76,7 %) | +19,4 pp | +34,0 pp |

**SUPUESTOS (marcados, no verificados):**
1. **p1 ≈ 40 %.** No tenemos la tasa histórica de entrega *de los pedidos que caen en novedad* (la línea base de 83,4 % es de **todos** los pedidos, cohorte 8-ago a 22-sep). Si el 83,4 % incluye los pedidos que se recuperan solos, la novedad "suelta" probablemente resuelve bastante menos de la mitad. **Acción:** sacar p1 real de Dropi (pedidos de ago-sep que tuvieron algún estado de novedad y su desenlace final).
2. Pedidos independientes (un cliente = un pedido; si hay dos pedidos del mismo teléfono, solo entra el primero).
3. Aproximación normal; con n = 50 es aceptable y se confirma con la prueba exacta de Fisher.

**Lectura honesta:** con 50/50, si Zynex sube la entrega de novedades de 40 % a 55 % (+15 pp, que sería muy valioso), **lo más probable es que el piloto no salga "significativo"**. Por eso:
- El piloto **no** se juzga solo por el valor p. Se reporta la diferencia, el IC 95 % y el COP rescatado.
- Es un **piloto de factibilidad y de efecto grande**. Si la diferencia apunta en la dirección buena, el siguiente paso es extenderlo a ~100/100 (MDE ~20 pp) o acumular cohortes de varias semanas.

Referencia de economía: con p1 = 40 %, un efecto de +27,7 pp sobre 50 pedidos tratados son ~14 pedidos rescatados × ~COP 90.000 ≈ **COP 1,25M** adicionales en un ciclo.

### 1.6 Calendario y factibilidad (crítico)

| Fecha | Hito |
|---|---|
| 9–10 oct | CEO aprueba (§6). Revisión del dígito y de p1 histórico en Dropi. Plantillas WhatsApp listas. |
| **dom 11 y lun 12 oct** (domingo y festivo, Día de la Raza) | **No se contacta.** Solo inscripción y asignación de grupo. |
| mar 13 oct → **mié 21 oct** | Inscripción y contacto (7 días hábiles + sáb 17 de 8 a. m. a 3 p. m.). Último día para inscribir y medir a 10 días antes del 31-oct. |
| 23 oct | Corte intermedio: desenlaces de los inscritos del 13 oct. |
| **31 oct** | Corte final a 10 días de todos los inscritos. Reporte. |

- Hacen falta **~100 novedades elegibles** entre el 10 y el 21 de octubre. Al 8-oct hay ~29 abiertas, que entran si siguen abiertas el día de inicio y se asignan por dígito igual que las demás. Faltan **~70 nuevas en ~7 días hábiles, es decir ~10 por día hábil.**
- **Si el flujo no alcanza** (por ejemplo, Litper genera 3–4 novedades al día): (a) se mantiene la asignación aleatoria con los pedidos que haya y se mide a 10 días lo inscrito hasta el 21-oct; (b) el hito de "50 medidos" se cumple contando los **tratados con desenlace a 10 días** y se dice explícitamente cuántos son; (c) el piloto sigue en noviembre para completar 50/50. **No se rellena el grupo tratado con pedidos sin novedad ni con llamadas en frío:** eso rompe la métrica.
- **Primera tarea concreta:** contar en Dropi cuántos pedidos entraron a novedad por día en sep–oct. Si son menos de ~6 por día hábil, el 31-oct solo es alcanzable con el plan (b).

---

## 2. Elegibilidad y exclusiones

### 2.1 Criterios de inclusión (todos)
1. Pedido COD de Litper despachado por Dropi.
2. Estado actual de **novedad abierta** en Dropi o en la transportadora. Estados válidos según el catálogo de Dropi (consultado el 9-oct-2026):
   - **Genéricos:** `NOVEDAD` (Envía, Domina, Veloces).
   - **Cliente ausente / nadie recibe:** `CERRADO O NO HAY QUIEN RECIBA` (Domina), `INTENTO DE ENTREGA`, `PARA NUEVO INTENTO ENTREGA` (Interrapidísimo), `NO ENTREGADO`, `REAGENDADO` (Suppli Express), `EN ESPERA DE CITA` (Envía).
   - **No reclama en oficina:** `PARA RECLAMAR EN OFICINA`, `RECLAME EN OFICINA` (Interrapidísimo), `EN PUNTO DROOP` (Coordinadora), `RECIBIDO PUNTO DE VENTA` (Veloces), `LLEGO A OFICINA DE DESTINO` (Suppli).
   - **Dirección errada / zona:** `MAL ZONIFICADO`, `NO SE CUBRE LA ZONA` (Domina), `CERRADO POR INCIDENCIA, VER CAUSA` (Coordinadora; revisar la causa).
   - **Confirmación telefónica pendiente:** `EN CONFIRMACIÓN TELEFÓNICA`, `TELEMERCADEO` (Interrapidísimo).
   - **Otros:** `STAND BY` (Envía), `NOVEDAD DEVOLUCION` (Veloces) **solo si la devolución todavía no está ratificada**.
3. El cliente tiene un número celular colombiano válido (+57 3xx).
4. Hay tiempo para gestionar: la transportadora no ha marcado devolución definitiva.

### 2.2 Exclusiones (el pedido no entra al piloto)
- Ya en `DEVOLUCION`, `DEVOLUCION EN TRANSITO`, `DEVOLUCIÓN RATIFICADA`, `PARA DEVOLVER AL REMITENTE`, `EN PROCESO DE DEVOLUCIÓN`, `DEVUELTO AL REMITENTE` o `DEVOLUCIÓN POR CONFIRMACIÓN DEL CLIENTE`.
- Novedades no rescatables por contacto: `INCAUTADO`, `SINIESTRO`, `PROBLEMAS DE ORDEN PUBLICO`, `CIERRE DE VIAS PUBLICAS`, `CONDICIONES CLIMATOLOGICAS ADVERSAS`, `NO LLEGO EL ENVÍO FÍSICO`, `FISICO NO RECIBIDO`, indemnizaciones.
- El cliente ya pidió no ser contactado, ya canceló explícitamente o tiene una PQR o garantía abierta.
- Pedido duplicado del mismo teléfono (entra solo el primero).
- Pedidos de prueba, internos o de mayoristas.
- Las exclusiones se aplican **antes** de mirar el dígito. Si un pedido se excluye después de asignado (por ejemplo, el cliente dice "no me vuelvan a llamar"), **sigue contando en su grupo** (ITT).

---

## 3. Guiones

**Reglas de tono:** cálido, colombiano, de usted, corto y sin presión. Nunca se mencionan reembolsos, devoluciones de dinero ni garantías de devolución. Las plantillas son generales (no por producto) y llevan variables entre `{{ }}`. El asistente se presenta siempre como **asistente virtual de Litper**.

### 3.1 WhatsApp (3 mensajes)

**Mensaje 1. Aviso de la novedad (día 0, en horario legal)**
> ¡Hola, {{nombre}}! 👋 Le escribe el asistente virtual de **Litper**. Su pedido **#{{pedido_id}}** va en camino con {{transportadora}}, pero la transportadora nos reportó una novedad: *{{motivo_novedad_en_palabras_simples}}*.
> Queremos que le llegue sin problema. ¿Nos ayuda a confirmar un dato? Puede responder aquí mismo. 🙏

**Mensaje 2. Opciones concretas (si responde, o 3–4 horas después si no responde, el mismo día y antes de las 7 p. m.)**
> Para que la entrega salga bien, cuéntenos qué le queda mejor:
> 1️⃣ Confirmar o corregir la dirección
> 2️⃣ Decirnos qué día y en qué horario hay alguien para recibir
> 3️⃣ Recogerlo en la oficina de {{transportadora}} en {{ciudad}}
> 4️⃣ Ya no lo necesito
> Si prefiere, **le podemos llamar por aquí mismo por WhatsApp** 2 minuticos. ¿Le parece bien? Responda *SÍ LLAMADA* y le marcamos.

**Mensaje 3. Confirmación de compromiso (cuando hay acuerdo)**
> ¡Listo, {{nombre}}! ✅ Quedó así: *{{compromiso}}* el **{{fecha_compromiso}}**. Ya le avisamos a {{transportadora}}.
> Recuerde tener a la mano **${{valor_cod}}** para pagar contraentrega. Si algo cambia, escríbanos aquí. ¡Gracias por confiar en Litper! 💛

*Reglas de envío:* máximo los 3 mensajes, todos en horario legal y sin repetir los mismos mensajes en días seguidos. Si no responde nada, el mismo día solo se envía el mensaje 2 y se escala a la llamada (§3.3). En el Mensaje 2 se pide el permiso para la llamada por WhatsApp; **sin ese "sí" no se hace la llamada por WhatsApp**.

### 3.2 Escalera de contacto (v2) y reglas de frecuencia

| Paso | Canal | Condición | Ventana |
|---|---|---|---|
| 1 | WhatsApp, mensajes 1 y 2 | Siempre (grupo tratado) | Día 0 |
| 2 | Llamada **por WhatsApp** con IA | Solo si el cliente respondió "SÍ LLAMADA" o pidió que lo llamaran | Mismo día del permiso, en horario legal |
| 3 | 1 llamada desde **1 número colombiano** (IA o persona) | No hubo respuesta al WhatsApp en 24 h | **Un solo intento**, otro día |
| 4 | Humano de Litper | Rechazo, enojo, caso complejo o el cliente pide hablar con una persona | Horario legal |

- **Máximo 1 contacto saliente por día** por cliente, y no más de **2 días con contacto** por pedido en la semana. Las respuestas a mensajes que el cliente inicia no cuentan como contacto nuevo.
- **Nunca** ráfagas: no se rellama a los 5 minutos ni se hacen llamadas cortas repetidas desde la misma línea. Ese patrón es justo el que la CRC marca como "llamada sospechosa" (§5.3).

### 3.3 Guion de llamada (IA o humano)

**A. Apertura con permiso (≤ 20 s)**
> "¡Buenos días/tardes! ¿Hablo con {{nombre}}? … Mucho gusto, le habla el asistente virtual de **Litper**, la tienda donde usted pidió {{categoria_general: "un producto para el hogar"}}. Lo llamo por su pedido que va en camino. **Esta llamada se graba para tener constancia de lo que acordemos. ¿Tiene dos minuticos?**"
- **No / ahora no** → "Con gusto, ¿le escribo por WhatsApp o prefiere que le marquemos otro día?" Se registra y se cierra. **No se insiste.**
- **No acepta la grabación** → se detiene la grabación (o se pasa a WhatsApp) y se continúa solo con notas.
- **No es la persona** → "¿Me ayuda a que {{nombre}} nos escriba al WhatsApp de Litper? Muchas gracias." No se dan detalles del pedido a terceros.

**B. Verificación (≤ 30 s)**
> "Para confirmar: el pedido número {{últimos 4 dígitos}}, a nombre de {{nombre}}, para {{ciudad}}. La transportadora nos reporta *{{motivo}}*. ¿Usted sí está esperando el pedido?"
- Si dice **"nadie ha venido" o "nunca me llamaron"** → *evidencia de novedad posiblemente falsa*: "Entiendo, qué pena con usted. Lo dejo anotado para reclamarle a la transportadora." Se marca `novedad_falsa_reportada = true` y se sigue con la rama que corresponda.

**C. Ramas**

| Rama | Disparador | Guion clave | Acción y registro |
|---|---|---|---|
| **1. Dirección** | Dirección errada o incompleta | "¿Me regala la dirección completa, con barrio y un punto de referencia? … Se la repito: {{dirección}}. ¿Está bien así?" | Se lee la dirección de vuelta. Se actualiza en la solución de novedad de Dropi. `resultado = direccion_corregida` |
| **2. Ausente** | Nadie recibió | "Tranquilo(a), pasa mucho. ¿Qué día y en qué horario hay alguien en casa? ¿Hay otra persona que pueda recibir y pagar?" | Se registran la fecha, la franja y quien recibe. Se agenda el reintento. `resultado = reprogramado` |
| **3. Reclamo en oficina** | Está en oficina o punto | "Su pedido lo espera en la oficina de {{transportadora}} en {{dirección_oficina}}, abierta {{horario}}. Solo lleve su cédula y ${{valor_cod}}. ¿Qué día le queda bien pasar?" | Se envía la ubicación por WhatsApp. `resultado = va_a_oficina` |
| **4. Rechazo** | "Ya no lo quiero" | "Entiendo perfectamente. ¿Me cuenta qué pasó, para mejorar? … *(si es por tiempo o dinero)* ¿Le serviría recibirlo otro día de esta semana o la próxima?" Una sola pregunta de rescate. Si mantiene el no: "Listo, gracias por avisarnos. Que tenga buen día." | **No** se ofrecen descuentos ni reembolsos y **no** se insiste más de una vez. Se registra el motivo. `resultado = rechazo` |

**D. Cierre con compromiso y fecha (≤ 20 s)**
> "Perfecto, {{nombre}}. Entonces queda: **{{compromiso}} el {{día}} {{fecha}}**, y tiene a la mano **${{valor_cod}}** para pagar contraentrega. Le dejo todo por escrito en su WhatsApp. ¿Algo más en lo que le pueda ayudar? ¡Que tenga un excelente día!"
- Se envía el **Mensaje 3** de WhatsApp como constancia escrita.
- **Pase a humano:** si el cliente está molesto, pide una persona, menciona un reclamo legal o garantía, o la IA no entiende dos veces seguidas.

---

## 4. Registro

### 4.1 Campos por contacto (una fila por **intento** de contacto; los controles tienen una fila de inscripción sin contacto)

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | uuid | Clave de la fila |
| `pedido_id` | text | ID de pedido en Dropi |
| `guia` | text | Número de guía de la transportadora |
| `transportadora` | text | Envía, Interrapidísimo, Coordinadora… |
| `grupo` | text | `tratado` / `control` (por último dígito) |
| `fecha_inscripcion` | timestamptz | Día 0 |
| `estado_novedad_inicial` | text | Estado Dropi o transportadora al inscribir |
| `canal` | text | `whatsapp_msg` / `whatsapp_llamada_ia` / `llamada_numero_co` / `humano` / `ninguno` (control) |
| `paso_escalera` | smallint | 1–4 |
| `hora_contacto` | timestamptz | Hora real (zona America/Bogota) |
| `dentro_horario_legal` | boolean | Validación automática (§5) |
| `permiso_llamada` | boolean | El cliente dio el "sí" para la llamada |
| `permiso_grabacion` | boolean | El cliente aceptó la grabación |
| `resultado` | text | `sin_respuesta` / `direccion_corregida` / `reprogramado` / `va_a_oficina` / `rechazo` / `no_es_titular` / `pide_no_contacto` / `pase_humano` |
| `compromiso` | text | Texto del acuerdo |
| `fecha_compromiso` | date | Fecha prometida |
| `novedad_falsa_reportada` | boolean | El cliente dice que nadie fue o nadie llamó |
| `evidencia_url` | text | Grabación, captura o transcripción (almacenamiento privado) |
| `duracion_seg` | int | Duración de la llamada |
| `estado_dropi_d10` | text | Estado en Dropi a los 10 días |
| `entregado_d10` | boolean | Métrica verdad |
| `estado_dropi_d20` | text | Secundaria |
| `valor_cod` | numeric | COP del pedido |
| `notas` | text | Libre |

### 4.2 DDL propuesto para Supabase (**NO ejecutado; solo propuesta**)

```sql
-- PROPUESTA. No ejecutar sin aprobación del CEO.
create table if not exists public.piloto_novedades (
  id                       uuid primary key default gen_random_uuid(),
  pedido_id                text        not null,
  guia                     text,
  transportadora           text,
  grupo                    text        not null check (grupo in ('tratado','control')),
  fecha_inscripcion        timestamptz not null default now(),
  estado_novedad_inicial   text        not null,
  canal                    text        not null check (canal in
                             ('whatsapp_msg','whatsapp_llamada_ia','llamada_numero_co','humano','ninguno')),
  paso_escalera            smallint    check (paso_escalera between 1 and 4),
  hora_contacto            timestamptz,
  dentro_horario_legal     boolean,
  permiso_llamada          boolean     default false,
  permiso_grabacion        boolean     default false,
  resultado                text        check (resultado in
                             ('sin_respuesta','direccion_corregida','reprogramado','va_a_oficina',
                              'rechazo','no_es_titular','pide_no_contacto','pase_humano')),
  compromiso               text,
  fecha_compromiso         date,
  novedad_falsa_reportada  boolean     default false,
  evidencia_url            text,
  duracion_seg             integer,
  estado_dropi_d10         text,
  entregado_d10            boolean,
  estado_dropi_d20         text,
  valor_cod                numeric(12,0),
  notas                    text,
  creado_en                timestamptz not null default now(),
  -- la asignación de grupo debe cumplir la regla del último dígito
  constraint grupo_por_digito check (
    (grupo = 'tratado' and right(pedido_id,1) in ('0','2','4','6','8')) or
    (grupo = 'control' and right(pedido_id,1) in ('1','3','5','7','9'))
  ),
  -- los controles nunca tienen contacto de Zynex
  constraint control_sin_contacto check (grupo = 'tratado' or canal = 'ninguno')
);

create index if not exists piloto_novedades_pedido_idx on public.piloto_novedades (pedido_id);
create index if not exists piloto_novedades_grupo_idx  on public.piloto_novedades (grupo);

-- Datos personales: activar RLS y no exponer a la clave anónima.
alter table public.piloto_novedades enable row level security;
-- (Sin políticas para anon. El acceso se hace con la service role desde el backend de Zynex.)

-- Validación de horario legal (Ley 2300 de 2023, art. 3), hora Colombia.
-- Los festivos se validan aparte, contra una tabla de festivos.
create or replace function public.es_horario_legal(ts timestamptz)
returns boolean language sql immutable as $$
  select case extract(isodow from ts at time zone 'America/Bogota')
    when 7 then false                                               -- domingo
    when 6 then (ts at time zone 'America/Bogota')::time between '08:00' and '15:00'
    else        (ts at time zone 'America/Bogota')::time between '07:00' and '19:00'
  end;
$$;

-- Vista de resultado (un registro por pedido)
create or replace view public.piloto_resultado as
select grupo,
       count(distinct pedido_id)                                       as pedidos,
       count(distinct pedido_id) filter (where entregado_d10)          as entregados_d10,
       round(100.0 * count(distinct pedido_id) filter (where entregado_d10)
             / nullif(count(distinct pedido_id),0), 1)                 as tasa_entrega_d10
from public.piloto_novedades
group by grupo;
```

> Nota: `right(pedido_id,1)` supone un ID numérico. Si el ID de Dropi trae prefijo o sufijo alfanumérico, se toma el último **dígito** con una expresión regular.

---

## 5. Cumplimiento legal

> Esto no es asesoría jurídica. Es la lectura operativa de las normas citadas, que conviene validar con un abogado antes de escalar más allá del piloto.

### 5.1 Ley 2300 de 2023 ("Dejen de fregar"), vigente desde el 10-oct-2023
- **Horario (art. 3):** lunes a viernes de **7:00 a. m. a 7:00 p. m.**, sábados de **8:00 a. m. a 3:00 p. m.**, **sin contacto los domingos ni los festivos**.
- **Frecuencia (art. 3):** una vez hay contacto directo, **no se puede contactar por varios canales en la misma semana ni más de una vez el mismo día**. *Corrección al brief:* la ley no dice "una vez por semana por canal". Lo que dice es "no varios canales en la misma semana y máximo una vez al día". Nuestra escalera (WhatsApp → llamada) usa más de un canal, por eso:
  - (a) la llamada por WhatsApp va **dentro del mismo canal WhatsApp** y solo con permiso expreso;
  - (b) el paso 3 (número colombiano) solo se usa si **no hubo contacto directo** por WhatsApp (sin respuesta);
  - (c) máximo 1 contacto saliente por día.
- **Canales (art. 2):** se contacta solo por los canales que el cliente dio al comprar (celular y WhatsApp del pedido).
- **Alcance:** la ley aplica directamente a la **cobranza** (arts. 1–3) y extiende el horario a los **mensajes comerciales y publicitarios** (art. 5, par. 3). La coordinación de la entrega de un pedido que el cliente hizo es información *relacionada con el bien comprado* y está cerca de la excepción del art. 8 ("información solicitada por el consumidor"), pero **para el piloto aplicamos el horario y la frecuencia de forma estricta**, como si nos aplicara. Por eso los guiones no hablan de dinero como "cobro", sino del pago contraentrega como dato de la entrega.
- **Festivos a bloquear en la ventana del piloto:** lunes **12-oct-2026** (Día de la Raza). Los domingos siempre quedan bloqueados. El siguiente festivo es el lunes 2-nov (Todos los Santos), que cae fuera de la ventana.
- Fuentes: [Ley 2300 de 2023, texto (Colpensiones, compilación)](https://normativa.colpensiones.gov.co/colpens/compilacion/docs/ley_2300_2023.htm) · [Ley 2300 de 2023, PDF (MinTIC)](https://normograma.mintic.gov.co/docs/pdf/ley_2300_2023.pdf) · [Ley 2300 de 2023, Rama Judicial](https://sidn.ramajudicial.gov.co/SIDN/NORMATIVA/TEXTOS_COMPLETOS/7_LEYES/LEYES%202023/Ley%202300%20de%202023%20(Derecho%20a%20la%20intimidad%20del%20consumidor).pdf) · [Xataka: entrada en vigencia y resumen](https://www.xataka.com.co/robotica-e-ia/hoy-entra-vigencia-ley-dejen-fregar-esto-que-debes-saber/amp)

### 5.2 Datos personales, consentimiento y grabación: Ley 1581 de 2012 (Habeas Data)
- **Base para contactar:** el cliente dio su teléfono para la entrega del pedido, así que usarlo para coordinar esa entrega está dentro de la finalidad. **No** se puede usar el piloto para ofrecer otros productos.
- **Grabación:** la voz es un dato personal y, si se usa para identificar a la persona, puede ser un dato biométrico (sensible). Por eso: **se avisa al inicio** que la llamada se graba y para qué ("constancia de lo acordado"), **se pide aceptación** (queda en `permiso_grabacion`) y, si el cliente no acepta, se sigue sin grabar.
- **Transparencia sobre la IA:** el asistente se presenta como **asistente virtual**. No se hace pasar por una persona.
- **Custodia:** las grabaciones y transcripciones van a almacenamiento privado (sin enlaces públicos), con RLS activo y **borrado a los 90 días** salvo que respalden una disputa con la transportadora.
- **Derechos:** si el cliente pide no ser contactado, se marca `pide_no_contacto` y no se le vuelve a contactar. Litper debe tener una política de tratamiento de datos publicada.
- Fuentes: [Ley 1581 de 2012 (Colombia Compra Eficiente, relatoría)](https://relatoria.colombiacompra.gov.co/normativa/ley-1581-de-2012/?print=pdf) · [Concepto SIC, radicado 17-018838](https://sedeelectronica.sic.gov.co/sites/default/files/normatividad/052017/Radicado_17-018838.pdf) · [Cartilla de contactabilidad (iNNpulsa)](https://www.innpulsacolombia.com/wp-content/uploads/2024/01/Welawyou-Cartilla-Marzo-FBD-contactabilidad-v2.pdf)

### 5.3 CRC: llamadas masivas, alertas y bloqueo (Resolución CRC 8308 de 2026)
- La CRC exige **registrar previamente los números** usados para campañas comerciales. Las llamadas publicitarias se etiquetan, y los patrones atípicos (**muchas llamadas cortas y repetidas desde la misma línea**) muestran la alerta **"llamada sospechosa"**. Se bloquean los números no asignados o habilitados solo para recibir.
- **Implicaciones para el piloto:**
  - (a) un solo número colombiano, **asignado y habilitado para salientes**, sin rotar números;
  - (b) volumen bajo y espaciado (≤ ~15 llamadas al día, sin rellamadas inmediatas);
  - (c) las llamadas de este piloto son de servicio (pedido en curso), **no publicitarias**, pero hay que confirmar con el operador si el número necesita registro;
  - (d) priorizar WhatsApp, donde el cliente ve la marca Litper.
- Fuentes: [El Colombiano: Resolución CRC 8308 de 2026](https://www.elcolombiano.com/tecnologia/llamadas-spam-colombia-medida-crc-resolucion-8308-2026-LN39529345) · [Valora Analitik: bloqueo de spam](https://www.valoraanalitik.com/?p=601903) · [Asuntos Legales: CRC endurece medidas](https://www.asuntoslegales.com.co/actualidad/crc-endurece-las-medidas-contra-el-fraude-movil-con-alertas-4448986) · [ENTER.CO: bloqueos y alertas CRC](https://www.enter.co/?p=585689)

### 5.4 Checklist operativo antes de cada contacto
- [ ] `es_horario_legal(now())` es verdadero y hoy no es festivo
- [ ] El cliente no tuvo contacto saliente hoy
- [ ] No hay contacto directo previo esta semana por otro canal (si lo hay, se sigue solo en ese canal)
- [ ] El cliente no está marcado `pide_no_contacto`
- [ ] El pedido es del grupo **tratado**

---

## 6. Qué necesita el CEO para arrancar (máx. 3) y costo

### 6.1 Tres decisiones o insumos
1. **Aprobación del diseño y de la regla de asignación** (par = tratado, impar = control), con la aceptación explícita de que los ~50 pedidos de control **no** reciben contacto de Zynex durante 10 días (sí reciben la gestión habitual). Costo de oportunidad aproximado: si Zynex rescata +27 pp, el control "deja de ganar" ~14 pedidos, unos COP 1,25M. Es el precio de saber si funciona.
2. **Acceso operativo a Dropi** de quien gestione las soluciones de novedad, más el **conteo de novedades por día de sep–oct** y el **histórico de desenlace de las novedades** (para fijar p1 y confirmar si el 31-oct es alcanzable).
3. **Un número de WhatsApp Business de Litper y una línea colombiana existente habilitada para salientes**, más **una persona de Litper** (1–2 h al día del 13 al 21 de octubre) como escalón humano y para cargar las soluciones en Dropi.

### 6.2 Costo estimado (sin suscripciones pagas nuevas)

| Rubro | Supuesto | Costo |
|---|---|---|
| WhatsApp (mensajes y llamadas) | App WhatsApp Business existente de Litper. Mensajes y llamadas por WhatsApp sin costo por mensaje | **COP 0** |
| Llamadas desde número colombiano | Plan móvil existente con minutos ilimitados a Colombia. ≤ 50 llamadas × ~3 min | **COP 0** (incluido en el plan) |
| Voz IA (si se usa el asistente de voz) | Créditos **ya existentes** de la cuenta de voz IA actual. ~50 llamadas × 3 min = ~150 min. *Supuesto: ~USD 0,08–0,10 por minuto si se pagara aparte* | **COP 0 en caja** (consume créditos existentes; ~USD 12–15 de valor) |
| Supabase | Plan actual (tabla pequeña, < 1 MB) | **COP 0** |
| Tiempo humano | 1–2 h al día × 7 días hábiles de una persona de Litper, más ~3 h de análisis | ~10–15 h internas |
| **Total en efectivo** | | **≈ COP 0** |

> Si no hay créditos de voz IA disponibles, el paso 2 lo hace la persona de Litper con el **mismo guion** (§3.3) y el piloto sigue siendo válido: mide el **protocolo de rescate**. La IA se valida después en el mismo diseño.

**Retorno esperado (ilustrativo):** con un efecto de +15 a +28 pp sobre 50 tratados, son **7–14 pedidos rescatados × ~COP 90.000 ≈ COP 0,6M–1,25M por ciclo**, con costo en efectivo cercano a cero.

---

### Anexo: plan de análisis (el 31-oct)
1. Exportar de Dropi el estado de cada `pedido_id` a día 10 → `estado_dropi_d10`, `entregado_d10`.
2. `select * from piloto_resultado;` → tasas por grupo.
3. Diferencia (tratado − control) en pp con IC 95 % (Wald / Newcombe) y prueba exacta de Fisher.
4. Chequeo de balance: transportadora, ciudad, tipo de novedad y valor COD por grupo.
5. Reporte de 1 página: tasa por grupo, diferencia con IC, pedidos y COP rescatados, novedades falsas detectadas (con evidencia para disputa) y aprendizajes del guion.
