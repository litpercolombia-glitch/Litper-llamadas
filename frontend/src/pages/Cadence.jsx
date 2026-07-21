import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Phone, ChatCircleText, CheckCircle, XCircle, Warning, ArrowsClockwise } from "@phosphor-icons/react";
import { toast } from "sonner";

const RESULTS = [
  { v: "confirmado",       label: "Confirmado",       icon: CheckCircle, tone: "text-green-400" },
  { v: "ya_recogio",       label: "Ya recogió",       icon: CheckCircle, tone: "text-emerald-400" },
  { v: "extension",        label: "Solicita extensión", icon: Warning,    tone: "text-yellow-400" },
  { v: "no_contesta",      label: "No contesta",      icon: XCircle,     tone: "text-zinc-400" },
  { v: "rechaza",          label: "Rechaza",          icon: XCircle,     tone: "text-red-400" },
  { v: "numero_incorrecto",label: "Número incorrecto", icon: XCircle,    tone: "text-red-400" },
];

function StatusDot({ status, result }) {
  const map = {
    pending:    "bg-zinc-600",
    dispatched: "bg-blue-500",
    done:       "bg-green-500",
    skipped:    "bg-zinc-800 border border-zinc-700",
  };
  const resMap = {
    confirmado: "bg-green-500", ya_recogio: "bg-emerald-500",
    extension: "bg-yellow-500", no_contesta: "bg-zinc-500",
    rechaza: "bg-red-500", numero_incorrecto: "bg-red-500",
  };
  const cls = (result && resMap[result]) || map[status] || "bg-zinc-600";
  return <span className={`w-3 h-3 rounded-full ${cls}`} />;
}

export default function CadencePage() {
  const [params] = useSearchParams();
  const [queueId, setQueueId] = useState(params.get("q") || "");
  const [queue, setQueue] = useState([]);
  const [plan, setPlan] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await api.get("/queue", { params: { limit: 500 } });
      setQueue(r.data || []);
      if (!queueId && r.data?.[0]) setQueueId(r.data[0].id);
    })();
  }, []);

  useEffect(() => {
    if (!queueId) return;
    (async () => {
      setLoading(true);
      try {
        const [q, s] = await Promise.all([
          api.get(`/queue/${queueId}`),
          api.get(`/calls/schedule/${queueId}`).catch(() => ({ data: null })),
        ]);
        setDetail(q.data);
        setPlan(s.data);
      } finally { setLoading(false); }
    })();
  }, [queueId]);

  const buildPlan = async () => {
    try {
      const r = await api.post("/calls/schedule", { queue_id: queueId });
      setPlan(r.data);
      toast.success("Cadencia generada");
    } catch (e) { toast.error(`Error: ${e.message}`); }
  };

  const registerResult = async (attempt_number, result) => {
    try {
      await api.post("/calls/attempt-result", { queue_id: queueId, attempt_number, result });
      const [q, s] = await Promise.all([
        api.get(`/queue/${queueId}`),
        api.get(`/calls/schedule/${queueId}`),
      ]);
      setDetail(q.data);
      setPlan(s.data);
      toast.success(`Intento #${attempt_number}: ${result}`);
    } catch (e) { toast.error(`Error: ${e.message}`); }
  };

  return (
    <Layout title="Cadencia de Contacto" subtitle="Plan de 5 intentos por pedido en oficina"
      actions={
        <div className="flex items-center gap-2">
          <Select value={queueId} onValueChange={setQueueId}>
            <SelectTrigger data-testid="cadence-select-queue" className="w-96 bg-zinc-900 border-zinc-800 rounded-sm text-sm">
              <SelectValue placeholder="Selecciona un pedido" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800 max-h-96">
              {queue.map(q => (
                <SelectItem key={q.id} value={q.id}>
                  {q.customer_name} · {q.carrier_name} · {q.city}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={buildPlan}
            data-testid="cadence-build-plan"
            className="bg-white text-black hover:bg-zinc-200 rounded-sm">
            <ArrowsClockwise size={14} className="mr-1" /> Regenerar plan
          </Button>
        </div>
      }
    >
      {loading && <div className="text-zinc-500 font-mono text-sm">Cargando…</div>}
      {detail && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="border border-zinc-800 bg-zinc-900/50 p-5 rounded-sm">
            <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-zinc-500 mb-1">Cliente</div>
            <div className="text-lg text-white">{detail.customer_name}</div>
            <div className="text-xs text-zinc-400 font-mono mt-1">{detail.customer_phone}</div>
            <div className="text-xs text-zinc-400 mt-2">{detail.address}, {detail.city}</div>
          </div>
          <div className="border border-zinc-800 bg-zinc-900/50 p-5 rounded-sm">
            <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-zinc-500 mb-1">Transportadora</div>
            <div className="text-lg text-white">{detail.carrier_name}</div>
            <div className="text-xs text-zinc-400 font-mono mt-1">Tracking: {detail.tracking_number || "—"}</div>
            <div className="text-xs text-zinc-400 mt-2">Reclamo máx: {detail.office_claim_max_days ?? "—"} días</div>
          </div>
          <div className="border border-zinc-800 bg-zinc-900/50 p-5 rounded-sm">
            <div className="text-[10px] uppercase tracking-[0.18em] font-mono text-zinc-500 mb-1">Estado</div>
            <div className="text-lg text-white uppercase font-mono tracking-wider">{detail.status}</div>
            <div className="text-xs text-zinc-400 mt-2">Intento actual: {detail.current_attempt}/5</div>
            <div className="text-xs text-zinc-400 font-mono mt-1">Próximo: {formatDateTime(detail.next_attempt_at)}</div>
          </div>
        </div>
      )}

      {!plan && detail && (
        <div className="border border-dashed border-zinc-800 p-8 text-center">
          <p className="text-zinc-400 mb-3">Aún no hay plan de cadencia para este pedido.</p>
          <Button onClick={buildPlan} className="bg-white text-black hover:bg-zinc-200 rounded-sm"
            data-testid="cadence-create-first">
            Generar plan de 5 intentos
          </Button>
        </div>
      )}

      {plan && (
        <div className="border border-zinc-800 bg-zinc-900/40 p-6">
          <h3 className="text-xs uppercase tracking-[0.15em] font-mono text-zinc-500 mb-6">Plan de 5 intentos</h3>
          <ol className="border-l-2 border-zinc-800 ml-3 space-y-6">
            {plan.attempts.map((a) => (
              <li key={a.attempt_number} className="relative pl-8" data-testid={`cadence-attempt-${a.attempt_number}`}>
                <div className="absolute -left-[9px] top-1"><StatusDot status={a.status} result={a.result} /></div>
                <div className="flex flex-wrap items-center gap-3 mb-2">
                  <span className="text-[10px] uppercase tracking-widest font-mono text-zinc-500">Intento</span>
                  <span className="text-xl font-mono text-white">#{a.attempt_number}</span>
                  <span className="border border-zinc-700 px-2 py-0.5 text-[10px] uppercase tracking-widest font-mono text-zinc-300 rounded-sm inline-flex items-center gap-1">
                    {a.channel === "call" ? <Phone size={12} /> : <ChatCircleText size={12} />} {a.channel}
                  </span>
                  <span className="text-[10px] uppercase tracking-widest font-mono text-zinc-500">
                    {a.window} · {formatDateTime(a.scheduled_at)}
                  </span>
                  <span className={`text-[10px] uppercase tracking-widest font-mono ml-auto ${
                    a.status === "done" ? "text-green-400"
                      : a.status === "dispatched" ? "text-blue-400"
                      : a.status === "skipped" ? "text-zinc-500" : "text-zinc-400"
                  }`}>
                    {a.status}{a.result ? ` · ${a.result}` : ""}
                  </span>
                </div>
                {a.status !== "done" && a.status !== "skipped" && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {RESULTS.map(({ v, label, icon: Ic, tone }) => (
                      <Button key={v} variant="outline"
                        onClick={() => registerResult(a.attempt_number, v)}
                        data-testid={`cadence-result-${a.attempt_number}-${v}`}
                        className={`border-zinc-700 bg-transparent hover:bg-zinc-800 rounded-sm h-8 text-xs ${tone}`}>
                        <Ic size={14} className="mr-1" /> {label}
                      </Button>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </Layout>
  );
}
