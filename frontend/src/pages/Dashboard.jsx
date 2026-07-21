import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { CheckCircle, WarningCircle, Phone, ChatDots, ListChecks, Package as PackageIcon } from "@phosphor-icons/react";

function Kpi({ label, value, sub, icon: Icon, tone = "zinc", testId }) {
  const tones = {
    zinc: "border-zinc-800 bg-zinc-900/50",
    green: "border-green-500/30 bg-green-500/5",
    red: "border-red-500/30 bg-red-500/5",
    yellow: "border-yellow-500/30 bg-yellow-500/5",
  };
  return (
    <div data-testid={testId} className={`border rounded-sm p-5 ${tones[tone]} flex flex-col gap-3`}>
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-zinc-500">{label}</div>
        {Icon && <Icon size={18} weight="duotone" className="text-zinc-500" />}
      </div>
      <div className="text-3xl font-semibold font-mono text-white">{value}</div>
      {sub && <div className="text-xs text-zinc-500 font-mono">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const [m, setM] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancel = false;
    const load = async () => {
      try {
        const r = await api.get("/metrics");
        if (!cancel) setM(r.data);
      } catch (e) { if (!cancel) setErr(e.message); }
    };
    load();
    const id = setInterval(load, 15000);
    return () => { cancel = true; clearInterval(id); };
  }, []);

  return (
    <Layout title="Métricas Operativas" subtitle="Panorama en tiempo real de la operación COD">
      {err && <div className="border border-red-500/40 bg-red-500/10 p-4 mb-6 text-red-400 text-sm">Error: {err}</div>}
      {!m && !err && <div className="text-zinc-500 font-mono text-sm">Cargando métricas…</div>}
      {m && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <Kpi label="Cola Total"       value={m.queue_total}       sub={`${m.orders_total} pedidos totales`} icon={PackageIcon} testId="kpi-queue-total" />
            <Kpi label="Intentos 24h"     value={m.attempts_today}    sub={`${m.completed_today} completados`} icon={Phone} testId="kpi-attempts" />
            <Kpi label="Tasa de Contacto" value={`${m.contact_rate_pct}%`} sub="Confirmado / Ya recogió / Extensión" icon={CheckCircle} tone={m.contact_rate_pct > 50 ? "green" : "yellow"} testId="kpi-contact-rate" />
            <Kpi label="Tickets Abiertos" value={m.tasks_open}        sub="Requieren atención" icon={ListChecks} tone={m.tasks_open > 0 ? "yellow" : "zinc"} testId="kpi-tasks-open" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="border border-zinc-800 bg-zinc-900/50 p-5 rounded-sm lg:col-span-2">
              <h3 className="text-xs uppercase tracking-[0.15em] font-mono text-zinc-500 mb-4">Cola por Estado</h3>
              <div className="space-y-2">
                {Object.keys(m.queue_by_status).length === 0 && (
                  <div className="text-sm text-zinc-500">Sin datos.</div>
                )}
                {Object.entries(m.queue_by_status).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between border-b border-zinc-800 py-2">
                    <span className="text-sm text-zinc-300 font-mono uppercase tracking-wider">{k}</span>
                    <span className="text-lg font-mono text-white">{v}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="border border-zinc-800 bg-zinc-900/50 p-5 rounded-sm">
              <h3 className="text-xs uppercase tracking-[0.15em] font-mono text-zinc-500 mb-4">Mensajería 24h</h3>
              <div className="flex items-center gap-3 mb-4">
                <ChatDots size={28} weight="duotone" className="text-zinc-400" />
                <div>
                  <div className="text-3xl font-mono text-white">{m.messages_24h}</div>
                  <div className="text-xs text-zinc-500 font-mono">mensajes WhatsApp</div>
                </div>
              </div>
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500">
                Última actualización
              </div>
              <div className="text-xs text-zinc-400 font-mono mt-1">{formatDateTime(m.generated_at)}</div>
            </div>
          </div>
        </>
      )}
    </Layout>
  );
}
