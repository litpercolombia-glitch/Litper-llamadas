import { useCallback, useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { ChartBar, ArrowsClockwise, Copy } from "@phosphor-icons/react";

/** Resultados del formulario de descubrimiento: cada barra abre las respuestas que la forman. */
const TXT = {
  pedidos_dia: { menos_20: "Menos de 20", "20_100": "20 a 100", "100_500": "100 a 500", mas_500: "Más de 500" },
  dolores: { confirmar: "Confirmar pedidos", novedades: "Novedades", oficina: "Pedidos en oficina", devoluciones: "Devoluciones", chats: "Responder chats" },
  quien: { yo: "Yo", una_persona: "1 persona", equipo: "Equipo de 2 o más", herramienta: "Un bot o herramienta" },
};
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40 p-5";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";

function Barras({ titulo, campo, datos, total, sel, onSel }) {
  const filas = Object.entries(datos || {}).sort((a, b) => b[1] - a[1]);
  return (
    <div className={caja}>
      <div className={`${rotulo} mb-3`}>{titulo}</div>
      {filas.length === 0 ? <p className="text-sm text-zinc-400">Sin respuestas aún.</p> : (
        <ul className="space-y-2">
          {filas.map(([k, n]) => {
            const pct = total ? Math.round((n / total) * 100) : 0;
            const activa = sel && sel.campo === campo && sel.valor === k;
            return (
              <li key={k}>
                <button type="button" onClick={() => onSel(activa ? null : { campo, valor: k, titulo: (TXT[campo] || {})[k] || k })}
                        aria-pressed={!!activa} className={`w-full text-left rounded-sm p-2 border ${activa ? "border-cyan-400/70 bg-cyan-500/10" : "border-transparent hover:border-zinc-700"}`}>
                  <div className="flex justify-between text-sm text-zinc-200"><span>{(TXT[campo] || {})[k] || k}</span><span className="tabular-nums">{n} · {pct} %</span></div>
                  <div className="h-2 mt-1 rounded-sm bg-zinc-800"><div className="h-2 rounded-sm bg-cyan-400" style={{ width: `${pct}%` }} /></div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default function EncuestaResultadosPage() {
  const [d, setD] = useState(null);
  const [sel, setSel] = useState(null);
  const enlace = `${window.location.origin}/encuesta`;
  const cargar = useCallback(() => api.get("/encuesta/resultados").then((r) => setD(r.data))
    .catch((e) => { toast.error(errorText(e)); setD({ error: true }); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  const copiar = async () => {
    try { await navigator.clipboard.writeText(enlace); toast.success("Enlace copiado."); } catch { toast.error("Cópialo a mano."); }
  };
  const resp = (d?.respuestas || []).filter((r) => !sel || (Array.isArray(r[sel.campo]) ? r[sel.campo].includes(sel.valor) : r[sel.campo] === sel.valor));

  return (
    <Layout>
      <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-5" data-testid="encuesta-resultados">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-white flex items-center gap-2"><ChartBar size={24} weight="duotone" /> Encuesta a dropshippers</h1>
            <p className="text-sm text-zinc-400 mt-1">Qué le duele más a quien vende con Dropi. Toca una barra para ver esas respuestas.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={copiar} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs"><Copy size={14} className="mr-1.5" /> Copiar enlace</Button>
            <Button variant="outline" onClick={cargar} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs"><ArrowsClockwise size={14} className="mr-1.5" /> Actualizar</Button>
          </div>
        </div>
        <div className={`${caja} text-sm text-zinc-300 break-all`}>Enlace para compartir: <span className="font-mono text-zinc-100">{enlace}</span> · agrega <span className="font-mono">?origen=grupo-x</span> para saber de dónde llegó cada respuesta.</div>

        {d === null ? <p className="text-sm text-zinc-400">Cargando…</p> : d.error ? <p className="text-sm text-zinc-400">No se pudieron cargar los resultados.</p> : (
          <>
            <div className="grid gap-3 grid-cols-2 md:grid-cols-3">
              <div className={caja}><div className="text-3xl font-semibold text-white tabular-nums">{d.total}<span className="text-base text-zinc-400"> / {d.meta}</span></div><div className="text-xs text-zinc-300 mt-1">Respuestas (meta)</div></div>
              <div className={caja}><div className="text-3xl font-semibold text-white tabular-nums">{d.quieren_prueba}</div><div className="text-xs text-zinc-300 mt-1">Quieren la prueba gratis</div></div>
              <div className={`${caja} col-span-2 md:col-span-1`}><div className="text-3xl font-semibold text-white tabular-nums">{Object.keys(d.pais || {}).length}</div><div className="text-xs text-zinc-300 mt-1">Países</div></div>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <Barras titulo="Qué les quita más tiempo" campo="dolores" datos={d.dolores} total={d.total} sel={sel} onSel={setSel} />
              <Barras titulo="Pedidos al día" campo="pedidos_dia" datos={d.pedidos_dia} total={d.total} sel={sel} onSel={setSel} />
              <Barras titulo="Quién lo hace hoy" campo="quien" datos={d.quien} total={d.total} sel={sel} onSel={setSel} />
            </div>
            <div className={caja} data-testid="encuesta-respuestas">
              <div className={`${rotulo} mb-3`}>{sel ? `Respuestas · ${sel.titulo}` : "Todas las respuestas"} · {resp.length}</div>
              {resp.length === 0 ? <p className="text-sm text-zinc-400">Aún no hay respuestas aquí.</p> : (
                <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Respuestas">
                  <table className="w-full text-sm">
                    <thead><tr className="text-left text-[11px] text-zinc-400 border-b border-zinc-800">
                      {["Fecha", "País", "Pedidos/día", "Le duele", "Quién", "Herramienta", "Arreglaría", "WhatsApp"].map((h) => <th key={h} scope="col" className="py-2 pr-4 font-normal whitespace-nowrap">{h}</th>)}
                    </tr></thead>
                    <tbody>
                      {resp.map((r) => (
                        <tr key={r.id} className="border-b border-zinc-900 text-zinc-200 align-top">
                          <td className="py-2 pr-4 text-xs whitespace-nowrap">{new Date(r.creado).toLocaleDateString("es-CO")}</td>
                          <td className="py-2 pr-4 text-xs">{r.pais}</td>
                          <td className="py-2 pr-4 text-xs">{TXT.pedidos_dia[r.pedidos_dia]}</td>
                          <td className="py-2 pr-4 text-xs">{(r.dolores || []).map((x) => TXT.dolores[x] || x).join(", ")}</td>
                          <td className="py-2 pr-4 text-xs">{TXT.quien[r.quien]}</td>
                          <td className="py-2 pr-4 text-xs">{r.herramienta || "—"}</td>
                          <td className="py-2 pr-4 text-xs max-w-[18rem]">{r.arreglar || "—"}</td>
                          <td className="py-2 pr-4 text-xs font-mono">{r.whatsapp || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
