/**
 * Supuestos con los que el servidor calcula una cifra estimada (retorno,
 * devoluciones evitadas, costos). Regla de honestidad: una cifra que depende
 * de supuestos solo se muestra si la API los declara en `supuestos`, y siempre
 * va rotulada «Estimado» con sus supuestos al lado.
 *
 * Mapa campo por campo de lo que devuelve GET /metrics en `supuestos`:
 *   moneda, moneda_perfil, tipo_cambio_usd, tipo_cambio_definido, margen_pct,
 *   tasa_base_pct, minutos_por_llamada, costos_unitarios_usd{telefonia_por_min,
 *   voz_ia_por_min, whatsapp_por_msg, llm_por_1k_tokens},
 *   costo_por_recuperado_objetivo, nota  (son_estimaciones no se lista: es el rótulo).
 */
const num = (v, max = 4) => Number(v).toLocaleString("es", { maximumFractionDigits: max });
const isNum = (v) => typeof v === "number" && Number.isFinite(v);
const usd = (v) => `${num(v)} USD`;

const UNIT_COSTS = [
  ["telefonia_por_min", "Telefonía, por minuto"],
  ["voz_ia_por_min", "Voz, por minuto"],
  ["whatsapp_por_msg", "WhatsApp, por mensaje"],
  ["llm_por_1k_tokens", "Inteligencia artificial, por cada 1.000 tokens"],
];

/** Texto de la nota del servidor (aviso en lenguaje llano), si viene. */
export function supuestosNota(m) {
  const s = m?.supuestos;
  return s && typeof s === "object" && !Array.isArray(s) && typeof s.nota === "string" ? s.nota : "";
}

/** Busca `supuestos` en la respuesta de /metrics. Devuelve [[etiqueta, valor, clave]] o null. */
export function findSupuestos(m) {
  const s = m?.supuestos;
  if (!s || typeof s !== "object" || Array.isArray(s)) return null;
  const rows = [];
  const add = (key, label, value) => { if (value !== null && value !== undefined && value !== "") rows.push([label, value, key]); };

  const moneda = typeof s.moneda === "string" ? s.moneda.toUpperCase() : "";
  const perfil = typeof s.moneda_perfil === "string" ? s.moneda_perfil.toUpperCase() : "";
  add("moneda", "Moneda de estas cifras", moneda);
  if (perfil && perfil !== moneda) add("moneda_perfil", "Moneda de tu perfil", perfil);

  if (s.tipo_cambio_definido === false) {
    add("tipo_cambio", "Tipo de cambio",
        `No definido${perfil ? ` para ${perfil}` : ""}: cifras en USD`);
  } else if (moneda === "USD") {
    add("tipo_cambio", "Tipo de cambio", "No aplica: cifras en USD");
  } else if (isNum(s.tipo_cambio_usd)) {
    add("tipo_cambio", "Tipo de cambio", `1 USD = ${num(s.tipo_cambio_usd)} ${moneda}`.trim());
  }

  if (isNum(s.margen_pct)) add("margen_pct", "Margen sobre el valor recuperado", `${num(s.margen_pct)}%`);
  if (isNum(s.tasa_base_pct)) add("tasa_base_pct", "Pérdida habitual sin gestión (tasa base)", `${num(s.tasa_base_pct)}%`);
  if (isNum(s.minutos_por_llamada)) add("minutos_por_llamada", "Duración supuesta de cada llamada", `${num(s.minutos_por_llamada)} min`);

  const cu = s.costos_unitarios_usd && typeof s.costos_unitarios_usd === "object" ? s.costos_unitarios_usd : {};
  UNIT_COSTS.forEach(([k, label]) => { if (isNum(cu[k])) add(`costo_${k}`, `Costo unitario · ${label}`, usd(cu[k])); });

  if (isNum(s.costo_por_recuperado_objetivo)) {
    add("costo_objetivo", "Costo objetivo por caso recuperado",
        `${num(s.costo_por_recuperado_objetivo, 2)} ${moneda}`.trim());
  }
  // La nota no va como fila: se pinta completa debajo (ver SupuestosList).
  const nota = supuestosNota(m);
  if (rows.length === 0 && !nota) return null;
  rows.nota = nota;
  rows.sinTipoCambio = s.tipo_cambio_definido === false;
  return rows;
}

/** Moneda en la que el servidor dice que vienen las cifras, si lo dice. */
export function declaredCurrency(m) {
  const s = m?.supuestos || {};
  const c = m?.moneda || m?.currency || (typeof s === "object" && !Array.isArray(s) ? s.moneda : "");
  return typeof c === "string" ? c : "";
}

export function EstimadoBadge() {
  return (
    <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border border-yellow-500/20 bg-yellow-500/10 text-yellow-400 rounded-sm"
          data-testid="estimado-badge">
      Estimado
    </span>
  );
}

export default function SupuestosList({ rows, testId = "supuestos" }) {
  if (!rows) return null;
  return (
    <div className="mt-3 pt-3 border-t border-zinc-800" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1.5">
        Supuestos de este cálculo
      </div>
      {rows.sinTipoCambio && (
        <p className="text-[11px] text-yellow-300/90 border border-yellow-500/20 bg-yellow-500/10 rounded-sm px-2 py-1.5 mb-2 leading-snug"
           data-testid={`${testId}-sin-cambio`}>
          Tipo de cambio no definido: cifras en USD. El retorno no es confiable hasta definirlo.
        </p>
      )}
      <dl className="space-y-1">
        {rows.map(([label, value, key]) => (
          <div key={key} className="flex items-baseline justify-between gap-3 text-xs">
            <dt className="text-zinc-400">{label}</dt>
            <dd className="font-mono text-zinc-200 text-right break-words">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="text-[11px] text-zinc-500 mt-2 leading-snug" data-testid={`${testId}-nota`}>
        {rows.nota || "Es una estimación, no un resultado contable: cambia si cambian estos supuestos."}
      </p>
    </div>
  );
}
