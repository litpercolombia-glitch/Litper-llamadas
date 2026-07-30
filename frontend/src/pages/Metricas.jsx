import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import HowItWorks from "../components/HowItWorks";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import {
  CurrencyCircleDollar, TrendUp, Package, TrendDown,
  Truck, MapPin, ArrowRight, ChartLineUp,
} from "@phosphor-icons/react";

function fmtCOP(v) {
  if (v == null || Number.isNaN(v)) return "$0";
  return `$${Math.round(v).toLocaleString("es-CO")}`;
}

function StarCard({ label, value, sub, tone = "cyan", icon: Icon, testId }) {
  const bar = tone === "green" ? "from-emerald-500/40" :
              tone === "amber" ? "from-yellow-500/40" :
              tone === "red"   ? "from-red-500/40" :
              "from-cyan-500/40";
  return (
    <div data-testid={testId}
         className={`relative rounded-sm border border-zinc-800 bg-gradient-to-br ${bar} to-transparent p-6 overflow-hidden`}>
      <div className="flex items-center justify-between mb-4">
        <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-400">{label}</div>
        {Icon && <Icon size={20} weight="duotone" className="text-white/70" />}
      </div>
      <div className="text-4xl font-semibold text-white mb-2">{value}</div>
      {sub && <div className="text-xs text-zinc-400">{sub}</div>}
    </div>
  );
}

function EmptyState({ onImport, onOpenCopilot }) {
  return (
    <div className="border border-dashed border-zinc-800 rounded-sm p-10 text-center bg-zinc-900/30"
         data-testid="metricas-empty">
      <ChartLineUp size={40} className="mx-auto mb-4 text-zinc-600" weight="duotone" />
      <h3 className="text-lg font-semibold text-white mb-1">Aún no hay métricas</h3>
      <p className="text-sm text-zinc-400 max-w-md mx-auto mb-5">
        Corre tu primer rescate para ver <b className="text-white">$ recuperado</b>, entrega efectiva y
        devoluciones evitadas.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        <Button onClick={onImport} className="btn-cta-grad rounded-sm" data-testid="metricas-cta-importar">
          Importar Excel de Dropi <ArrowRight size={14} className="ml-1" />
        </Button>
        <Button onClick={onOpenCopilot} variant="outline"
                className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800"
                data-testid="metricas-cta-copilot">
          Abrir Copilot
        </Button>
      </div>
    </div>
  );
}

export default function MetricasPage() {
  const nav = useNavigate();
  const [m, setM] = useState(null);
  const [byCarrier, setByCarrier] = useState([]);
  const [byCity, setByCity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get("/metrics");
        setM(r.data);
        // Group orders by carrier/city on the client from queue.
        const q = await api.get("/queue", { params: { limit: 500 } });
        const rows = q.data || [];
        const carr = {}; const cty = {};
        rows.forEach((x) => {
          const isRec = x.status === "confirmado" || x.status === "ya_recogio";
          if (!isRec) return;
          const c = x.carrier_name || x.carrier_slug || "—";
          const t = x.city || "—";
          carr[c] = (carr[c] || 0) + (x.total_amount || 0);
          cty[t]  = (cty[t]  || 0) + (x.total_amount || 0);
        });
        setByCarrier(Object.entries(carr).map(([k, v]) => ({ k, v })).sort((a, b) => b.v - a.v).slice(0, 5));
        setByCity(Object.entries(cty).map(([k, v]) => ({ k, v })).sort((a, b) => b.v - a.v).slice(0, 5));
      } finally { setLoading(false); }
    })();
  }, []);

  const norte = m?.norte || {};
  const roi = norte.roi_cop || {};
  const recovered = roi.recovered_value_cop || 0;
  const recoveryRate = norte.recovery_rate?.value || 0;
  const rtoReduction = norte.rto_reduction?.value || 0;
  const ordersTotal = m?.orders_total || 0;

  const isEmpty = !loading && ordersTotal === 0;

  return (
    <Layout
      title="Métricas"
      subtitle="Solo lo que mueve la aguja: $ recuperado, entrega efectiva, devoluciones evitadas."
    >
      <HowItWorks
        testIdPrefix="metricas-howitworks"
        intro="Solo métricas de North Star: cuánto dinero recuperó Lyan, cuál es tu tasa de entrega efectiva y cuántas devoluciones evitaste."
        steps={[
          "Corre tu primer rescate — la cascada de 5 agentes activa las métricas.",
          "Ves el $ recuperado por transportadora y por ciudad.",
          "Compara semana a semana para probar el impacto real.",
        ]}
      />
      {loading && <div className="text-zinc-500 font-mono text-sm">Cargando…</div>}

      {isEmpty && (
        <EmptyState
          onImport={() => nav("/app/pedidos?tab=importar")}
          onOpenCopilot={() => nav("/app")}
        />
      )}

      {!loading && !isEmpty && (
        <>
          {/* North Star */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StarCard label="$ Recuperado (30 días)"
                      value={fmtCOP(recovered)}
                      sub={`${recoveryRate}% de tasa de recuperación`}
                      tone="green" icon={CurrencyCircleDollar}
                      testId="star-recuperado" />
            <StarCard label="Entrega efectiva"
                      value={`${recoveryRate}%`}
                      sub={`${m?.queue_total || 0} pedidos activos`}
                      tone="cyan" icon={TrendUp}
                      testId="star-entrega" />
            <StarCard label="Devoluciones evitadas"
                      value={`${rtoReduction}%`}
                      sub={`baseline ${norte.rto_reduction?.baseline || 0}% → ${norte.rto_reduction?.current || 0}%`}
                      tone="amber" icon={TrendDown}
                      testId="star-devoluciones" />
          </div>

          {/* Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
            <div className="border border-zinc-800 rounded-sm p-5 bg-zinc-900/30" data-testid="breakdown-carrier">
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-4 flex items-center gap-2">
                <Truck size={13} weight="duotone" /> $ recuperado por transportadora
              </div>
              {byCarrier.length === 0 ? (
                <div className="text-xs text-zinc-500">Sin recuperaciones aún.</div>
              ) : (
                <div className="space-y-2">
                  {byCarrier.map(({ k, v }) => (
                    <div key={k} className="flex items-center justify-between text-sm">
                      <span className="text-zinc-300">{k}</span>
                      <span className="text-white font-mono">{fmtCOP(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="border border-zinc-800 rounded-sm p-5 bg-zinc-900/30" data-testid="breakdown-city">
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-4 flex items-center gap-2">
                <MapPin size={13} weight="duotone" /> $ recuperado por ciudad
              </div>
              {byCity.length === 0 ? (
                <div className="text-xs text-zinc-500">Sin recuperaciones aún.</div>
              ) : (
                <div className="space-y-2">
                  {byCity.map(({ k, v }) => (
                    <div key={k} className="flex items-center justify-between text-sm">
                      <span className="text-zinc-300">{k}</span>
                      <span className="text-white font-mono">{fmtCOP(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </Layout>
  );
}
