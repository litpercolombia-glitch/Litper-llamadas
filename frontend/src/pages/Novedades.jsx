import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { Input } from "../components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { MagnifyingGlass } from "@phosphor-icons/react";

const CAT_CLS = {
  RECLAMO_EN_OFICINA: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  DEVOLUCION:         "bg-red-500/10 text-red-400 border-red-500/30",
  NOVEDAD:            "bg-orange-500/10 text-orange-400 border-orange-500/30",
  TRANSITO:           "bg-blue-500/10 text-blue-400 border-blue-500/30",
  ENTREGADO:          "bg-green-500/10 text-green-400 border-green-500/30",
  OTRO:               "bg-zinc-500/10 text-zinc-400 border-zinc-500/30",
};

export default function NovedadesPage() {
  const [rows, setRows] = useState([]);
  const [cat, setCat] = useState("all");
  const [q, setQ] = useState("");

  useEffect(() => { (async () => {
    const r = await api.get("/carriers/novedades");
    setRows(r.data || []);
  })(); }, []);

  const filtered = rows
    .filter(n => cat === "all" || n.categoria === cat)
    .filter(n => !q || [n.carrier, n.estatus_carrier, n.significado, n.accion]
      .join(" ").toLowerCase().includes(q.toLowerCase()));

  const cats = Array.from(new Set(rows.map(n => n.categoria))).sort();

  return (
    <Layout title="Novedades del Carrier" subtitle="Mapa de estatus del carrier → acción operativa"
      actions={
        <div className="flex items-center gap-2">
          <div className="relative">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <Input data-testid="novedades-search"
              className="pl-9 w-64 bg-zinc-900 border-zinc-800 rounded-sm text-sm"
              placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Select value={cat} onValueChange={setCat}>
            <SelectTrigger data-testid="novedades-cat" className="w-52 bg-zinc-900 border-zinc-800 rounded-sm text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800">
              <SelectItem value="all">Todas las categorías</SelectItem>
              {cats.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      }
    >
      <div className="border border-zinc-800 bg-zinc-900/40 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-[10px] uppercase tracking-[0.15em] font-mono text-zinc-500">
              <th className="text-left py-3 px-4">Categoría</th>
              <th className="text-left py-3 px-4">Carrier</th>
              <th className="text-left py-3 px-4">Estatus Carrier</th>
              <th className="text-left py-3 px-4">Estatus Dropi</th>
              <th className="text-left py-3 px-4">Significado</th>
              <th className="text-left py-3 px-4">Acción</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-zinc-500 text-sm">Sin novedades.</td></tr>
            )}
            {filtered.map(n => (
              <tr key={n.id} className="data-row" data-testid={`novedad-row-${n.id}`}>
                <td className="py-2.5 px-4">
                  <span className={`inline-block px-2 py-0.5 rounded-sm text-[10px] font-mono uppercase tracking-widest border ${CAT_CLS[n.categoria] || CAT_CLS.OTRO}`}>
                    {n.categoria}
                  </span>
                </td>
                <td className="py-2.5 px-4 text-zinc-200">{n.carrier}</td>
                <td className="py-2.5 px-4 font-mono text-xs text-zinc-300">{n.estatus_carrier}</td>
                <td className="py-2.5 px-4 font-mono text-xs text-zinc-400">{n.estatus_dropi || "—"}</td>
                <td className="py-2.5 px-4 text-zinc-300 text-xs max-w-md">{n.significado}</td>
                <td className="py-2.5 px-4 text-zinc-400 text-xs max-w-md">{n.accion}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
