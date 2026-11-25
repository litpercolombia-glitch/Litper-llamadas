import { useRef, useState } from "react";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { UploadSimple } from "@phosphor-icons/react";

/** Traer mi operación: el cliente sube su reporte de órdenes de Dropi y elige
 *  cuántos días traer. Con eso se llenan Clientes y Métricas de SU espacio. */
const DIAS = [30, 60, 90];
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";

export default function TraerOperacion({ onListo }) {
  const [dias, setDias] = useState(90);
  const [archivo, setArchivo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const input = useRef(null);

  const subir = async () => {
    if (!archivo) return;
    setBusy(true); setRes(null);
    try {
      const fd = new FormData();
      fd.append("file", archivo); fd.append("dias", String(dias));
      const r = await api.post("/zcall/motor/operacion/importar", fd, { timeout: 120000 });
      setRes(r.data); toast.success(r.data.mensaje);
      setArchivo(null); if (input.current) input.current.value = "";
      onListo?.();
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  return (
    <section className={`${caja} p-5 space-y-4`} data-testid="traer-operacion" aria-labelledby="traer-op-t">
      <div>
        <h2 id="traer-op-t" className="text-base font-semibold text-white">Traer mi operación</h2>
        <div className="grid gap-3 md:grid-cols-2 text-sm mt-2">
          <p className="text-zinc-300"><span className={`${rotulo} block mb-1`}>Para qué sirve</span>
            Trae tus pedidos de Dropi de los últimos días para ver tus clientes y tus métricas desde el primer día.</p>
          <p className="text-zinc-300"><span className={`${rotulo} block mb-1`}>Cómo funciona</span>
            En Dropi descarga el reporte de órdenes en Excel, súbelo aquí y elige el periodo. Solo se guardan tus pedidos; no se envía nada a tus clientes.</p>
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
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="traer-op-file" className="sr-only">Reporte de órdenes de Dropi</label>
        <input id="traer-op-file" ref={input} type="file" accept=".xlsx,.xls,.csv" onChange={(e) => setArchivo(e.target.files?.[0] || null)}
               className="text-sm text-zinc-200 max-w-full file:mr-3 file:h-9 file:px-3 file:rounded-sm file:border file:border-zinc-700 file:bg-zinc-950 file:text-zinc-100 file:text-sm" />
        <Button disabled={!archivo || busy} onClick={subir} className="btn-cta-grad rounded-sm h-9 text-sm">
          <UploadSimple size={15} className="mr-1.5" /> {busy ? "Subiendo…" : "Traer pedidos"}</Button>
      </div>
      {res && (
        <p className="text-sm text-zinc-200" role="status" data-testid="traer-operacion-res">
          Guardamos {res.guardados} pedidos de {res.leidos} leídos.
          {res.fuera_de_periodo > 0 && ` ${res.fuera_de_periodo} quedaron fuera del periodo.`}
          {res.sin_dato > 0 && ` ${res.sin_dato} no tenían número de pedido o estado.`}
        </p>
      )}
    </section>
  );
}
