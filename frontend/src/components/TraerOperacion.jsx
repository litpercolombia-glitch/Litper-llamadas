import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { UploadSimple, Sparkle } from "@phosphor-icons/react";

/** Traer mi operación: el cliente trae sus pedidos de Dropi con su Claude
 *  (recomendado) o subiendo el reporte. Con eso se llenan Clientes y Métricas. */
const DIAS = [30, 60, 90];
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";
const pill = "text-[10px] px-1.5 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100 whitespace-nowrap";
const TIPO = { traer_operacion: "Traer la operación", refrescar_pedidos: "Actualizar pedidos activos" };
const ESTADO = { pendiente: "Esperando a tu Claude", hecha: "Hecha", cancelada: "Cancelada" };

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

  const pedir = async () => {
    setBusy("pedir");
    try { const r = await api.post("/zcall/motor/operacion/pedir", { dias }); toast.success(r.data.mensaje); await cargar(); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(""); }
  };
  const subir = async () => {
    if (!archivo) return;
    setBusy("subir"); setRes(null);
    try {
      const fd = new FormData();
      fd.append("file", archivo); fd.append("dias", String(dias));
      const r = await api.post("/zcall/motor/operacion/importar", fd, { timeout: 120000 });
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
            Trae tus pedidos de Dropi para ver tus clientes y tus métricas desde el primer día, y mantenerlos al día.</p>
          <p className="text-zinc-300"><span className={`${rotulo} block mb-1`}>Cómo funciona</span>
            Zynex le pide los pedidos a tu Claude, tu Claude los lee de tu Dropi y se los entrega a Zynex. Solo se guardan tus pedidos; no se envía nada a tus clientes.</p>
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
        <div className="border border-zinc-800 rounded-sm p-4 space-y-3" data-testid="traer-op-claude">
          <div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-white">Con tu Claude</h3><span className={pill}>Recomendado</span></div>
          <ol className="text-sm text-zinc-300 space-y-1 list-decimal pl-5">
            <li>Conecta Zynex y Dropi en tu Claude. La dirección de Zynex está en <Link to="/app/conexiones?tab=claude" className="underline text-zinc-100">Conexiones → Claude</Link>.</li>
            <li>Pulsa «Pedirle a Claude».</li>
            <li>En tu Claude escribe: «Sincroniza mi Zynex».</li>
          </ol>
          <Button disabled={busy === "pedir"} onClick={pedir} className="btn-cta-grad rounded-sm h-9 text-sm">
            <Sparkle size={15} className="mr-1.5" /> {busy === "pedir" ? "Pidiendo…" : `Pedirle a Claude los últimos ${dias} días`}</Button>
          {sols.length > 0 && (
            <ul className="space-y-1.5" aria-label="Solicitudes a Claude">
              {sols.slice(-4).map((s) => (
                <li key={s.solicitud_id} className="flex flex-wrap items-center gap-2 text-xs text-zinc-300">
                  <span className={pill}>{ESTADO[s.estado] || s.estado}</span>
                  {TIPO[s.tipo] || s.tipo}{s.params?.dias ? ` · ${s.params.dias} días` : ""} · {s.entregados} pedidos recibidos
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="border border-zinc-800 rounded-sm p-4 space-y-3" data-testid="traer-op-archivo">
          <h3 className="text-sm font-semibold text-white">Con el reporte de Dropi</h3>
          <p className="text-sm text-zinc-300">Si no usas Claude: en Dropi descarga el reporte de órdenes en Excel y súbelo aquí.</p>
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
