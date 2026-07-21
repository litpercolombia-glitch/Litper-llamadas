import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line, Legend, FunnelChart, Funnel, LabelList, Cell,
} from "recharts";
import {
  ArrowsClockwise, TrendUp, TrendDown, CurrencyDollar, Package,
  Phone, ChatCircleDots, ArrowsIn, Warning,
} from "@phosphor-icons/react";

const STATUS_TONE = {
  green:  "border-green-500/40 bg-green-500/5 text-green-400",
  amber:  "border-yellow-500/40 bg-yellow-500/5 text-yellow-400",
  red:    "border-red-500/40 bg-red-500/5 text-red-400",
  gris:   "border-zinc-700 bg-zinc-900/50 text-zinc-400",
};

function fmtCOP(v) {
  if (v == null) return "—";
  return `$${Math.round(v).toLocaleString("es-CO")}`;
}
function fmtNum(v, digits = 0) {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString("es-CO", { maximumFractionDigits: digits });
}

function Kpi({ label, value, unit, status = "gris", target, targetMax, sub, icon: Icon, testId, big = false }) {
  const tone = STATUS_TONE[status] || STATUS_TONE.gris;
  return (
    <div data-testid={testId}
      className={`tilt-card metal-surface ${big ? "p-6" : "p-5"} ${tone.split(" ").slice(2).join(" ")}`}
      style={{
        borderColor: status === "green"  ? "rgba(48,209,88,0.35)"
                   : status === "amber"  ? "rgba(255,159,10,0.35)"
                   : status === "red"    ? "rgba(255,69,58,0.35)"
                   : undefined,
      }}>
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-zinc-500">{label}</div>
        {Icon && <Icon size={16} weight="duotone" className="text-zinc-500" />}
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <div className={`${big ? "text-4xl" : "text-3xl"} font-semibold font-mono ${tone.split(" ").pop()}`}>{value}</div>
        {unit && <div className="text-sm text-zinc-500 font-mono">{unit}</div>}
      </div>
      {(target || targetMax) && (
        <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
          ref: {target ? `≥${target}${unit || "%"}` : `≤${targetMax}${unit === "COP" ? " COP" : unit || "%"}`}
        </div>
      )}
      {sub && <div className="text-xs text-zinc-400 font-mono mt-1">{sub}</div>}
    </div>
  );
}

function SectionHeader({ letter, title, subtitle }) {
  return (
    <div className="flex items-center gap-3 mt-8 mb-4">
      <div className="w-8 h-8 flex items-center justify-center border border-zinc-700 rounded-sm font-mono text-sm text-white">
        {letter}
      </div>
      <div>
        <h3 className="text-sm uppercase tracking-[0.15em] font-mono text-white">{title}</h3>
        {subtitle && <p className="text-xs text-zinc-500 font-mono">{subtitle}</p>}
      </div>
    </div>
  );
}

const SEM_COLORS = { rojo: "#ef4444", amarillo: "#eab308", verde: "#22c55e", gris: "#71717a" };
const COST_COLORS = { twilio_cop: "#3b82f6", elevenlabs_cop: "#a855f7",
                     whatsapp_cop: "#22c55e", llm_cop: "#f59e0b" };
const COST_LABEL = { twilio_cop: "Twilio", elevenlabs_cop: "ElevenLabs",
                    whatsapp_cop: "WhatsApp", llm_cop: "LLM" };

export default function DashboardPage() {
  const [m, setM] = useState(null);
  const [err, setErr] = useState(null);
  const [carriers, setCarriers] = useState([]);
  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const [filters, setFilters] = useState({ date_from: monthAgo, date_to: today, country: "all", carrier_slug: "all" });

  const load = async () => {
    setErr(null);
    try {
      const params = { date_from: filters.date_from, date_to: filters.date_to };
      if (filters.country !== "all") params.country = filters.country;
      if (filters.carrier_slug !== "all") params.carrier_slug = filters.carrier_slug;
      const r = await api.get("/metrics", { params });
      setM(r.data);
    } catch (e) { setErr(e.message); }
  };

  useEffect(() => { (async () => {
    const r = await api.get("/carriers");
    setCarriers(r.data || []);
  })(); }, []);

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filters]);

  const funnelData = useMemo(() => {
    if (!m) return [];
    return m.funnel.stages.map((s, i) => ({
      name: s.name, value: s.count,
      fill: ["#0ea5e9", "#3b82f6", "#8b5cf6", "#22c55e", "#10b981"][i] || "#71717a",
    }));
  }, [m]);

  return (
    <Layout
      title="Métricas Operativas"
      subtitle="KPIs de la operación COD · llamadas a oficina"
      actions={
        <div className="flex items-center gap-2">
          <Input type="date" value={filters.date_from}
            data-testid="metrics-date-from"
            onChange={(e) => setFilters(f => ({ ...f, date_from: e.target.value }))}
            className="w-40 bg-zinc-900 border-zinc-800 rounded-sm text-xs font-mono" />
          <span className="text-zinc-600">→</span>
          <Input type="date" value={filters.date_to}
            data-testid="metrics-date-to"
            onChange={(e) => setFilters(f => ({ ...f, date_to: e.target.value }))}
            className="w-40 bg-zinc-900 border-zinc-800 rounded-sm text-xs font-mono" />
          <Select value={filters.country}
            onValueChange={(v) => setFilters(f => ({ ...f, country: v }))}>
            <SelectTrigger data-testid="metrics-country" className="w-28 bg-zinc-900 border-zinc-800 rounded-sm text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800">
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="CO">Colombia</SelectItem>
              <SelectItem value="EC">Ecuador</SelectItem>
              <SelectItem value="CL">Chile</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filters.carrier_slug}
            onValueChange={(v) => setFilters(f => ({ ...f, carrier_slug: v }))}>
            <SelectTrigger data-testid="metrics-carrier" className="w-44 bg-zinc-900 border-zinc-800 rounded-sm text-xs">
              <SelectValue placeholder="Transportadora" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800 max-h-72">
              <SelectItem value="all">Todas</SelectItem>
              {carriers.map(c => <SelectItem key={c.slug} value={c.slug}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={load} className="border-zinc-700 rounded-sm bg-transparent">
            <ArrowsClockwise size={14} />
          </Button>
        </div>
      }
    >
      {err && <div className="border border-red-500/40 bg-red-500/10 p-4 mb-6 text-red-400 text-sm">Error: {err}</div>}
      {!m && !err && <div className="text-zinc-500 font-mono text-sm">Cargando métricas…</div>}
      {m && (
        <>
          {/* ---------- GROUP A · NORTE ---------- */}
          <SectionHeader letter="A" title="NORTE" subtitle="KPIs de negocio" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Kpi label="Tasa de Recuperación" value={`${m.norte.recovery_rate.value}%`}
              status={m.norte.recovery_rate.status} target={m.norte.recovery_rate.target}
              icon={TrendUp} sub={`${m.queue_total} pedidos en rango`} testId="kpi-recovery" big />
            <Kpi label="RTO Evitado" value={`${m.norte.rto_reduction.value}%`}
              status={m.norte.rto_reduction.status} target={15}
              icon={TrendDown} sub={`baseline ${m.norte.rto_reduction.baseline}% → actual ${m.norte.rto_reduction.current}%`}
              testId="kpi-rto" big />
            <Kpi label="Costo por Recuperado" value={fmtCOP(m.norte.cpr_cop.value)} unit="COP"
              status={m.norte.cpr_cop.status} targetMax={5000}
              icon={CurrencyDollar}
              sub={`Costo total: ${fmtCOP(m.norte.roi_cop.total_cost_cop)}`} testId="kpi-cpr" big />
            <Kpi label="ROI / Margen Neto" value={fmtCOP(m.norte.roi_cop.value)} unit="COP"
              status={m.norte.roi_cop.status}
              icon={Package}
              sub={`Recuperado: ${fmtCOP(m.norte.roi_cop.recovered_value_cop)}`} testId="kpi-roi" big />
          </div>

          {/* Trend 14 días */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
            <div className="border border-zinc-800 bg-zinc-900/40 p-5 rounded-sm" data-testid="chart-recovery-trend">
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3">
                Tasa de recuperación · últimos 14 días
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={m.trend.recovery_rate_14d}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 10, fontFamily: "IBM Plex Mono" }} tickFormatter={(d) => d.slice(5)} />
                  <YAxis tick={{ fill: "#71717a", fontSize: 10, fontFamily: "IBM Plex Mono" }} unit="%" />
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #27272a", fontSize: 12 }} />
                  <Line type="monotone" dataKey="value" stroke="#22c55e" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="border border-zinc-800 bg-zinc-900/40 p-5 rounded-sm" data-testid="chart-cpr-trend">
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3">
                Costo por recuperado (COP) · últimos 14 días
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={m.trend.cpr_14d}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 10, fontFamily: "IBM Plex Mono" }} tickFormatter={(d) => d.slice(5)} />
                  <YAxis tick={{ fill: "#71717a", fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #27272a", fontSize: 12 }} />
                  <Line type="monotone" dataKey="value" stroke="#a855f7" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ---------- GROUP B · EMBUDO ---------- */}
          <SectionHeader letter="B" title="Embudo de Contacto" subtitle="Programados → Marcados → Contactados → Confirmados → Recogidos" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 border border-zinc-800 bg-zinc-900/40 p-5 rounded-sm" data-testid="chart-funnel">
              <ResponsiveContainer width="100%" height={220}>
                <FunnelChart>
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #27272a", fontSize: 12 }} />
                  <Funnel dataKey="value" data={funnelData} isAnimationActive>
                    <LabelList position="right" fill="#f4f4f5" stroke="none"
                      dataKey="name" style={{ fontFamily: "IBM Plex Mono", fontSize: 11 }} />
                    <LabelList position="center" fill="#f4f4f5" stroke="none"
                      dataKey="value" style={{ fontFamily: "IBM Plex Mono", fontSize: 14, fontWeight: 600 }} />
                  </Funnel>
                </FunnelChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Kpi label="Connect Rate" value={`${m.funnel.connect_rate.value}%`}
                status={m.funnel.connect_rate.status} target={25} icon={Phone} testId="kpi-connect" />
              <Kpi label="Right Party" value={`${m.funnel.right_party.value}%`}
                status={m.funnel.right_party.status} target={60} testId="kpi-rpc" />
              <Kpi label="Confirmación" value={`${m.funnel.confirmation_rate.value}%`}
                status={m.funnel.confirmation_rate.status} target={40} testId="kpi-confirm" />
              <Kpi label="Intentos → contacto" value={fmtNum(m.funnel.avg_attempts_to_contact.value, 2)}
                status={m.funnel.avg_attempts_to_contact.status} targetMax={3} unit="" testId="kpi-attempts-avg" />
              <Kpi label="No contesta" value={`${m.funnel.no_answer_pct.value}%`}
                status="gris" testId="kpi-noanswer" />
              <Kpi label="# incorrecto" value={`${m.funnel.wrong_number_pct.value}%`}
                status={m.funnel.wrong_number_pct.status} testId="kpi-wrong" />
            </div>
          </div>

          {/* ---------- GROUP C · WHATSAPP ---------- */}
          <SectionHeader letter="C" title="WhatsApp Fallback" subtitle="Chatea Pro · outbound + inbound" />
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <Kpi label="Enviados" value={fmtNum(m.whatsapp.sent)} icon={ChatCircleDots} testId="kpi-wa-sent" />
            <Kpi label="Entregados" value={fmtNum(m.whatsapp.delivered)} testId="kpi-wa-delivered" />
            <Kpi label="Read Rate" value={`${m.whatsapp.read_rate.value}%`}
              status={m.whatsapp.read_rate.status} target={80} testId="kpi-wa-read" />
            <Kpi label="Response Rate" value={`${m.whatsapp.response_rate.value}%`}
              status={m.whatsapp.response_rate.status} target={15} testId="kpi-wa-response" />
            <Kpi label="→ Confirmación" value={`${m.whatsapp.conversion_to_confirmation.value}%`}
              status={m.whatsapp.conversion_to_confirmation.status} target={30} testId="kpi-wa-conv" />
            <Kpi label="Resp. promedio" value={fmtNum(m.whatsapp.avg_response_min.value, 1)} unit="min"
              status={m.whatsapp.avg_response_min.status} targetMax={5}
              sub="<5min = 21x conv." testId="kpi-wa-time" />
          </div>

          {/* ---------- GROUP D · OPERACIÓN / URGENCIA ---------- */}
          <SectionHeader letter="D" title="Operación / Urgencia" subtitle="Estado actual de la cola" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="border border-zinc-800 bg-zinc-900/40 p-5 rounded-sm">
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3">Pedidos por semáforo</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={m.operacion.by_semaphore}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: "#71717a", fontSize: 11, fontFamily: "IBM Plex Mono" }} />
                  <YAxis tick={{ fill: "#71717a", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #27272a", fontSize: 12 }} />
                  <Bar dataKey="count" data-testid="chart-semaforo">
                    {m.operacion.by_semaphore.map((s) => (
                      <Cell key={s.name} fill={SEM_COLORS[s.name] || "#71717a"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="border border-zinc-800 bg-zinc-900/40 p-5 rounded-sm">
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3">Vencen HOY / MAÑANA</div>
              {(m.operacion.vencen_hoy.length + m.operacion.vencen_manana.length) === 0 && (
                <div className="text-xs text-zinc-500 font-mono">Sin vencimientos inminentes 🎉</div>
              )}
              <table className="w-full text-xs">
                <tbody>
                  {m.operacion.vencen_hoy.map((v) => (
                    <tr key={"h" + v.carrier_slug} className="border-b border-zinc-800/50">
                      <td className="py-1.5 text-red-400 font-mono uppercase">HOY</td>
                      <td className="py-1.5 text-zinc-200">{v.carrier_slug}</td>
                      <td className="py-1.5 text-right font-mono text-white">{v.count}</td>
                    </tr>
                  ))}
                  {m.operacion.vencen_manana.map((v) => (
                    <tr key={"m" + v.carrier_slug} className="border-b border-zinc-800/50">
                      <td className="py-1.5 text-yellow-400 font-mono uppercase">MAÑANA</td>
                      <td className="py-1.5 text-zinc-200">{v.carrier_slug}</td>
                      <td className="py-1.5 text-right font-mono text-white">{v.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <Kpi label="Escalados" value={`${m.operacion.escalation_rate.value}%`}
                  status={m.operacion.escalation_rate.status} targetMax={20} testId="kpi-escalation" />
                <Kpi label="Tickets abiertos" value={fmtNum(m.operacion.tasks_open)}
                  icon={Warning} testId="kpi-tasks" />
              </div>
            </div>
            <div className="border border-zinc-800 bg-zinc-900/40 p-5 rounded-sm">
              <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3">Tickets por tipo</div>
              {m.operacion.tasks_by_type.length === 0 && (
                <div className="text-xs text-zinc-500 font-mono">Sin tickets en el rango.</div>
              )}
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={m.operacion.tasks_by_type} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
                  <XAxis type="number" tick={{ fill: "#71717a", fontSize: 10 }} />
                  <YAxis type="category" dataKey="type" width={110}
                    tick={{ fill: "#a1a1aa", fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #27272a", fontSize: 12 }} />
                  <Bar dataKey="count" fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ---------- GROUP E · COSTOS ---------- */}
          <SectionHeader letter="E" title="Costos por Canal" subtitle="Barras apiladas por día · totales del rango" />
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="grid grid-cols-1 gap-3">
              <Kpi label="Total del rango" value={fmtCOP(m.costos.totals.total_cop)} unit="COP" testId="kpi-cost-total" big />
              <Kpi label="Twilio" value={fmtCOP(m.costos.totals.twilio_cop)} unit="COP"
                sub={`${fmtNum(m.costos.totals.minutes, 1)} min`} testId="kpi-cost-twilio" />
              <Kpi label="ElevenLabs" value={fmtCOP(m.costos.totals.elevenlabs_cop)} unit="COP" testId="kpi-cost-eleven" />
              <Kpi label="WhatsApp" value={fmtCOP(m.costos.totals.whatsapp_cop)} unit="COP"
                sub={`${fmtNum(m.costos.totals.messages)} mensajes`} testId="kpi-cost-wa" />
              <Kpi label="LLM" value={fmtCOP(m.costos.totals.llm_cop)} unit="COP" testId="kpi-cost-llm" />
            </div>
            <div className="lg:col-span-3 border border-zinc-800 bg-zinc-900/40 p-5 rounded-sm">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={m.costos.days} data-testid="chart-costos">
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)}
                    tick={{ fill: "#71717a", fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                  <YAxis tick={{ fill: "#71717a", fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                  <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #27272a", fontSize: 12 }}
                    formatter={(v, k) => [fmtCOP(v), COST_LABEL[k] || k]} />
                  <Legend wrapperStyle={{ fontSize: 11, fontFamily: "IBM Plex Mono" }}
                    formatter={(k) => COST_LABEL[k] || k} />
                  {Object.keys(COST_COLORS).map(k => (
                    <Bar key={k} dataKey={k} stackId="a" fill={COST_COLORS[k]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="mt-8 text-[10px] font-mono text-zinc-600 text-right">
            Generado: {formatDateTime(m.generated_at)} · Filtros: {m.filters.date_from} → {m.filters.date_to}
            {m.filters.country ? ` · ${m.filters.country}` : ""}
            {m.filters.carrier_slug ? ` · ${m.filters.carrier_slug}` : ""}
          </div>
        </>
      )}
    </Layout>
  );
}
