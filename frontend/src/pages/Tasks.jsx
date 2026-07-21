import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Plus, Check, ArrowsClockwise } from "@phosphor-icons/react";
import { toast } from "sonner";

const TASK_TYPES = [
  { v: "cambio_direccion", label: "Cambio de dirección" },
  { v: "factura",          label: "Factura" },
  { v: "mas_dias",         label: "Más días" },
  { v: "cambio_oficina",   label: "Cambio de oficina" },
  { v: "otro",             label: "Otro" },
];

const STATUSES = ["open", "in_progress", "resolved", "closed"];

export default function TasksPage() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ type: "otro", description: "", assigned_to: "" });

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/tasks", { params: { limit: 200 } });
      setTasks(r.data || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.description.trim()) return toast.error("Escribe una descripción.");
    try {
      await api.post("/tasks", { ...form, source: "agent" });
      setOpen(false);
      setForm({ type: "otro", description: "", assigned_to: "" });
      toast.success("Ticket creado");
      load();
    } catch (e) { toast.error(e.message); }
  };

  const update = async (id, patch) => {
    try {
      await api.patch(`/tasks/${id}`, patch);
      load();
    } catch (e) { toast.error(e.message); }
  };

  const filtered = tasks.filter(t => filter === "all" || t.status === filter);

  return (
    <Layout title="Tickets de Cliente" subtitle={`${filtered.length} tickets`}
      actions={
        <div className="flex items-center gap-2">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger data-testid="tasks-filter" className="w-40 bg-zinc-900 border-zinc-800 rounded-sm text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800">
              <SelectItem value="all">Todos</SelectItem>
              {STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={load} className="border-zinc-700 rounded-sm bg-transparent">
            <ArrowsClockwise size={14} />
          </Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-white text-black hover:bg-zinc-200 rounded-sm" data-testid="tasks-new">
                <Plus size={14} className="mr-1" /> Nuevo ticket
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-950 border-zinc-800 rounded-sm">
              <DialogHeader><DialogTitle>Nuevo ticket</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div>
                  <label className="text-xs uppercase tracking-widest font-mono text-zinc-500 mb-1 block">Tipo</label>
                  <Select value={form.type} onValueChange={(v) => setForm(f => ({ ...f, type: v }))}>
                    <SelectTrigger data-testid="tasks-form-type" className="bg-zinc-900 border-zinc-800 rounded-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-zinc-800">
                      {TASK_TYPES.map(t => <SelectItem key={t.v} value={t.v}>{t.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest font-mono text-zinc-500 mb-1 block">Descripción</label>
                  <Textarea data-testid="tasks-form-description"
                    className="bg-zinc-900 border-zinc-800 rounded-sm"
                    value={form.description}
                    onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
                    placeholder="Detalles del ticket…" />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-widest font-mono text-zinc-500 mb-1 block">Asignar a</label>
                  <Input data-testid="tasks-form-assignee"
                    className="bg-zinc-900 border-zinc-800 rounded-sm"
                    value={form.assigned_to}
                    onChange={(e) => setForm(f => ({ ...f, assigned_to: e.target.value }))}
                    placeholder="Ej. agente@litper.com" />
                </div>
                <Button onClick={create} data-testid="tasks-form-submit"
                  className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm">Crear</Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      }
    >
      <div className="border border-zinc-800 bg-zinc-900/40 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-[10px] uppercase tracking-[0.15em] font-mono text-zinc-500">
              <th className="text-left py-3 px-4">Estado</th>
              <th className="text-left py-3 px-4">Tipo</th>
              <th className="text-left py-3 px-4">Descripción</th>
              <th className="text-left py-3 px-4">Fuente</th>
              <th className="text-left py-3 px-4">Asignado</th>
              <th className="text-left py-3 px-4">Creado</th>
              <th className="py-3 px-4"></th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={7} className="py-6 text-center text-zinc-500 font-mono text-xs">Cargando…</td></tr>}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={7} className="py-8 text-center text-zinc-500 text-sm">Sin tickets.</td></tr>
            )}
            {filtered.map(t => (
              <tr key={t.id} className="data-row" data-testid={`task-row-${t.id}`}>
                <td className="py-2.5 px-4">
                  <Select value={t.status} onValueChange={(v) => update(t.id, { status: v })}>
                    <SelectTrigger className="h-7 w-32 bg-zinc-900 border-zinc-800 rounded-sm text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-zinc-800">
                      {STATUSES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </td>
                <td className="py-2.5 px-4 font-mono text-xs text-zinc-300 uppercase tracking-wider">{t.type}</td>
                <td className="py-2.5 px-4 text-zinc-200 max-w-md">{t.description}</td>
                <td className="py-2.5 px-4 font-mono text-xs text-zinc-500">{t.source}</td>
                <td className="py-2.5 px-4 text-xs text-zinc-400">{t.assigned_to || "—"}</td>
                <td className="py-2.5 px-4 font-mono text-xs text-zinc-500">{formatDateTime(t.created_at)}</td>
                <td className="py-2.5 px-4 text-right">
                  {t.status !== "resolved" && (
                    <Button size="sm" variant="ghost" onClick={() => update(t.id, { status: "resolved" })}
                      data-testid={`task-resolve-${t.id}`}
                      className="text-green-400 hover:text-green-300 hover:bg-zinc-800 h-7 rounded-sm">
                      <Check size={14} className="mr-1" /> Resolver
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
