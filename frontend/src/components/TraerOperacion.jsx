import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { UploadSimple, Sparkle, Copy, ArrowsClockwise } from "@phosphor-icons/react";

/** Traer mi operación: el cliente trae sus pedidos de Dropi con su Claude
 *  (recomendado) o subiendo el reporte. Con eso se llenan Clientes y Métricas.
 *  Con Claude se trae por semanas: cada semana termina cuando Claude entrega su
 *  última página; si Claude se detiene, sigue donde quedó en otra conversación. */
const DIAS = [30, 60, 90];
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";
const pill = "text-[10px] px-1.5 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100 whitespace-nowrap";
export const PROMPT_CLAUDE = "Sincroniza mi Zynex: revisa con zynex_logistica_solicitudes lo que Zynex me pide y cúmplelo con mi conector de Dropi, una semana a la vez. Entrega cada página con zynex_logistica_entregar y marca final=true cuando termines cada semana. Para los pedidos activos usa get_order y manda todo el detalle (dirección, productos y pago). Al final dime cuántas semanas quedaron listas y cuántas faltan.";

const hace = (v) => {
  if (!v) return "";
  const m = Math.round((Date.now() - new Date(v).getTime()) / 60000);
  return m < 1 ? "hace un momento" : m < 60 ? `hace ${m} min` : m < 1440 ? `hace ${Math.round(m / 60)} h` : `hace ${Math.round(m / 1440)} días`;
};

async function copiar(texto) {
  try { await navigator.clipboard.writeText(texto); toast.success("Mensaje copiado. Pégalo en tu Claude."); }
  catch { toast.error("No se pudo copiar: selecciona el texto y cópialo a mano."); }
}

/** Agrupa las solicitudes: cada «traer operación» son varias semanas; «actualizar pedidos» va aparte. */
function agrupar(sols) {
  const grupos = {};
  (sols || []).forEach((s) => {
    const k = s.tipo === "traer_operacion" ? `op:${s.params?.grupo || s.solicitud_id}` : `ref:${s.solicitud_id}`;
    (grupos[k] = grupos[k] || []).push(s);
  });
  return Object.entries(grupos).map(([k, items]) => {
    const total = items[0]?.params?.de || items.length;
    const listas = items.filter((s) => s.estado === "hecha").length;
    const pendientes = items.filter((s) => s.estado === "pendiente").length;
    return {
      k, tipo: items[0].tipo, dias: items[0].params?.dias, total, listas, pendientes,
      pedidos: items.reduce((a, s) => a + (Number(s.entregados) || 0), 0),
      ultimo: items.map((s) => s.actualizado || s.creado).sort().pop(),
      id: (items.find((s) => s.estado === "pendiente") || items[0]).solicitud_id,
      nPedidos: items[0].params?.pedidos?.length,
    };
  }).sort((a, b) => (b.pendientes > 0) - (a.pendientes > 0) || String(b.ultimo).localeCompare(String(a.ultimo)));
}

function Avance({ g, onTerminar, busy }) {
  const pct = g.total ? Math.round((g.listas / g.total) * 100) : 0;
  const titulo = g.tipo === "traer_operacion" ? `Traer ${g.dias || ""} días` : `Actualizar ${g.nPedidos || ""} pedidos activos`;
  const estado = g.pendientes === 0 ? "Terminado" : g.listas === 0 && g.pedidos === 0 ? "Esperando a tu Claude" : "Tu Claude va en camino";
  return (
    <li className="border border-zinc-800 rounded-sm p-3 space-y-2" data-testid="traer-op-avance">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-white font-medium">{titulo}</div>
        <span className={pill}>{estado}</span>
      </div>
      {g.tipo === "traer_operacion" && (
        <div className="h-2 rounded-sm bg-zinc-800" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label={`${titulo}: ${pct} %`}>
          <div className="h-2 rounded-sm bg-emerald-400" style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="text-xs text-zinc-300">
        {g.tipo === "traer_operacion" ? `${g.listas} de ${g.total} semanas listas · ` : ""}{g.pedidos.toLocaleString("es-CO")} pedidos recibidos
        {g.ultimo ? ` · último movimiento ${hace(g.ultimo)}` : ""}
      </div>
      {g.pendientes > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] text-zinc-400">Si tu Claude se detuvo, escríbele otra vez el mensaje de arriba: sigue donde quedó.</span>
          <Button type="button" variant="outline" disabled={busy} onClick={() => onTerminar(g.id)}
                  className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">Dar por terminado</Button>
        </div>
      )}
    </li>
  );
}

export default function TraerOperacion({ onListo }) {
  const [dias, setDias] = useState(90);
  const [archivo, setArchivo] = useState(null);
  const [busy, setBusy] = useState("");
  const [res, setRes] = useState(null);
  const [sols, setSols] = useState([]);
  const input = useRef(null);

  const cargar = useCallback(() => api.get("/zcall/motor/operacion/solicitudes")
    .then((r) => setSols(r.data.solicitudes || [])).catch(() => setSols([])), []);
  useEffect(() => { cargar(); }, [cargar]);
  const grupos = useMemo(() => agrupar(sols), [sols]);
  const hayPendiente = grupos.some((g) => g.pendientes > 0);
  useEffect(() => {
    if (!hayPendiente) return undefined;
    const t = setInterval(cargar, 30000);
    return () => clearInterval(t);
  }, [hayPendiente, cargar]);

  const pedir = async () => {
    setBusy("pedir");
    try { const r = await api.post("/zcall/motor/operacion/pedir", { dias }); toast.success(r.data.mensaje); await cargar(); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(""); }
  };
  const terminar = async (id) => {
    setBusy("terminar");
    try { const r = await api.post(`/zcall/motor/operacion/solicitudes/${id}/terminar`); toast.success(r.data.mensaje); await cargar(); onListo?.(); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(""); }
  };
  const subir = async () => {
    if (!archivo) return;
    setBusy("subir"); setRes(null);
    try {
      const fd = new FormData();
      fd.append("file", archivo); fd.append("dias", String(dias));
      const r = await api.post("/zcall/motor/operacion/importar", fd, { timeout: 180000 });
      setRes(r.data); toast.success(r.data.mensaje);
      setArchivo(null); if (input.current) input.current.value = "";
      onListo?.();
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(""); }
  };

  return (
    <section className={`${caja} p-5 space-y-5`} data-testid="traer-operacion" aria-labelledby="traer-op-t">
      <div>
        <h2 id="traer-op-t" className="text-base font-semibold text-white">Traer mi operación</h2>
        <div className="grid gap-3 md:grid-cols-2 text-sm mt-2">
          <p className="text-zinc-300"><span className={`${rotulo} block mb-1`}>Para qué sirve</span>
            Trae tus pedidos de Dropi, con todo su detalle, para ver tus clientes y tus métricas desde el primer día y mantenerlos al día.</p>
          <p className="text-zinc-300"><span className={`${rotulo} block mb-1`}>Cómo funciona</span>
            Zynex le pide los pedidos a tu Claude por semanas. Tu Claude los lee en tu Dropi y se los entrega a Zynex. Cada semana queda lista cuando Claude entrega su última página. No se envía nada a tus clientes.</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Periodo a traer">
        <span className={rotulo}>Traer</span>
        {DIAS.map((d) => (
          <button key={d} type="button" aria-pressed={dias === d} onClick={() => setDias(d)}
                  className={`h-9 px-3 rounded-sm border text-sm ${dias === d ? "border-emerald-400/70 bg-emerald-500/10 text-white" : "border-zinc-800 text-zinc-300 hover:bg-zinc-900"}`}>
            Últimos {d} días</button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="border border-zinc-800 rounded-sm p-4 space-y-3 min-w-0" data-testid="traer-op-claude">
          <div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-white">Con tu Claude</h3><span className={pill}>Recomendado</span></div>
          <ol className="text-sm text-zinc-300 space-y-1 list-decimal pl-5">
            <li>Conecta Zynex y Dropi en tu Claude. La dirección de Zynex está en <Link to="/app/conexiones?tab=claude" className="underline text-zinc-100">Conexiones → Claude</Link>.</li>
            <li>Pulsa «Pedirle a Claude». Se divide en semanas ({Math.ceil(dias / 7)} para {dias} días).</li>
            <li>Copia este mensaje y pégalo en tu Claude:</li>
          </ol>
          <div className="flex items-start gap-2">
            <p className="flex-1 min-w-0 text-xs text-zinc-200 bg-black/40 border border-zinc-800 rounded-sm p-2 break-words" data-testid="traer-op-prompt">{PROMPT_CLAUDE}</p>
            <button type="button" onClick={() => copiar(PROMPT_CLAUDE)} aria-label="Copiar mensaje para Claude" title="Copiar mensaje"
                    className="h-8 w-8 shrink-0 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><Copy size={14} /></button>
          </div>
          <Button disabled={busy === "pedir"} onClick={pedir} className="btn-cta-grad rounded-sm h-9 text-sm">
            <Sparkle size={15} className="mr-1.5" /> {busy === "pedir" ? "Pidiendo…" : `Pedirle a Claude los últimos ${dias} días`}</Button>
          {grupos.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className={rotulo}>Cómo va</div>
                <button type="button" onClick={cargar} className="text-xs text-zinc-300 inline-flex items-center gap-1 hover:text-white"><ArrowsClockwise size={12} /> Revisar</button>
              </div>
              <ul className="space-y-2" aria-label="Peticiones a tu Claude">
                {grupos.slice(0, 4).map((g) => <Avance key={g.k} g={g} onTerminar={terminar} busy={busy === "terminar"} />)}
              </ul>
            </div>
          )}
        </div>

        <div className="border border-zinc-800 rounded-sm p-4 space-y-3 min-w-0" data-testid="traer-op-archivo">
          <h3 className="text-sm font-semibold text-white">Con el reporte de Dropi</h3>
          <p className="text-sm text-zinc-300">La vía rápida para 60 o 90 días: en Dropi descarga el reporte de órdenes en Excel y súbelo aquí. Entra completo, con todas sus columnas, en un minuto.</p>
          <label htmlFor="traer-op-file" className="sr-only">Reporte de órdenes de Dropi</label>
          <input id="traer-op-file" ref={input} type="file" accept=".xlsx,.xls,.csv" onChange={(e) => setArchivo(e.target.files?.[0] || null)}
                 className="block text-sm text-zinc-200 max-w-full file:mr-3 file:h-9 file:px-3 file:rounded-sm file:border file:border-zinc-700 file:bg-zinc-950 file:text-zinc-100 file:text-sm" />
          <Button disabled={!archivo || busy === "subir"} variant="outline" onClick={subir} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-sm">
            <UploadSimple size={15} className="mr-1.5" /> {busy === "subir" ? "Subiendo…" : "Subir reporte"}</Button>
          {res && (
            <p className="text-sm text-zinc-200" role="status" data-testid="traer-operacion-res">
              Guardamos {res.guardados} pedidos de {res.leidos} leídos.
              {res.fuera_de_periodo > 0 && ` ${res.fuera_de_periodo} quedaron fuera del periodo.`}
              {res.sin_dato > 0 && ` ${res.sin_dato} no tenían número de pedido o estado.`}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
