import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { X, Plus } from "@phosphor-icons/react";

/** Pendientes de Chatea Pro: tres reglas que cada cliente ajusta. Aquí se elige
 *  qué columnas del tablero trabaja el agente y los valores de cada regla. */
const INFO = {
  diario: {
    titulo: "Pendientes diarios",
    para: "El cliente quiere comprar, pero falta un dato: dirección, color, medida o confirmar algo.",
    como: "El agente lee los chats de las columnas que elijas, pide el dato que falta y, cuando está completo, deja el pedido listo para crear.",
    casillas: "Pendiente diario: falta un dato",
  },
  oficina: {
    titulo: "Pendientes en oficina",
    para: "La zona sale en rojo en la huella: hay riesgo alto de que no reclamen el pedido.",
    como: "Antes de enviar se pide un adelanto. Tú decides el valor y si además se llama al cliente.",
    casillas: "Pendiente en oficina: pedir adelanto",
  },
  final: {
    titulo: "Pendientes finales",
    para: "El cliente dejó de responder y el pedido quedó a medias.",
    como: "Pasados los días que elijas, se envía una plantilla por día. Si no responde a ninguna, el pedido se cancela.",
    casillas: "Pendiente final: recordatorio 1, 2 y último aviso",
  },
};
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";
const pill = "text-[10px] px-1.5 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100";
const campo = "bg-black/40 border-zinc-700 text-white text-sm";

function Casilla({ id, checked, onChange, children }) {
  return (
    <label htmlFor={id} className="flex items-start gap-2.5 text-sm text-zinc-200 cursor-pointer min-h-[32px]">
      <input id={id} type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 h-5 w-5 accent-fuchsia-400" />
      <span>{children}</span>
    </label>
  );
}

function Regla({ regla, onGuardada }) {
  const info = INFO[regla.clase];
  const [f, setF] = useState({ activo: regla.activo, columnas: regla.columnas || [], ...regla.params });
  const [nueva, setNueva] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const agregar = () => {
    const c = nueva.trim().toUpperCase();
    if (!c) return;
    if (f.columnas.length >= 10) { toast.error("Máximo 10 columnas."); return; }
    if (!f.columnas.includes(c)) set("columnas", [...f.columnas, c]);
    setNueva("");
  };
  const guardar = async () => {
    setBusy(true);
    try {
      const cuerpo = { activo: f.activo, columnas: f.columnas, llamar: !!f.llamar };
      if (regla.clase === "oficina") cuerpo.adelanto = Number(f.adelanto) || 0;
      if (regla.clase === "final") Object.assign(cuerpo, { dias_sin_respuesta: Number(f.dias_sin_respuesta) || 2, plantillas: Number(f.plantillas) || 3, cancelar: !!f.cancelar });
      const r = await api.put(`/zcall/motor/pendientes/${regla.clase}`, cuerpo);
      toast.success(r.data.mensaje); onGuardada();
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };
  const id = `pend-${regla.clase}`;
  return (
    <section className={`${caja} p-5 space-y-4`} data-testid={id} aria-labelledby={`${id}-t`}>
      <div className="flex flex-wrap items-center gap-2">
        <h2 id={`${id}-t`} className="text-base font-semibold text-white">{info.titulo}</h2>
        <span className={pill}>Beta</span>
        <span className={pill}>{f.activo ? "Encendida" : "Apagada"}</span>
      </div>
      <div className="grid gap-3 md:grid-cols-2 text-sm">
        <p className="text-zinc-300"><span className={`${rotulo} block mb-1`}>Para qué sirve</span>{info.para}</p>
        <p className="text-zinc-300"><span className={`${rotulo} block mb-1`}>Cómo funciona</span>{info.como}</p>
      </div>

      <div>
        <div className={`${rotulo} mb-2`}>Columnas del tablero de Chatea que trabaja</div>
        <div className="flex flex-wrap gap-2 mb-2">
          {f.columnas.length === 0 && <span className="text-xs text-zinc-400">Ninguna columna elegida.</span>}
          {f.columnas.map((c) => (
            <span key={c} className="inline-flex items-center gap-1 pl-2 pr-1 h-8 rounded-sm border border-zinc-600 bg-zinc-800 text-xs text-zinc-100">
              {c}
              <button type="button" onClick={() => set("columnas", f.columnas.filter((x) => x !== c))} aria-label={`Quitar columna ${c}`}
                      className="h-6 w-6 grid place-items-center rounded-sm hover:bg-zinc-700"><X size={12} /></button>
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Input aria-label={`Nombre de la columna para ${info.titulo}`} value={nueva} maxLength={40} onChange={(e) => setNueva(e.target.value)}
                 onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregar(); } }}
                 placeholder="Nombre de la columna, como aparece en Chatea" className={`${campo} max-w-xs`} />
          <Button type="button" variant="outline" onClick={agregar} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-sm"><Plus size={14} className="mr-1.5" /> Agregar columna</Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {regla.clase === "oficina" && (
          <div>
            <label htmlFor={`${id}-adelanto`} className={`${rotulo} block mb-1`}>Adelanto que se pide (pesos)</label>
            <Input id={`${id}-adelanto`} type="number" min={0} max={500000} step={1000} value={f.adelanto ?? ""} onChange={(e) => set("adelanto", e.target.value)} className={campo} />
          </div>
        )}
        {regla.clase === "final" && (
          <>
            <div>
              <label htmlFor={`${id}-dias`} className={`${rotulo} block mb-1`}>Días sin respuesta antes de empezar</label>
              <Input id={`${id}-dias`} type="number" min={1} max={10} value={f.dias_sin_respuesta ?? ""} onChange={(e) => set("dias_sin_respuesta", e.target.value)} className={campo} />
            </div>
            <div>
              <label htmlFor={`${id}-pl`} className={`${rotulo} block mb-1`}>Plantillas a enviar (una por día)</label>
              <Input id={`${id}-pl`} type="number" min={1} max={3} value={f.plantillas ?? ""} onChange={(e) => set("plantillas", e.target.value)} className={campo} />
            </div>
          </>
        )}
      </div>

      <div className="space-y-1.5">
        <Casilla id={`${id}-llamar`} checked={f.llamar} onChange={(v) => set("llamar", v)}>También llamar al cliente con el agente de voz.</Casilla>
        {regla.clase === "final" && <Casilla id={`${id}-cancelar`} checked={f.cancelar} onChange={(v) => set("cancelar", v)}>Cancelar el pedido si no responde a ninguna plantilla.</Casilla>}
        <Casilla id={`${id}-activo`} checked={f.activo} onChange={(v) => set("activo", v)}>Encender esta regla.</Casilla>
      </div>

      <p className="text-xs text-zinc-400">La plantilla se elige en la pestaña Plantillas, casilla «{info.casillas}».</p>
      <Button disabled={busy} onClick={guardar} className="btn-cta-grad rounded-sm h-9 text-sm">{busy ? "Guardando…" : "Guardar regla"}</Button>
    </section>
  );
}

export default function PendientesChatea() {
  const [reglas, setReglas] = useState(null);
  const cargar = useCallback(() => api.get("/zcall/motor/pendientes").then((r) => setReglas(r.data.reglas || []))
    .catch((e) => setReglas({ error: e?.response?.status === 501 ? "Esta parte aún no está activada. Soporte de Zynex la activa." : errorText(e) })), []);
  useEffect(() => { cargar(); }, [cargar]);
  if (reglas === null) return <p className="text-sm text-zinc-400">Cargando…</p>;
  if (reglas.error) return <div className={`${caja} p-5 text-sm text-zinc-300`}>{reglas.error}</div>;
  if (reglas.length === 0) return <p className="text-sm text-zinc-400">Tu espacio se está preparando. Abre la pestaña Panel y vuelve aquí.</p>;
  return (
    <div className="space-y-5" data-testid="log-pendientes">
      <div className={`${caja} p-5 text-sm text-zinc-300`}>
        Aquí decides cómo trabaja el agente los chats pendientes de Chatea Pro. Está en Beta: guarda tus reglas, pero todavía no envía mensajes ni cancela pedidos.
      </div>
      {reglas.map((r) => <Regla key={r.clase} regla={r} onGuardada={cargar} />)}
    </div>
  );
}
