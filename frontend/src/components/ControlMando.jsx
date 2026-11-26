import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { X, User, PhoneCall, ChatText, ClockCounterClockwise, CheckCircle, WarningCircle } from "@phosphor-icons/react";

/** Control de mando: informe por proceso del cerebro logístico (pendientes, seguimiento,
 *  novedades, oficina y cierre), la cola de cada uno, la línea de tiempo del pedido,
 *  lo que dijo el cliente y los casos que pasan a una persona. Modo sombra: decide y anota. */
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";
const cop = (v) => (v ? `$${Number(v).toLocaleString("es-CO")}` : "—");
const fechaHora = (v) => (v ? new Date(v).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "—");
const NOMBRE = { pendientes: "Pendientes", seguimiento: "Seguimiento", novedades: "Novedades", oficina: "Reclamo en oficina", cierre: "Cierre", persona: "Para una persona", postventa: "Postventa", proveedores: "Proveedores" };
const CANAL = { "mensaje+llamada": "Mensaje y llamada", mensaje: "Mensaje", llamada: "Llamada", proveedor: "Proveedor", persona: "Persona", ninguno: "Sin acción" };
const limpio = (t) => String(t || "").replace(/_/g, " ");

function Linea({ pedido, onCerrar }) {
  const [d, setD] = useState(null);
  const [texto, setTexto] = useState("");
  const [compromiso, setCompromiso] = useState("");
  const [canal, setCanal] = useState("llamada");
  const [guardando, setGuardando] = useState(false);
  const [ticket, setTicket] = useState(false);
  const cargar = useCallback(() => api.get(`/zcall/cerebro/pedidos/${pedido}/linea`).then((r) => setD(r.data))
    .catch((e) => { toast.error(errorText(e)); setD({ linea: [], decision: null }); }), [pedido]);
  useEffect(() => { setD(null); cargar(); }, [cargar]);
  const guardar = async () => {
    if (texto.trim().length < 3) { toast.error("Escribe qué dijo el cliente (mínimo 3 letras)."); return; }
    setGuardando(true);
    try {
      const r = await api.post(`/zcall/cerebro/pedidos/${pedido}/dicho`, { texto, compromiso, canal, ticket });
      toast.success(r.data?.repetido ? "Ese registro ya estaba guardado." : r.data?.caso_para_persona ? "Registro guardado y caso abierto para una persona." : "Registro guardado."); setTicket(false); setTexto(""); setCompromiso(""); await cargar();
    } catch (e) { toast.error(errorText(e)); } finally { setGuardando(false); }
  };
  const dec = d?.decision;
  const ped = d?.pedido;
  return (
    <div className={`${caja} p-5 space-y-4`} data-testid="cm-linea">
      <div className="flex items-center justify-between gap-3">
        <div className={rotulo}>Pedido {pedido} · línea de tiempo</div>
        <button type="button" onClick={onCerrar} aria-label="Cerrar" className="h-11 w-11 inline-flex items-center justify-center text-zinc-400 hover:text-white"><X size={16} /></button>
      </div>
      {d === null ? <p className="text-sm text-zinc-400">Cargando…</p> : (<>
        {ped && (
          <div className="text-xs text-zinc-300 flex flex-wrap gap-x-4 gap-y-1" data-testid="cm-linea-cabecera">
            <span>{ped.estado}</span><span>{ped.ciudad || "Sin ciudad"}</span><span>{cop(ped.valor)}</span>
            <span>{ped.transportadora || "Sin transportadora"}{ped.guia ? ` · guía ${ped.guia}` : ""}</span>
            <span className={ped.tiene_telefono ? "" : "text-amber-300"}>{ped.tiene_telefono ? "Con teléfono" : "Sin teléfono: no se puede contactar"}</span>
            <span>Leído de Dropi: {fechaHora(ped.ultima_lectura)}</span>
          </div>)}
        {dec && (
          <div className="border border-fuchsia-400/40 bg-fuchsia-500/5 rounded-sm p-3 text-sm text-zinc-100">
            <div className={rotulo}>Qué toca ahora</div>
            <div className="mt-1 font-medium">{limpio(dec.accion)} · {CANAL[dec.canal] || dec.canal}</div>
            <div className="text-zinc-300 mt-1">{dec.motivo}</div>
            <div className="text-[11px] text-zinc-400 mt-1">{dec.estado} · {dec.fecha_confiable ? "" : "al menos "}{dec.dias ?? "—"} días en este estado{dec.fecha_confiable ? "" : " (se vio por primera vez ya así)"}{dec.fuente ? ` · Regla: ${dec.fuente}` : ""}</div>
          </div>)}
        <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto_auto_auto] items-end">
          <label className="text-xs text-zinc-300">Qué dijo el cliente
            <Input value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={1000} data-testid="cm-dicho-texto" className="mt-1 h-11 rounded-sm bg-zinc-950 border-zinc-700" /></label>
          <label className="text-xs text-zinc-300">Compromiso (opcional)
            <Input value={compromiso} onChange={(e) => setCompromiso(e.target.value)} maxLength={300} placeholder="Ej.: retira el viernes" className="mt-1 h-11 rounded-sm bg-zinc-950 border-zinc-700" /></label>
          <label className="text-xs text-zinc-300">Canal
            <select value={canal} onChange={(e) => setCanal(e.target.value)} className="mt-1 h-11 w-full rounded-sm bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 px-2">
              <option value="llamada">Llamada</option><option value="whatsapp">WhatsApp</option><option value="mensaje">Mensaje</option><option value="chat">Chat</option><option value="otro">Otro</option></select></label>
          <label className="text-xs text-zinc-300 flex items-center gap-2 min-h-[44px]"><input type="checkbox" checked={ticket} onChange={(e) => setTicket(e.target.checked)} className="h-5 w-5" data-testid="cm-dicho-ticket" /> Necesita a una persona</label>
          <Button onClick={guardar} disabled={guardando} data-testid="cm-dicho-guardar" className="h-11 rounded-sm text-xs">{guardando ? "Guardando…" : "Guardar"}</Button>
        </div>
        {(d.linea || []).length === 0 ? <p className="text-sm text-zinc-400">Aún no hay movimientos de este pedido.</p> : (
          <ol className="space-y-2">
            {d.linea.map((l, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="text-[11px] text-zinc-400 w-28 shrink-0 tabular-nums">{fechaHora(l.cuando)}</span>
                <span className="text-[11px] px-2 py-0.5 h-fit rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100 shrink-0">{l.tipo}</span>
                <span className="text-zinc-200 break-words min-w-0">{limpio(l.texto)}</span>
              </li>))}
          </ol>)}
      </>)}
    </div>
  );
}

function Cola({ proceso, onAbrir }) {
  const [filas, setFilas] = useState(null);
  useEffect(() => { setFilas(null);
    api.get("/zcall/cerebro/cola", { params: { proceso, limite: 1000 } }).then((r) => setFilas(r.data.filas || []))
      .catch((e) => { toast.error(errorText(e)); setFilas([]); }); }, [proceso]);
  return (
    <div className={`${caja} p-5`} data-testid="cm-cola">
      <div className={`${rotulo} mb-3`}>{NOMBRE[proceso]}{filas ? ` · ${filas.length} · ${filas.filter((f) => f.accionable).length} piden acción (van primero)` : ""}</div>
      {filas === null ? <p className="text-sm text-zinc-400">Cargando…</p> : filas.length === 0 ? <p className="text-sm text-zinc-400">No hay pedidos en esta cola hoy.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead><tr className="text-left text-[11px] text-zinc-400 uppercase tracking-wider">
              <th className="py-2 pr-3">Pedido</th><th className="pr-3">Estado</th><th className="pr-3">Días</th><th className="pr-3">Etiqueta</th><th className="pr-3">Qué toca</th><th className="pr-3">Ciudad</th><th className="pr-3">Valor</th><th>Último registro</th></tr></thead>
            <tbody>{filas.map((f) => (
              <tr key={`${f.pedido}-${f.accion}`} onClick={() => onAbrir(f.pedido)} tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") onAbrir(f.pedido); }}
                  className="border-t border-zinc-800 hover:bg-zinc-900 cursor-pointer text-zinc-200">
                <td className="py-2.5 pr-3 tabular-nums text-white">{f.pedido}</td><td className="pr-3">{f.estado}</td><td className="pr-3 tabular-nums" title={f.fecha_confiable ? "Días desde que se vio el cambio de estado" : "Mínimo: se vio por primera vez ya en este estado"}>{f.fecha_confiable ? "" : "≥ "}{f.dias ?? "—"}</td>
                <td className="pr-3">{f.escala && <WarningCircle size={13} className="inline mr-1 text-amber-300" aria-label="Pasa a una persona" />}{limpio(f.etiqueta)}</td>
                <td className="pr-3">{limpio(f.accion)} · {CANAL[f.canal] || f.canal}</td><td className="pr-3">{f.ciudad || "—"}{f.tiene_telefono === false && <span className="ml-1 text-amber-300">· sin teléfono</span>}</td><td className="pr-3 tabular-nums">{cop(f.valor)}</td>
                <td className="text-zinc-400 max-w-[220px] truncate">{f.ultimo_dicho || "—"}</td>
              </tr>))}</tbody>
          </table>
        </div>)}
    </div>
  );
}

function Persona({ onAbrir, recargar }) {
  const [casos, setCasos] = useState(null);
  const [nota, setNota] = useState({});
  const cargar = useCallback(() => api.get("/zcall/cerebro/persona").then((r) => setCasos(r.data.casos || []))
    .catch((e) => { toast.error(errorText(e)); setCasos([]); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  const resolver = async (c) => {
    const n = (nota[c.id] || "").trim();
    if (n.length < 5) { toast.error("Escribe qué se hizo con el caso (mínimo 5 letras)."); return; }
    try { await api.post(`/zcall/cerebro/persona/${c.id}/resolver`, { nota: n }); toast.success("Caso cerrado. No se vuelve a abrir en 24 horas."); setNota((s) => ({ ...s, [c.id]: "" })); await cargar(); recargar(); }
    catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div className={`${caja} p-5`} data-testid="cm-persona">
      <div className={`${rotulo} mb-3`}>Casos para una persona{casos ? ` · ${casos.length}` : ""}</div>
      {casos === null ? <p className="text-sm text-zinc-400">Cargando…</p> : casos.length === 0 ? <p className="text-sm text-zinc-400">No hay casos abiertos.</p> : (
        <ul className="space-y-2">{casos.map((c) => (
          <li key={c.id} className="border border-zinc-800 rounded-sm p-3 grid gap-2 md:grid-cols-[1fr_1fr_auto] items-center text-sm">
            <button type="button" onClick={() => onAbrir(c.pedido)} className="text-left min-h-[44px]">
              <span className="text-white tabular-nums">{c.pedido}</span> <span className="text-zinc-300">· {c.estado || "—"} · {c.fecha_confiable ? "" : "≥ "}{c.dias ?? "—"} días</span>
              <div className="text-[11px] text-zinc-400">{NOMBRE[c.proceso] || c.proceso} · {limpio(c.motivo)} · {c.ciudad || "—"} · {cop(c.valor)} · abierto hace {c.horas_abierto ?? "—"} h{c.tiene_telefono === false ? " · sin teléfono" : ""}</div>
              {c.ultimo_dicho && <div className="text-[11px] text-zinc-300 truncate">Cliente: {c.ultimo_dicho}</div>}
            </button>
            <Input value={nota[c.id] || ""} onChange={(e) => setNota((s) => ({ ...s, [c.id]: e.target.value }))} maxLength={500} placeholder="Qué se hizo" aria-label={`Qué se hizo con el pedido ${c.pedido}`} className="h-11 rounded-sm bg-zinc-950 border-zinc-700" />
            <Button variant="outline" onClick={() => resolver(c)} className="h-11 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs"><CheckCircle size={14} className="mr-1.5" /> Cerrar caso</Button>
          </li>))}</ul>)}
    </div>
  );
}

function Prompts() {
  const [lista, setLista] = useState(null);
  const [abierto, setAbierto] = useState(null);
  const [texto, setTexto] = useState("");
  const [guardando, setGuardando] = useState(false);
  const cargar = useCallback(() => api.get("/zcall/cerebro/prompts").then((r) => setLista(r.data.prompts || []))
    .catch((e) => { toast.error(errorText(e)); setLista([]); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  const abrir = (p) => { setAbierto(p); setTexto(p.contenido); };
  const guardar = async () => {
    if (texto.trim().length < 200) { toast.error("El texto debe tener al menos 200 caracteres."); return; }
    setGuardando(true);
    try { const r = await api.put(`/zcall/cerebro/prompts/${abierto.proceso}/${abierto.tipo}`, { contenido: texto });
      toast.success(`Guardado como versión ${r.data.version}. La anterior quedó guardada.`); setAbierto(null); await cargar(); }
    catch (e) { toast.error(errorText(e)); } finally { setGuardando(false); }
  };
  return (
    <div className={`${caja} p-5 space-y-3`} data-testid="cm-prompts">
      <div className={rotulo}>Instrucciones de los asistentes{lista ? ` · ${lista.length}` : ""}</div>
      {lista === null ? <p className="text-sm text-zinc-400">Cargando…</p> : (
        <div className="flex flex-wrap gap-2">{lista.map((p) => (
          <button key={p.id} type="button" onClick={() => abrir(p)} aria-pressed={abierto?.id === p.id}
                  className={`min-h-[44px] px-3 rounded-sm border text-sm text-left ${abierto?.id === p.id ? "border-fuchsia-400/70 bg-fuchsia-500/10 text-white" : "border-zinc-800 text-zinc-200 hover:bg-zinc-900"}`}>
            {p.proceso === "maestro" ? "Cerebro central" : NOMBRE[p.proceso] || p.proceso} · {p.tipo === "voz" ? "Voz" : "Texto"}
            <span className="block text-[11px] text-zinc-400">Versión {p.version}{p.propio ? " · tuya" : " · base"}{p.nota != null ? ` · nota ${p.nota}` : ""}</span>
          </button>))}</div>)}
      {abierto && (
        <div className="space-y-2">
          <label className="text-xs text-zinc-300 block">Texto de la instrucción
            <textarea value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={12000} rows={16} data-testid="cm-prompt-texto"
                      className="mt-1 w-full rounded-sm bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 p-3 font-mono leading-relaxed" /></label>
          <div className="flex flex-wrap gap-2 items-center">
            <Button onClick={guardar} disabled={guardando || texto === abierto.contenido} className="h-11 rounded-sm text-xs">{guardando ? "Guardando…" : "Guardar versión nueva"}</Button>
            <Button variant="outline" onClick={() => setAbierto(null)} className="h-11 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">Cancelar</Button>
            <span className="text-[11px] text-zinc-400">Al guardar se crea una versión tuya; la anterior no se borra.</span>
          </div>
        </div>)}
    </div>
  );
}

export default function ControlMando() {
  const [d, setD] = useState(null);
  const [cola, setCola] = useState(null);
  const [pedido, setPedido] = useState(null);
  const cargar = useCallback(() => api.get("/zcall/cerebro/control").then((r) => setD(r.data))
    .catch((e) => { toast.error(errorText(e)); setD({ conectado: false }); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  if (d === null) return <p className="text-sm text-zinc-400">Cargando…</p>;
  if (!d.conectado || !d.vinculado) return <div className={`${caja} p-5 text-sm text-zinc-300`} data-testid="cm-sin-conectar">El control de mando se llena cuando tu operación está conectada. Revisa la pestaña Panel.</div>;
  const c = d.cierre_30d || {};
  const u = d.ultima_corrida;
  const q = d.datos || {};
  const pe = d.persona || {};
  return (
    <div className="space-y-5" data-testid="control-mando">
      <div className="flex flex-wrap gap-2 text-[11px] text-zinc-100">
        <span className="px-2 py-1 rounded-sm border border-zinc-600 bg-zinc-800">Modo {d.modo === "sombra" ? "sombra: decide y anota, no envía nada" : d.modo}</span>
        <span className="px-2 py-1 rounded-sm border border-zinc-600 bg-zinc-800">{d.reglas} reglas activas</span>
        <span className="px-2 py-1 rounded-sm border border-zinc-600 bg-zinc-800"><ClockCounterClockwise size={12} className="inline mr-1" />Última revisión: {u ? fechaHora(u.fin || u.inicio) : "aún no corre"}</span>
        <span className="px-2 py-1 rounded-sm border border-zinc-600 bg-zinc-800">Corte: {fechaHora(d.corte)}</span>
      </div>
      {q.alerta && <div className="border border-amber-300/60 bg-amber-500/10 rounded-sm p-3 text-sm text-amber-100" data-testid="cm-alerta">{q.alerta}</div>}
      <div className={`${caja} p-4`} data-testid="cm-datos">
        <div className={`${rotulo} mb-2`}>Con qué datos decide</div>
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-4 text-sm text-zinc-200">
          <div><div className="text-2xl font-semibold text-white tabular-nums">{q.activos ?? "—"}</div><div className="text-[11px] text-zinc-400">pedidos activos de {q.pedidos ?? "—"} cargados · leídos de Dropi {fechaHora(q.ultima_carga)}</div></div>
          <div><div className="text-2xl font-semibold text-white tabular-nums">{q.pct_telefono != null ? `${q.pct_telefono} %` : "sin dato"}</div><div className="text-[11px] text-zinc-400">de los activos tienen teléfono ({q.activos_con_telefono ?? 0})</div></div>
          <div><div className="text-2xl font-semibold text-white tabular-nums">{q.pct_fecha_confiable != null ? `${q.pct_fecha_confiable} %` : "sin dato"}</div><div className="text-[11px] text-zinc-400">con fecha exacta del estado; en el resto los días son un mínimo</div></div>
          <div><div className="text-2xl font-semibold text-white tabular-nums">{c.tasa != null ? `${c.tasa} %` : "sin dato"}</div><div className="text-[11px] text-zinc-400">entrega vista desde {fechaHora(c.desde)}: {c.entregados || 0} entregados, {c.devueltos || 0} devueltos{d.cierre_total?.tasa != null ? ` · histórico cargado ${d.cierre_total.tasa} %` : ""}</div></div>
        </div>
      </div>
      <div>
        <div className={`${rotulo} mb-2`}>Informe por proceso · hoy</div>
        <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {(d.procesos || []).filter((p) => p.proceso !== "cierre").map((p) => (
            <button key={p.proceso} type="button" onClick={() => { setCola(p.proceso); setPedido(null); }} aria-pressed={cola === p.proceso} data-testid={`cm-proceso-${p.proceso}`}
                    className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === p.proceso ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
              <div className="text-xs text-zinc-200">{NOMBRE[p.proceso]}</div>
              <div className="text-3xl font-semibold text-white tabular-nums mt-1">{p.activos}</div>
              <div className="text-[11px] text-zinc-400">pedidos activos</div>
              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-[11px] text-zinc-300">
                <span><ChatText size={12} className="inline mr-1" />{p.mensajes_hoy} mensajes</span>
                <span><PhoneCall size={12} className="inline mr-1" />{p.llamadas_hoy} llamadas</span>
                <span><User size={12} className="inline mr-1" />{p.para_persona} a persona</span>
                <span>{p.registros_hoy} registros del cliente</span>
                <span>{p.accionables ?? 0} piden acción</span>
                {p.sin_telefono > 0 && <span className="text-amber-300">{p.sin_telefono} sin teléfono</span>}
              </div>
            </button>))}
          <button type="button" onClick={() => { setCola("postventa"); setPedido(null); }} aria-pressed={cola === "postventa"} data-testid="cm-proceso-postventa"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "postventa" ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Postventa</div>
            <div className="text-3xl font-semibold text-white tabular-nums mt-1">{d.extra?.postventa_hoy ?? 0}</div>
            <div className="text-[11px] text-zinc-400">clientes con un paso de postventa hoy (gracias, encuesta, guía, referidos, segunda compra)</div>
          </button>
          <button type="button" onClick={() => { setCola("proveedores"); setPedido(null); }} aria-pressed={cola === "proveedores"} data-testid="cm-proceso-proveedores"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "proveedores" ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Proveedores</div>
            <div className="text-3xl font-semibold text-white tabular-nums mt-1">{d.extra?.proveedores_hoy ?? 0}</div>
            <div className="text-[11px] text-zinc-400">pedidos para reclamarle al proveedor: sin despacho en 48 h o sin movimiento</div>
          </button>
          <button type="button" onClick={() => { setCola("prompts"); setPedido(null); }} aria-pressed={cola === "prompts"} data-testid="cm-proceso-prompts"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "prompts" ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Instrucciones de los asistentes</div>
            <div className="text-3xl font-semibold text-white tabular-nums mt-1">{d.reglas}</div>
            <div className="text-[11px] text-zinc-400">reglas activas · toca para ver y editar lo que dice cada asistente</div>
          </button>
          <button type="button" onClick={() => { setCola("persona"); setPedido(null); }} aria-pressed={cola === "persona"} data-testid="cm-proceso-persona"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "persona" ? "border-amber-300/70 bg-amber-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Para una persona</div>
            <div className="text-3xl font-semibold text-white tabular-nums mt-1">{d.para_persona}</div>
            <div className="text-[11px] text-zinc-400">casos abiertos que el motor no decide solo{pe.mas_antiguo_horas != null ? ` · el más viejo lleva ${pe.mas_antiguo_horas} h` : ""} · hoy cerró {pe.cerrados_hoy ?? 0} el equipo y {pe.cerrados_solos_hoy ?? 0} se cerraron solos</div>
          </button>
        </div>
      </div>
      {(d.sin_regla || []).length > 0 && (
        <div className={`${caja} p-4 text-sm text-zinc-200`} data-testid="cm-sin-regla">
          <div className={rotulo}>Reglas que faltan</div>
          <p className="mt-1">Estos estados no tienen regla y pasaron a una persona: {d.sin_regla.map((s) => `${s.estado} (${s.n})`).join(", ")}.</p>
        </div>)}
      {cola === "prompts" ? <Prompts /> : cola === "persona" ? <Persona onAbrir={setPedido} recargar={cargar} /> : cola ? <Cola proceso={cola} onAbrir={setPedido} /> : null}
      {pedido && <Linea pedido={pedido} onCerrar={() => setPedido(null)} />}
    </div>
  );
}
