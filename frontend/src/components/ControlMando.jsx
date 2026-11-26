import { useCallback, useEffect, useMemo, useState } from "react";
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
            <div className="text-[11px] text-zinc-400 mt-1">{dec.estado} · {dec.fecha_confiable ? "" : "cerca de "}{dec.dias ?? "—"} días en este estado{dec.fecha_confiable ? "" : " (estimado: se vio por primera vez ya así)"}{dec.fuente ? ` · Regla: ${dec.fuente}` : ""}</div>
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

const DIAS = [["", "Cualquier antigüedad"], ["0-1", "Menos de 1 día"], ["1-3", "1 a 3 días"], ["3-7", "3 a 7 días"], ["7-999", "Más de 7 días"]];
const CREADO = [["", "Creado cuando sea"], ["1", "Creado hoy o ayer"], ["3", "Últimos 3 días"], ["7", "Últimos 7 días"], ["15", "Últimos 15 días"], ["30", "Últimos 30 días"]];
const sel = "h-11 rounded-sm bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 px-2 min-w-0";
const unicos = (filas, k) => [...new Set(filas.map((f) => f[k]).filter(Boolean))].sort();

function Cola({ proceso, onAbrir }) {
  const [filas, setFilas] = useState(null);
  const [f, setF] = useState({ q: "", estado: "", transportadora: "", ciudad: "", etiqueta: "", canal: "", producto: "", dias: "", creado: "", accion: false, tel: "" });
  const [ver, setVer] = useState(100);
  useEffect(() => { setFilas(null); setVer(100);
    setF({ q: "", estado: "", transportadora: "", ciudad: "", etiqueta: "", canal: "", producto: "", dias: "", creado: "", accion: false, tel: "" });
    api.get("/zcall/cerebro/cola", { params: { proceso, limite: 1000 } }).then((r) => setFilas(r.data.filas || []))
      .catch((e) => { toast.error(errorText(e)); setFilas([]); }); }, [proceso]);
  const set = (k, v) => { setF((x) => ({ ...x, [k]: v })); setVer(100); };
  const vistas = useMemo(() => {
    if (!filas) return [];
    const q = f.q.trim().toLowerCase();
    const [dmin, dmax] = f.dias ? f.dias.split("-").map(Number) : [null, null];
    const desde = f.creado ? new Date(Date.now() - Number(f.creado) * 86400000).toISOString().slice(0, 10) : null;
    return filas.filter((r) =>
      (!q || String(r.pedido).includes(q) || String(r.guia || "").toLowerCase().includes(q) || String(r.ciudad || "").toLowerCase().includes(q) || String(r.producto || "").toLowerCase().includes(q))
      && (!f.estado || r.estado === f.estado) && (!f.transportadora || r.transportadora === f.transportadora)
      && (!f.ciudad || r.ciudad === f.ciudad) && (!f.etiqueta || r.etiqueta === f.etiqueta) && (!f.canal || r.canal === f.canal)
      && (!f.producto || r.producto === f.producto)
      && (dmin === null || (r.dias != null && r.dias >= dmin && r.dias < dmax))
      && (!desde || (r.creado && r.creado >= desde))
      && (!f.accion || r.accionable) && (!f.tel || (f.tel === "si" ? r.tiene_telefono : r.tiene_telefono === false)));
  }, [filas, f]);
  const activos = Object.entries(f).filter(([, v]) => v && v !== "").length;
  const conProducto = filas ? filas.filter((r) => r.producto).length : 0;
  return (
    <div className={`${caja} p-5`} data-testid="cm-cola">
      <div className={`${rotulo} mb-3`}>{NOMBRE[proceso]}{filas ? ` · ${vistas.length} de ${filas.length} · ${vistas.filter((r) => r.accionable).length} piden acción (van primero)` : ""}</div>
      {filas && filas.length > 0 && (
        <div className="grid gap-2 grid-cols-2 md:grid-cols-4 mb-3" data-testid="cm-filtros">
          <Input value={f.q} onChange={(e) => set("q", e.target.value)} placeholder="Buscar pedido, guía, ciudad o producto" aria-label="Buscar" className="h-11 rounded-sm bg-zinc-950 border-zinc-700 col-span-2" />
          <select aria-label="Estado" value={f.estado} onChange={(e) => set("estado", e.target.value)} className={sel}><option value="">Todos los estados</option>{unicos(filas, "estado").map((v) => <option key={v}>{v}</option>)}</select>
          <select aria-label="Qué toca" value={f.etiqueta} onChange={(e) => set("etiqueta", e.target.value)} className={sel}><option value="">Todas las etiquetas</option>{unicos(filas, "etiqueta").map((v) => <option key={v} value={v}>{limpio(v)}</option>)}</select>
          <select aria-label="Días en el estado" value={f.dias} onChange={(e) => set("dias", e.target.value)} className={sel}>{DIAS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
          <select aria-label="Fecha de creación" value={f.creado} onChange={(e) => set("creado", e.target.value)} className={sel}>{CREADO.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
          <select aria-label="Transportadora" value={f.transportadora} onChange={(e) => set("transportadora", e.target.value)} className={sel}><option value="">Todas las transportadoras</option>{unicos(filas, "transportadora").map((v) => <option key={v}>{v}</option>)}</select>
          <select aria-label="Ciudad" value={f.ciudad} onChange={(e) => set("ciudad", e.target.value)} className={sel}><option value="">Todas las ciudades</option>{unicos(filas, "ciudad").map((v) => <option key={v}>{v}</option>)}</select>
          <select aria-label="Canal" value={f.canal} onChange={(e) => set("canal", e.target.value)} className={sel}><option value="">Todos los canales</option>{unicos(filas, "canal").map((v) => <option key={v} value={v}>{CANAL[v] || v}</option>)}</select>
          <select aria-label="Producto" value={f.producto} onChange={(e) => set("producto", e.target.value)} className={sel}><option value="">{conProducto ? `Todos los productos (dato en ${conProducto} de ${filas.length})` : "Producto: sin dato todavía"}</option>{unicos(filas, "producto").map((v) => <option key={v}>{v}</option>)}</select>
          <select aria-label="Teléfono" value={f.tel} onChange={(e) => set("tel", e.target.value)} className={sel}><option value="">Con y sin teléfono</option><option value="si">Con teléfono</option><option value="no">Sin teléfono</option></select>
          <label className="text-xs text-zinc-300 flex items-center gap-2 min-h-[44px]"><input type="checkbox" checked={f.accion} onChange={(e) => set("accion", e.target.checked)} className="h-5 w-5" /> Solo lo que pide acción</label>
          {activos > 0 && <Button variant="outline" onClick={() => { setF({ q: "", estado: "", transportadora: "", ciudad: "", etiqueta: "", canal: "", producto: "", dias: "", creado: "", accion: false, tel: "" }); setVer(100); }} className="h-11 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">Quitar filtros ({activos})</Button>}
        </div>)}
      {filas === null ? <p className="text-sm text-zinc-400">Cargando…</p> : filas.length === 0 ? <p className="text-sm text-zinc-400">No hay pedidos en esta cola hoy.</p> : vistas.length === 0 ? <p className="text-sm text-zinc-400">Ningún pedido cumple esos filtros.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[860px]">
            <thead><tr className="text-left text-[11px] text-zinc-400 uppercase tracking-wider">
              <th className="py-2 pr-3">Pedido</th><th className="pr-3">Estado</th><th className="pr-3">Días</th><th className="pr-3">Etiqueta</th><th className="pr-3">Qué toca</th><th className="pr-3">Ciudad</th><th className="pr-3">Transportadora</th><th className="pr-3">Valor</th><th>Producto / último registro</th></tr></thead>
            <tbody>{vistas.slice(0, ver).map((r) => (
              <tr key={`${r.pedido}-${r.accion}`} onClick={() => onAbrir(r.pedido)} tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") onAbrir(r.pedido); }}
                  className="border-t border-zinc-800 hover:bg-zinc-900 cursor-pointer text-zinc-200">
                <td className="py-2.5 pr-3 tabular-nums text-white">{r.pedido}<div className="text-[11px] text-zinc-500">{r.creado || ""}</div></td><td className="pr-3">{r.estado}</td>
                <td className="pr-3 tabular-nums" title={r.fecha_confiable ? "Días desde que se vio el cambio de estado" : "Estimado: se vio por primera vez ya en este estado"}>{r.fecha_confiable ? "" : "≈ "}{r.dias ?? "—"}</td>
                <td className="pr-3">{r.escala && <WarningCircle size={13} className="inline mr-1 text-amber-300" aria-label="Pasa a una persona" />}{limpio(r.etiqueta)}</td>
                <td className="pr-3">{limpio(r.accion)} · {CANAL[r.canal] || r.canal}{r.verificar_antes && <span className="block text-[11px] text-amber-300">verificar en la transportadora antes de contactar</span>}{r.repetido_cliente && <span className="block text-[11px] text-amber-300">mismo cliente ya tiene otro contacto hoy</span>}{r.plantilla_lista === false && <span className="block text-[11px] text-amber-300">falta asignar la plantilla</span>}</td>
                <td className="pr-3">{r.ciudad || "—"}{r.tiene_telefono === false && <span className="block text-[11px] text-amber-300">sin teléfono</span>}</td>
                <td className="pr-3">{r.transportadora || "—"}</td><td className="pr-3 tabular-nums">{cop(r.valor)}</td>
                <td className="text-zinc-400 max-w-[220px] truncate">{r.ultimo_dicho || r.producto || "—"}</td>
              </tr>))}</tbody>
          </table>
          {vistas.length > ver && <Button variant="outline" onClick={() => setVer((n) => n + 200)} className="mt-3 h-11 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">Ver 200 más ({vistas.length - ver} sin mostrar)</Button>}
        </div>)}
    </div>
  );
}

function Catalogo({ c, fuente, recargar }) {
  const [q, setQ] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const actualizar = async () => { setOcupado(true);
    try { const r = await api.post("/zcall/cerebro/catalogo/actualizar"); (r.data?.pendiente ? toast.info : toast.success)(r.data?.mensaje || "Listo."); await recargar(); }
    catch (e) { toast.error(errorText(e)); } finally { setOcupado(false); } };
  const lista = (c?.lista || []).filter((p) => !q || p.nombre.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className={`${caja} p-5`} data-testid="cm-catalogo">
      <div className={`${rotulo} mb-1`}>Catálogo · {c?.productos || 0} productos · {c?.activos || 0} activos</div>
      <p className="text-[11px] text-zinc-400 mb-3">Se copia de {c?.fuente || "tu bot de ventas"}; aquí no se cambian precios. Última copia: {fechaHora(c?.actualizado)}. Queda guardado para que los asistentes respondan producto y precio cuando se conecten a este catálogo.</p>
      <div className="flex flex-wrap gap-2 mb-3">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar producto" aria-label="Buscar producto" className="h-11 rounded-sm bg-zinc-950 border-zinc-700 flex-1 basis-56" />
        <Button variant="outline" onClick={actualizar} disabled={ocupado} data-testid="cm-catalogo-actualizar" className="h-11 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">{ocupado ? "Actualizando…" : "Actualizar ahora"}</Button>
      </div>
      <p className="text-[11px] text-zinc-400 mb-3">Se actualiza solo una vez al día.{fuente?.ultimo_ok ? ` Última actualización desde Chatea: ${fechaHora(fuente.ultimo_ok)}.` : ""}{fuente?.error ? ` ${fuente.error}.` : ""}</p>
      {lista.length === 0 ? <p className="text-sm text-zinc-400">No hay productos que mostrar.</p> : (
        <ul className="divide-y divide-zinc-800">{lista.map((p, i) => (
          <li key={`${p.nombre}-${p.id_dropi}-${i}`} className="py-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <span className="text-zinc-100 flex-1 basis-56">{p.nombre}</span><span className="tabular-nums text-white">{cop(p.precio)}</span>
            <span className={`text-[11px] ${p.estado === "activo" ? "text-green-400" : "text-zinc-500"}`}>{p.estado}</span>
            <span className="text-[11px] text-zinc-400">{p.id_dropi ? `Dropi ${p.id_dropi}` : "sin ID de Dropi"}{p.complementos ? ` · ${p.complementos} complementos` : ""}</span>
          </li>))}</ul>)}
    </div>
  );
}

function Tienda({ t, recargar }) {
  const [v, setV] = useState({});
  const [g, setG] = useState(false);
  useEffect(() => { setV(t?.datos || {}); }, [t]);
  const guardar = async () => { setG(true);
    try { const r = await api.put("/zcall/cerebro/tienda", { datos: v }); toast.success(r.data?.por_revisar ? "Guardado. Para darlos por revisados completa los 7 datos." : r.data?.completo ? "Datos de la tienda completos." : `Guardado. Faltan: ${(r.data?.faltan || []).join(", ")}`); await recargar(); }
    catch (e) { toast.error(errorText(e)); } finally { setG(false); } };
  const faltan = t?.faltan || [];
  return (
    <div className={`${caja} p-5 space-y-3`} data-testid="cm-tienda">
      <div className={rotulo}>Datos de tu tienda · {(t?.campos || []).length - faltan.length} de {(t?.campos || []).length}{t?.fuente === "precargado" ? " · por revisar" : ""}</div>
      <p className="text-[11px] text-zinc-400">Con esto se arman los guiones de tus asistentes: los guiones armados llevan solo estos datos y se ponen al día cuando guardas. Sin los 7 datos no se puede crear un guion propio.{t?.fuente === "precargado" ? " Estos datos se precargaron: revísalos y corrige lo que no sea exacto." : ""}</p>
      {(t?.campos || []).map((c) => (
        <label key={c.k} className="text-xs text-zinc-300 block">{c.t}{faltan.includes(c.t) && <span className="text-amber-300"> · falta</span>}
          <textarea value={v[c.k] || ""} onChange={(e) => setV((x) => ({ ...x, [c.k]: e.target.value }))} maxLength={600} rows={2} data-testid={`cm-tienda-${c.k}`}
                    className="mt-1 w-full rounded-sm bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 p-2" /></label>))}
      <Button onClick={guardar} disabled={g} className="h-11 rounded-sm text-xs">{g ? "Guardando…" : "Guardar datos de la tienda"}</Button>
    </div>
  );
}

function Conocimiento() {
  const [d, setD] = useState(null);
  const [titulo, setTitulo] = useState("");
  const [contenido, setContenido] = useState("");
  const [g, setG] = useState(false);
  const cargar = useCallback(() => api.get("/zcall/cerebro/conocimiento").then((r) => setD(r.data)).catch((e) => { toast.error(errorText(e)); setD({ tuyas: [] }); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  const guardar = async () => {
    if (titulo.trim().length < 3 || contenido.trim().length < 10) { toast.error("Escribe un título y al menos una frase."); return; }
    setG(true);
    try { await api.post("/zcall/cerebro/conocimiento", { titulo, contenido }); toast.success("Nota guardada."); setTitulo(""); setContenido(""); await cargar(); }
    catch (e) { toast.error(errorText(e)); } finally { setG(false); } };
  const quitar = async (n) => { if (!window.confirm(`¿Quitar la nota «${n.titulo}»?`)) return; try { const r = await api.delete(`/zcall/cerebro/conocimiento/${n.id}`); setD(r.data); toast.success("Nota quitada."); } catch (e) { toast.error(errorText(e)); } };
  return (
    <div className={`${caja} p-5 space-y-3`} data-testid="cm-conocimiento">
      <div className={rotulo}>Base de conocimiento{d ? ` · ${(d.tuyas || []).length} notas tuyas` : ""}</div>
      {d?.base_zynex && <p className="text-sm text-zinc-300 border border-zinc-700 rounded-sm p-3">{d.base_zynex.aviso} ({d.base_zynex.notas} notas de método).</p>}
      <label className="text-xs text-zinc-300 block">Título
        <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} maxLength={120} placeholder="Ej.: Promoción de diciembre" className="mt-1 h-11 rounded-sm bg-zinc-950 border-zinc-700" /></label>
      <label className="text-xs text-zinc-300 block">Qué debe saber el asistente (se usará cuando los asistentes se conecten a esta base)
        <textarea value={contenido} onChange={(e) => setContenido(e.target.value)} maxLength={4000} rows={3} className="mt-1 w-full rounded-sm bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 p-2" /></label>
      <Button onClick={guardar} disabled={g} className="h-11 rounded-sm text-xs">{g ? "Guardando…" : "Agregar nota"}</Button>
      {d === null ? <p className="text-sm text-zinc-400">Cargando…</p> : (d.tuyas || []).length === 0 ? <p className="text-sm text-zinc-400">Todavía no has agregado notas propias.</p> : (
        <ul className="divide-y divide-zinc-800">{d.tuyas.map((n) => (<li key={n.id} className="py-2 text-sm flex gap-3 items-start"><div className="flex-1"><div className="text-zinc-100">{n.titulo}</div><div className="text-zinc-400 whitespace-pre-wrap">{n.contenido}</div></div>
          <Button variant="outline" onClick={() => quitar(n)} aria-label={`Quitar la nota ${n.titulo}`} className="h-11 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">Quitar</Button></li>))}</ul>)}
    </div>
  );
}

function Lote() {
  const [d, setD] = useState(null);
  const [o, setO] = useState(false);
  const cargar = useCallback(() => api.get("/zcall/cerebro/lote").then((r) => setD(r.data)).catch((e) => { toast.error(errorText(e)); setD({ filas: [] }); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  const armar = async () => { setO(true);
    try { const r = await api.post("/zcall/cerebro/lote/armar"); setD(r.data); const x = r.data?.resultado || {}; toast.success(`Lote armado: ${x.listos ?? 0} listos y ${x.bloqueados ?? 0} retenidos. No se envió nada.`); }
    catch (e) { toast.error(errorText(e)); } finally { setO(false); } };
  return (
    <div className={`${caja} p-5 space-y-3`} data-testid="cm-lote">
      <div className={rotulo}>Lote de confirmación · modo prueba</div>
      <p className="text-sm text-amber-200 border border-amber-500/40 rounded-sm p-3">{d?.aviso || "Vista previa. Nada se envía."}</p>
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={armar} disabled={o} data-testid="cm-lote-armar" className="h-11 rounded-sm text-xs">{o ? "Armando…" : "Armar lote de hoy (hasta 20)"}</Button>
        {d?.resumen && <span className="text-sm text-zinc-300">Hoy: {d.resumen.listos} listos · {d.resumen.bloqueados} retenidos · {d.resumen.enviados} enviados</span>}
      </div>
      {(d?.causas || []).length > 0 && <ul className="text-[11px] text-zinc-400 list-disc pl-4">{d.causas.map((c) => <li key={c.causa}>{c.n} · {c.causa}</li>)}</ul>}
      {d === null ? <p className="text-sm text-zinc-400">Cargando…</p> : (d.filas || []).length === 0 ? <p className="text-sm text-zinc-400">Todavía no hay lote de hoy.</p> : (
        <ul className="space-y-2">{d.filas.map((f) => (
          <li key={f.id} className="border border-zinc-800 rounded-sm p-3 text-sm">
            <div className="text-zinc-100"><span className="tabular-nums">{f.pedido}</span> · {f.ciudad || "—"} · {cop(f.valor)} · <span className={f.estado === "listo" ? "text-emerald-300" : "text-amber-300"}>{f.estado === "listo" ? "listo para aprobar" : "retenido"}</span></div>
            <div className="text-[11px] text-zinc-400">{f.plantilla || "sin plantilla"}</div>
            {(f.bloqueos || []).map((b) => <div key={b} className="text-[11px] text-amber-300">• {b}</div>)}
            {f.vista_previa && <pre className="mt-2 text-[11px] text-zinc-300 whitespace-pre-wrap border-t border-zinc-800 pt-2">{f.vista_previa}</pre>}
          </li>))}</ul>)}
    </div>
  );
}

function Secuencia({ pasos }) {
  const [proc, setProc] = useState("pendientes");
  const lista = (pasos || []).filter((p) => p.proceso === proc);
  return (
    <div className={`${caja} p-5`} data-testid="cm-secuencia">
      <div className={`${rotulo} mb-3`}>Plan de secuencias · qué hace el motor según el estado y los días</div>
      <div className="flex flex-wrap gap-2 mb-3">{["pendientes", "seguimiento", "novedades", "oficina", "postventa", "cierre"].map((k) => (
        <button key={k} type="button" onClick={() => setProc(k)} aria-pressed={proc === k} className={`min-h-[44px] px-3 rounded-sm border text-sm ${proc === k ? "border-fuchsia-400/70 bg-fuchsia-500/10 text-white" : "border-zinc-800 text-zinc-200 hover:bg-zinc-900"}`}>{NOMBRE[k] || k}</button>))}</div>
      {lista.length === 0 ? <p className="text-sm text-zinc-400">Sin pasos para este proceso.</p> : (
        <div className="overflow-x-auto"><table className="w-full text-sm min-w-[760px]">
          <thead><tr className="text-left text-[11px] text-zinc-400 uppercase tracking-wider"><th className="py-2 pr-3">Estado</th><th className="pr-3">Días</th><th className="pr-3">Qué hace</th><th className="pr-3">Canal</th><th className="pr-3">Plantilla</th><th className="pr-3">Llamada</th><th>Persona</th></tr></thead>
          <tbody>{lista.map((p, i) => (
            <tr key={`${p.estado}-${p.desde_dia}-${i}`} className="border-t border-zinc-800 text-zinc-200">
              <td className="py-2 pr-3">{p.estado}</td><td className="pr-3 tabular-nums">{p.desde_dia}{p.hasta_dia != null ? ` a ${p.hasta_dia}` : " o más"}</td>
              <td className="pr-3">{limpio(p.accion)}</td><td className="pr-3">{CANAL[p.canal] || p.canal}</td>
              <td className="pr-3 font-mono text-[11px]">{p.casilla ? (p.plantilla || <span className="text-amber-300">falta asignar ({p.casilla})</span>) : "—"}</td>
              <td className="pr-3">{p.llamada_a_los_min == null ? "—" : p.llamada_a_los_min === 0 ? "de inmediato" : `a los ${p.llamada_a_los_min} min`}</td>
              <td>{p.pasa_a_persona ? "Sí" : "No"}</td>
            </tr>))}</tbody></table></div>)}
    </div>
  );
}

function Persona({ onAbrir, recargar }) {
  const [casos, setCasos] = useState(null);
  const [nota, setNota] = useState({});
  const [fq, setFq] = useState(""); const [fp, setFp] = useState(""); const [fd, setFd] = useState("");
  const cargar = useCallback(() => api.get("/zcall/cerebro/persona").then((r) => setCasos(r.data.casos || []))
    .catch((e) => { toast.error(errorText(e)); setCasos([]); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  const resolver = async (c) => {
    const n = (nota[c.id] || "").trim();
    if (n.length < 5) { toast.error("Escribe qué se hizo con el caso (mínimo 5 letras)."); return; }
    try { await api.post(`/zcall/cerebro/persona/${c.id}/resolver`, { nota: n }); toast.success("Caso cerrado. No se vuelve a abrir en 24 horas."); setNota((s) => ({ ...s, [c.id]: "" })); await cargar(); recargar(); }
    catch (e) { toast.error(errorText(e)); }
  };
  const procesos = [...new Set((casos || []).map((c) => c.proceso).filter(Boolean))];
  const vistos = (casos || []).filter((c) => (!fp || c.proceso === fp) && (!fd || (c.dias ?? 0) >= Number(fd))
    && (!fq || `${c.pedido} ${c.estado || ""} ${c.ciudad || ""} ${c.motivo || ""} ${c.motivo_texto || ""}`.toLowerCase().includes(fq.toLowerCase())));
  const sel = "h-11 rounded-sm bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 px-2";
  return (
    <div className={`${caja} p-5`} data-testid="cm-persona">
      <div className={`${rotulo} mb-3`}>Casos para una persona{casos ? ` · ${vistos.length} de ${casos.length}` : ""}</div>
      {casos && casos.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3" data-testid="cm-persona-filtros">
          <Input value={fq} onChange={(e) => setFq(e.target.value)} placeholder="Buscar pedido, ciudad, estado o motivo" aria-label="Buscar en casos" className="h-11 rounded-sm bg-zinc-950 border-zinc-700 flex-1 basis-56" />
          <select value={fp} onChange={(e) => setFp(e.target.value)} aria-label="Proceso" className={sel}><option value="">Todos los procesos</option>{procesos.map((x) => <option key={x} value={x}>{NOMBRE[x] || x}</option>)}</select>
          <select value={fd} onChange={(e) => setFd(e.target.value)} aria-label="Días en el estado" className={sel}><option value="">Cualquier tiempo</option><option value="3">3 días o más</option><option value="7">7 días o más</option><option value="15">15 días o más</option></select>
        </div>)}
      {casos === null ? <p className="text-sm text-zinc-400">Cargando…</p> : casos.length === 0 ? <p className="text-sm text-zinc-400">No hay casos abiertos.</p> : vistos.length === 0 ? <p className="text-sm text-zinc-400">Ningún caso coincide con los filtros.</p> : (
        <ul className="space-y-2">{vistos.map((c) => (
          <li key={c.id} className="border border-zinc-800 rounded-sm p-3 grid gap-2 md:grid-cols-[1fr_1fr_auto] items-center text-sm">
            <button type="button" onClick={() => onAbrir(c.pedido)} className="text-left min-h-[44px]">
              <span className="text-white tabular-nums">{c.pedido}</span> <span className="text-zinc-300">· {c.estado || "—"} · {c.fecha_confiable ? "" : "≈ "}{c.dias ?? "—"} días</span>
              <div className="text-[11px] text-zinc-400">{NOMBRE[c.proceso] || c.proceso} · {limpio(c.motivo)} · {c.ciudad || "—"} · {cop(c.valor)} · abierto hace {c.horas_abierto ?? "—"} h{c.tiene_telefono === false ? " · sin teléfono" : ""}</div>
              {c.motivo_texto && <div className="text-[11px] text-zinc-300">{c.motivo_texto}</div>}
              {c.edad_pedido_dias != null && <div className="text-[11px] text-zinc-400">Pedido creado hace {c.edad_pedido_dias} días{c.fecha_tipo === "estimada" || c.fecha_tipo === "minima" ? " · fecha del estado estimada" : ""}</div>}
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
  const abrir = (p) => { setAbierto(p); setTexto(p.contenido || ""); setIdea(""); setVista(""); };
  const [idea, setIdea] = useState("");
  const [vista, setVista] = useState("");
  const armar = async () => {
    if (idea.trim().length < 40) { toast.error("Cuéntalo en al menos dos frases."); return; }
    setGuardando(true);
    try { const r = await api.post(`/zcall/cerebro/guion/${abierto.proceso}/${abierto.tipo}`, { texto: idea });
      toast.success(`Guion armado y guardado como versión ${r.data.version}.`); setVista(r.data.vista_previa || ""); await cargar(); }
    catch (e) { toast.error(errorText(e)); } finally { setGuardando(false); }
  };
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
          {abierto.protegido && <p className="text-sm text-zinc-300 border border-zinc-700 rounded-sm p-3" data-testid="cm-prompt-protegido">{abierto.resumen} Mínimo para que funcione: nombre de la tienda, qué vendes, tiempo de entrega, garantía y cambios, medios de pago, horario y a quién se pasa el caso.</p>}
          {abierto.proceso !== "maestro" && (
            <div className="border border-zinc-700 rounded-sm p-3 space-y-2" data-testid="cm-guion-armar">
              <label className="text-xs text-zinc-300 block">Cuéntame con tus palabras cómo quieres que hable este asistente y qué debe lograr; yo armo el guion con los datos de tu tienda
                <textarea value={idea} onChange={(e) => setIdea(e.target.value)} maxLength={3000} rows={3} placeholder="Ej.: Que salude por el nombre, confirme dirección y valor, y si el cliente duda le recuerde que paga al recibir." className="mt-1 w-full rounded-sm bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 p-2" /></label>
              <Button onClick={armar} disabled={guardando} className="h-11 rounded-sm text-xs">{guardando ? "Armando…" : "Armar mi guion"}</Button>
              {vista && <pre className="text-[11px] text-zinc-300 whitespace-pre-wrap border-t border-zinc-800 pt-2">{vista}</pre>}
            </div>)}
          <label className="text-xs text-zinc-300 block">{abierto.protegido ? "O escribe tu versión completa (opcional)" : "Texto de la instrucción"}
            <textarea value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={12000} rows={16} data-testid="cm-prompt-texto"
                      className="mt-1 w-full rounded-sm bg-zinc-950 border border-zinc-700 text-sm text-zinc-100 p-3 font-mono leading-relaxed" /></label>
          <div className="flex flex-wrap gap-2 items-center">
            <Button onClick={guardar} disabled={guardando || texto === (abierto.contenido || "")} className="h-11 rounded-sm text-xs">{guardando ? "Guardando…" : "Guardar versión nueva"}</Button>
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
      {(q.alertas || []).length > 0 && <ul className="border border-amber-300/60 bg-amber-500/10 rounded-sm p-3 text-sm text-amber-100 space-y-1" data-testid="cm-alerta">{q.alertas.map((t) => <li key={t}>{t}</li>)}</ul>}
      <div className={`${caja} p-4`} data-testid="cm-datos">
        <div className={`${rotulo} mb-2`}>Con qué datos decide</div>
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-4 text-sm text-zinc-200">
          <div><div className="text-2xl font-semibold text-white tabular-nums">{q.activos ?? "—"}</div><div className="text-[11px] text-zinc-400">pedidos activos de {q.pedidos ?? "—"} cargados · leídos de Dropi {fechaHora(q.ultima_carga)}</div></div>
          <div><div className="text-2xl font-semibold text-white tabular-nums">{q.pct_telefono != null ? `${q.pct_telefono} %` : "sin dato"}</div><div className="text-[11px] text-zinc-400">de los activos tienen teléfono ({q.activos_con_telefono ?? 0})</div></div>
          <div><div className="text-2xl font-semibold text-white tabular-nums">{q.pct_fecha_confiable != null ? `${q.pct_fecha_confiable} %` : "sin dato"}</div><div className="text-[11px] text-zinc-400">con fecha exacta del estado; en el resto los días son estimados</div></div>
          <div><div className="text-2xl font-semibold text-white tabular-nums">{c.tasa != null ? `${c.tasa} %` : "sin dato"}</div><div className="text-[11px] text-zinc-400">entrega vista desde {fechaHora(c.desde)}: {c.entregados || 0} entregados, {c.devueltos || 0} devueltos{c.aviso ? ` · ${c.aviso}` : ""}{d.cierre_total?.tasa != null ? ` · histórico cargado ${d.cierre_total.tasa} % (sale más alto que el real: lo que sigue en camino no cuenta)` : ""}</div></div>
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
          <button type="button" onClick={() => { setCola("tienda"); setPedido(null); }} aria-pressed={cola === "tienda"} data-testid="cm-proceso-tienda"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "tienda" ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Datos de tu tienda</div>
            <div className="text-3xl font-semibold text-white tabular-nums mt-1">{(d.extra?.tienda?.campos || []).length - (d.extra?.tienda?.faltan || []).length} de {(d.extra?.tienda?.campos || []).length}</div>
            <div className="text-[11px] text-zinc-400">{d.extra?.tienda?.fuente === "precargado" ? "precargados: revísalos y guárdalos una vez" : "envío, garantía, cambios, pagos y soporte: la base de tus guiones"}</div>
          </button>
          <button type="button" onClick={() => { setCola("conocimiento"); setPedido(null); }} aria-pressed={cola === "conocimiento"} data-testid="cm-proceso-conocimiento"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "conocimiento" ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Base de conocimiento</div>
            <div className="text-3xl font-semibold text-white tabular-nums mt-1">{d.extra?.conocimiento?.tuyas ?? 0}</div>
            <div className="text-[11px] text-zinc-400">notas tuyas · {d.extra?.conocimiento?.base_zynex ?? 0} de método Zynex, protegidas</div>
          </button>
          <button type="button" onClick={() => { setCola("catalogo"); setPedido(null); }} aria-pressed={cola === "catalogo"} data-testid="cm-proceso-catalogo"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "catalogo" ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Catálogo</div>
            <div className="text-3xl font-semibold text-white tabular-nums mt-1">{d.extra?.catalogo?.activos ?? 0}</div>
            <div className="text-[11px] text-zinc-400">productos activos con precio, copiados de tu bot de ventas</div>
          </button>
          <button type="button" onClick={() => { setCola("lote"); setPedido(null); }} aria-pressed={cola === "lote"} data-testid="cm-proceso-lote"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "lote" ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Lote de confirmación</div>
            <div className="text-3xl font-semibold text-white mt-1">Prueba</div>
            <div className="text-[11px] text-zinc-400">arma los mensajes de hoy con sus datos y muestra cuáles se retienen; no envía</div>
          </button>
          <button type="button" onClick={() => { setCola("secuencia"); setPedido(null); }} aria-pressed={cola === "secuencia"} data-testid="cm-proceso-secuencia"
                  className={`text-left p-4 rounded-sm border min-h-[120px] ${cola === "secuencia" ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
            <div className="text-xs text-zinc-200">Plan de secuencias</div>
            <div className="text-3xl font-semibold text-white tabular-nums mt-1">{(d.extra?.secuencia || []).length}</div>
            <div className="text-[11px] text-zinc-400">pasos por estado y días: mensaje, llamada, plantilla y cuándo pasa a una persona</div>
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
            <div className="text-[11px] text-zinc-400">casos abiertos que el motor no decide solo{pe.mas_antiguo_horas != null ? ` · el más viejo lleva ${pe.mas_antiguo_horas} h` : ""} · hoy cerró {pe.cerrados_hoy ?? 0} el equipo y {pe.cerrados_solos_hoy ?? 0} se cerraron solos{d.extra?.casos_fecha_estimada ? ` · ${d.extra.casos_fecha_estimada} con fecha estimada` : ""}</div>
          </button>
        </div>
      </div>
      {(d.sin_regla || []).length > 0 && (
        <div className={`${caja} p-4 text-sm text-zinc-200`} data-testid="cm-sin-regla">
          <div className={rotulo}>Reglas que faltan</div>
          <p className="mt-1">Estos estados no tienen regla y pasaron a una persona: {d.sin_regla.map((s) => `${s.estado} (${s.n})`).join(", ")}.</p>
        </div>)}
      {cola === "lote" ? <Lote /> : cola === "tienda" ? <Tienda t={d.extra?.tienda} recargar={cargar} /> : cola === "conocimiento" ? <Conocimiento /> : cola === "catalogo" ? <Catalogo c={d.extra?.catalogo} fuente={d.extra?.catalogo_fuente} recargar={cargar} /> : cola === "secuencia" ? <Secuencia pasos={d.extra?.secuencia} /> : cola === "prompts" ? <Prompts /> : cola === "persona" ? <Persona onAbrir={setPedido} recargar={cargar} /> : cola ? <Cola proceso={cola} onAbrir={setPedido} /> : null}
      {pedido && <Linea pedido={pedido} onCerrar={() => setPedido(null)} />}
    </div>
  );
}
