import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "../components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import { Download, Users, Trash, WhatsappLogo } from "@phosphor-icons/react";

const STATUS_STYLES = {
  nuevo:       "border-blue-500/40 text-blue-300 bg-blue-500/10",
  contactado:  "border-yellow-500/40 text-yellow-300 bg-yellow-500/10",
  unido:       "border-green-500/40 text-green-300 bg-green-500/10",
  descartado:  "border-zinc-500/40 text-zinc-400 bg-zinc-500/10",
};

export default function VipLeadsPage() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/vip-leads");
      setLeads(r.data || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const patch = async (id, body) => {
    await api.patch(`/vip-leads/${id}`, body);
    load();
  };

  const del = async (id) => {
    if (!window.confirm("¿Eliminar lead?")) return;
    await api.delete(`/vip-leads/${id}`);
    load();
  };

  const exportXlsx = async () => {
    try {
      const res = await api.get("/vip-leads/export.xlsx", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "litper_vip_leads.xlsx";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Exportado.");
    } catch { toast.error("Error exportando."); }
  };

  const stats = {
    total: leads.length,
    nuevos: leads.filter((l) => l.status === "nuevo").length,
    unidos: leads.filter((l) => l.status === "unido").length,
  };

  return (
    <Layout
      title="Leads VIP"
      subtitle="Capturas del funnel de lanzamiento."
      actions={
        <Button onClick={exportXlsx} variant="outline" data-testid="vip-export-btn">
          <Download size={14} /> Exportar Excel
        </Button>
      }
    >
      <div className="grid grid-cols-3 gap-3 mb-6">
        <StatBox label="Total leads" value={stats.total} />
        <StatBox label="Nuevos" value={stats.nuevos} />
        <StatBox label="Unidos al VIP" value={stats.unidos} />
      </div>

      <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-900/40 backdrop-blur-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>WhatsApp</TableHead>
              <TableHead>País</TableHead>
              <TableHead>Volumen</TableHead>
              <TableHead>WA welcome</TableHead>
              <TableHead>Status</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={8} className="text-center text-zinc-500 py-6">Cargando…</TableCell></TableRow>}
            {!loading && leads.length === 0 && (
              <TableRow><TableCell colSpan={8} className="text-center text-zinc-500 py-8">Aún no hay leads.</TableCell></TableRow>
            )}
            {leads.map((l) => (
              <TableRow key={l.id} data-testid={`vip-lead-${l.id}`}>
                <TableCell className="text-xs font-mono text-zinc-400">
                  {new Date(l.created_at).toLocaleString("es-CO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                </TableCell>
                <TableCell className="text-sm">{l.nombre}</TableCell>
                <TableCell className="text-sm font-mono">
                  <a href={`https://wa.me/${l.whatsapp.replace(/\D/g, "")}`} target="_blank" rel="noreferrer"
                    className="text-emerald-300 hover:text-emerald-200">
                    <WhatsappLogo size={12} className="inline mr-1" />{l.whatsapp}
                  </a>
                </TableCell>
                <TableCell className="text-sm">{l.pais}</TableCell>
                <TableCell className="text-xs">{l.pedidos_semana || "—"}</TableCell>
                <TableCell className="text-xs">
                  {l.welcome_sent ? <Badge className="bg-green-500/10 text-green-300 border-green-500/40 border">enviado</Badge>
                                  : <Badge variant="outline" className="text-zinc-400">—</Badge>}
                </TableCell>
                <TableCell>
                  <Select value={l.status} onValueChange={(v) => patch(l.id, { status: v })}>
                    <SelectTrigger className={`h-7 text-xs w-32 ${STATUS_STYLES[l.status] || ""}`}
                      data-testid={`vip-status-${l.id}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="nuevo">Nuevo</SelectItem>
                      <SelectItem value="contactado">Contactado</SelectItem>
                      <SelectItem value="unido">Unido</SelectItem>
                      <SelectItem value="descartado">Descartado</SelectItem>
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300"
                    onClick={() => del(l.id)}><Trash size={14} /></Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Layout>
  );
}

function StatBox({ label, value }) {
  return (
    <div className="border border-zinc-800 rounded p-4 bg-zinc-900/60">
      <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">{label}</div>
      <div className="text-2xl font-semibold text-white mt-1 flex items-center gap-2">
        <Users size={16} className="text-zinc-400" /> {value}
      </div>
    </div>
  );
}
