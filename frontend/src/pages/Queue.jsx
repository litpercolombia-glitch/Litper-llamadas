import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import Semaforo from "../components/Semaforo";
import { api, formatCOP, formatDateTime, statusStyles } from "../lib/api";
import { MagnifyingGlass, ArrowRight, Funnel } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";

export default function QueuePage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [sem, setSem] = useState("all");
  const [status, setStatus] = useState("all");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const r = await api.get("/queue", { params: { limit: 500 } });
        setRows(r.data || []);
      } finally { setLoading(false); }
    })();
  }, []);

  const filtered = rows
    .filter(r => sem === "all" || r.semaphore === sem)
    .filter(r => status === "all" || r.status === status)
    .filter(r => {
      if (!q) return true;
      const t = q.toLowerCase();
      return (r.customer_name || "").toLowerCase().includes(t)
          || (r.customer_phone || "").includes(q)
          || (r.carrier_name || "").toLowerCase().includes(t)
          || (r.tracking_number || "").toLowerCase().includes(t);
    });

  return (
    <Layout title="Cola de Llamadas a Oficina" subtitle={`${filtered.length} de ${rows.length} pedidos`}
      actions={
        <div className="flex items-center gap-2">
          <div className="relative">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <Input data-testid="queue-search"
              className="pl-9 w-64 bg-zinc-900 border-zinc-800 rounded-sm text-sm"
              placeholder="Buscar cliente, tel, tracking…"
              value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Select value={sem} onValueChange={setSem}>
            <SelectTrigger data-testid="queue-filter-semaforo" className="w-40 bg-zinc-900 border-zinc-800 rounded-sm text-sm">
              <Funnel size={14} className="mr-1" />
              <SelectValue placeholder="Semáforo" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800">
              <SelectItem value="all">Todos los semáforos</SelectItem>
              <SelectItem value="rojo">Rojo</SelectItem>
              <SelectItem value="amarillo">Amarillo</SelectItem>
              <SelectItem value="verde">Verde</SelectItem>
              <SelectItem value="gris">Gris</SelectItem>
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger data-testid="queue-filter-status" className="w-40 bg-zinc-900 border-zinc-800 rounded-sm text-sm">
              <SelectValue placeholder="Estado" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800">
              <SelectItem value="all">Todos los estados</SelectItem>
              <SelectItem value="pending">Pendiente</SelectItem>
              <SelectItem value="in_progress">En progreso</SelectItem>
              <SelectItem value="confirmado">Confirmado</SelectItem>
              <SelectItem value="rechazado">Rechazado</SelectItem>
              <SelectItem value="ya_recogio">Ya recogió</SelectItem>
              <SelectItem value="extension">Extensión</SelectItem>
              <SelectItem value="escalado">Escalado</SelectItem>
              <SelectItem value="detenido">Detenido</SelectItem>
            </SelectContent>
          </Select>
        </div>
      }
    >
      <div className="border border-zinc-800 bg-zinc-900/40 overflow-x-auto">
        <table className="w-full text-sm" data-testid="queue-table">
          <thead>
            <tr className="border-b border-zinc-800 text-[10px] uppercase tracking-[0.15em] font-mono text-zinc-500">
              <th className="text-left py-3 px-4">Semáforo</th>
              <th className="text-left py-3 px-4">Cliente</th>
              <th className="text-left py-3 px-4">Teléfono</th>
              <th className="text-left py-3 px-4">Ciudad</th>
              <th className="text-left py-3 px-4">Transportadora</th>
              <th className="text-right py-3 px-4">Recaudo</th>
              <th className="text-right py-3 px-4">Días Restantes</th>
              <th className="text-left py-3 px-4">Estado</th>
              <th className="text-left py-3 px-4">Próximo</th>
              <th className="py-3 px-4"></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={10} className="py-6 text-center text-zinc-500 font-mono text-xs">Cargando…</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={10} className="py-8 text-center text-zinc-500 text-sm">Sin resultados.</td></tr>
            )}
            {filtered.map((r) => (
              <tr key={r.id} className="data-row" data-testid={`queue-row-${r.id}`}>
                <td className="py-2.5 px-4"><Semaforo value={r.semaphore} /></td>
                <td className="py-2.5 px-4 text-zinc-200">{r.customer_name || "-"}</td>
                <td className="py-2.5 px-4 font-mono text-zinc-400 text-xs">{r.customer_phone || "-"}</td>
                <td className="py-2.5 px-4 text-zinc-400">{r.city || "-"}</td>
                <td className="py-2.5 px-4 text-zinc-200">{r.carrier_name || r.carrier_slug}</td>
                <td className="py-2.5 px-4 font-mono text-right text-zinc-200">{formatCOP(r.total_amount, r.currency)}</td>
                <td className="py-2.5 px-4 font-mono text-right text-zinc-300">
                  {r.days_left ?? "—"}
                </td>
                <td className="py-2.5 px-4">
                  <span className={`inline-block px-2 py-0.5 rounded-sm text-[11px] font-mono uppercase tracking-wider ${statusStyles[r.status] || "bg-zinc-800 text-zinc-300"}`}>
                    {r.status}
                  </span>
                </td>
                <td className="py-2.5 px-4 font-mono text-xs text-zinc-400">{formatDateTime(r.next_attempt_at)}</td>
                <td className="py-2.5 px-4 text-right">
                  <Link to={`/cadence?q=${r.id}`}>
                    <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-sm h-7"
                      data-testid={`queue-open-cadence-${r.id}`}>
                      Ver <ArrowRight size={14} className="ml-1" />
                    </Button>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
