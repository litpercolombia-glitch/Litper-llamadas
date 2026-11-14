import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import EmptyState from "../components/EmptyState";
import SupuestosList, { EstimadoBadge, findSupuestos, declaredCurrency } from "../components/Supuestos";
import { api } from "../lib/api";
import { formatMoney, useOrgProfile } from "../lib/assistant";
import { usePacks } from "../lib/packs";
import {
  CurrencyCircleDollar, TrendUp, TrendDown, Truck, MapPin, ChartLineUp,
  ListChecks, PhoneCall, Receipt,
} from "@phosphor-icons/react";

function StarCard({ label, value, sub, tone = "cyan", icon: Icon, testId, estimado = false, children }) {
  const bar = tone === "green" ? "from-emerald-500/40" :
              tone === "amber" ? "from-yellow-500/40" :
              tone === "red"   ? "from-red-500/40" :
              "from-cyan-500/40";
  return (
    <div data-testid={testId}
         className={`relative rounded-sm border border-zinc-800 bg-gradient-to-br ${bar} to-transparent p-6 overflow-hidden`}>
      <div className="flex items-center justify-between gap-2 mb-4">
        <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-400">{label}</div>
        <div className="flex items-center gap-2">
          {estimado && <EstimadoBadge />}
          {Icon && <Icon size={20} weight="duotone" className="text-white/70" />}
        </div>
      </div>
      <div className="text-4xl font-semibold text-white mb-2 break-words">{value}</div>
      {sub && <div className="text-xs text-zinc-400">{sub}</div>}
      {children}
    </div>
  );
}

function Breakdown({ title, icon: Icon, rows, money, testId }) {
  return (
    <div className="border border-zinc-800 rounded-sm p-5 bg-zinc-900/30" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-4 flex items-center gap-2">
        <Icon size={13} weight="duotone" /> {title}
      </div>
      {rows.length === 0 ? (
        <div className="text-xs text-zinc-500">Sin datos aún.</div>
      ) : (
        <div className="space-y-2">
          {rows.map(({ k, v }) => (
            <div key={k} className="flex items-center justify-between text-sm">
              <span className="text-zinc-300">{k}</span>
              <span className="text-white font-mono">{money(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const pct = (v) => (v == null || Number.isNaN(Number(v)) ? "—" : `${v}%`);

export default function MetricasPage() {
  const nav = useNavigate();
  const { loaded: packsLoaded, hasCod } = usePacks();
  const profile = useOrgProfile();
  const [m, setM] = useState(null);
  const [byCarrier, setByCarrier] = useState([]);
  const [byCity, setByCity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get("/metrics");
        setM(r.data);
      } catch { setError(true); }
      finally { setLoading(false); }
    })();
  }, []);

  // Desglose por transportadora y ciudad: solo con el paquete de contra entrega.
  useEffect(() => {
    if (!hasCod) return;
    (async () => {
      try {
        const q = await api.get("/queue", { params: { limit: 500 } });
        const carr = {}; const cty = {};
        (q.data || []).forEach((x) => {
          if (!(x.status === "confirmado" || x.status === "ya_recogio")) return;
          const c = x.carrier_name || x.carrier_slug || "—";
          const t = x.city || "—";
          carr[c] = (carr[c] || 0) + (x.total_amount || 0);
          cty[t]  = (cty[t]  || 0) + (x.total_amount || 0);
        });
        const top = (o) => Object.entries(o).map(([k, v]) => ({ k, v })).sort((a, b) => b.v - a.v).slice(0, 5);
        setByCarrier(top(carr)); setByCity(top(cty));
      } catch { /* el desglose es opcional */ }
    })();
  }, [hasCod]);

  const norte = m?.norte || {};
  const roi = norte.roi || {};
  const supuestos = findSupuestos(m);
  // Moneda: la que declare el servidor para estas cifras; si no, la del perfil del negocio.
  const currency = declaredCurrency(m) || profile?.moneda || "";
  const money = (v) => formatMoney(v, currency);

  const actividad = (m?.orders_total || 0) + (m?.queue_total || 0)
    + ((m?.funnel?.stages || []).reduce((n, s) => n + (s.count || 0), 0));
  const isEmpty = !loading && !error && actividad === 0;
  const ready = !loading && !error && !isEmpty && packsLoaded;

  return (
    <Layout
      title="Métricas"
      subtitle="Los resultados de tu operación, en números."
    >
      {loading && <div className="text-zinc-500 font-mono text-sm">Cargando…</div>}

      {error && (
        <div className="border border-red-500/30 bg-red-500/10 text-red-300 text-sm rounded-sm p-3" role="alert"
             data-testid="metricas-error">
          No pudimos cargar las métricas. Recarga la página para intentarlo de nuevo.
        </div>
      )}

      {isEmpty && (
        <EmptyState
          icon={ChartLineUp}
          testId="metricas-empty"
          title="Aún no hay métricas"
          description="Aquí verás los resultados de tu operación en cuanto haya actividad real: crea tu primer agente y ponlo a trabajar."
          action={hasCod
            ? { label: "Importar un archivo", onClick: () => nav("/app/pedidos?tab=importar") }
            : { label: "Crear un agente", onClick: () => nav("/app/ajustes?tab=agentes") }}
          prompt="Resume mis resultados de esta semana y dime qué puedo mejorar."
        />
      )}

      {ready && (
        <>
          {/* Cifras medidas (sin supuestos) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {hasCod ? (
              <>
                <StarCard label="Valor de pedidos recuperados"
                          value={money(roi.recovered_value || 0)}
                          sub="Suma del valor de los pedidos confirmados o recogidos."
                          tone="green" icon={CurrencyCircleDollar}
                          testId="star-recuperado" />
                <StarCard label="Tasa de recuperación"
                          value={pct(norte.recovery_rate?.value ?? 0)}
                          sub={`${m?.queue_total || 0} pedidos en el periodo`}
                          tone="cyan" icon={TrendUp}
                          testId="star-entrega" />
              </>
            ) : (
              <>
                <StarCard label="Pendientes en el periodo"
                          value={(m?.queue_total || 0).toLocaleString("es")}
                          sub={`${m?.operacion?.tasks_open ?? 0} tickets abiertos`}
                          tone="cyan" icon={ListChecks}
                          testId="star-pendientes" />
                <StarCard label="Llamadas contestadas"
                          value={pct(m?.funnel?.connect_rate?.value)}
                          sub="De las llamadas que hicieron tus agentes."
                          tone="green" icon={PhoneCall}
                          testId="star-contacto" />
              </>
            )}
            <StarCard label="Costo de uso del periodo"
                      value={money(m?.costos?.totals?.total)} estimado
                      sub="Estimado: llamadas, WhatsApp e inteligencia artificial."
                      tone="amber" icon={Receipt}
                      testId="star-costo" />
          </div>

          {/* Cifras estimadas: solo si la API declara sus supuestos */}
          {supuestos ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4" data-testid="metricas-estimados">
              <StarCard label="Retorno" estimado
                        value={money(roi.value)}
                        sub="Margen de lo recuperado menos el costo de uso."
                        tone={Number(roi.value) >= 0 ? "green" : "red"} icon={CurrencyCircleDollar}
                        testId="star-roi">
                <SupuestosList rows={supuestos} testId="star-roi-supuestos" />
              </StarCard>
              {hasCod && (
                <StarCard label="Devoluciones evitadas" estimado
                          value={pct(norte.rto_reduction?.value ?? 0)}
                          sub={`Tasa base ${norte.rto_reduction?.baseline ?? "—"}% → actual ${norte.rto_reduction?.current ?? "—"}%`}
                          tone="amber" icon={TrendDown}
                          testId="star-devoluciones">
                  <SupuestosList rows={supuestos} testId="star-devoluciones-supuestos" />
                </StarCard>
              )}
            </div>
          ) : (
            <p className="text-xs text-zinc-500 mt-4" data-testid="metricas-sin-estimados">
              El retorno no se muestra: es una cifra estimada y el servidor no envió los supuestos con los que se calcula.
            </p>
          )}

          {hasCod && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
              <Breakdown title="Valor recuperado por transportadora" icon={Truck}
                         rows={byCarrier} money={money} testId="breakdown-carrier" />
              <Breakdown title="Valor recuperado por ciudad" icon={MapPin}
                         rows={byCity} money={money} testId="breakdown-city" />
            </div>
          )}
        </>
      )}
    </Layout>
  );
}
