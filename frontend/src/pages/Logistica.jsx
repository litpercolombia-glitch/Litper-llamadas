import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import PendientesChatea from "../components/PendientesChatea";
import {
  Package, ArrowsClockwise, ChartBar, ChatText, ChatsCircle, PhoneCall, WhatsappLogo, User, CheckCircle, WarningCircle, X, ListChecks, Path,
} from "@phosphor-icons/react";

/** Agente de Logística: panel por estado de Dropi (cada número abre su lista),
 *  casillas de plantilla del cliente y la secuencia mensaje → llamada → WhatsApp. */
const TABS = [
  { key: "panel",     label: "Panel",      Icon: Package,    desc: "Pedidos por estado de Dropi. Toca un número para ver los pedidos." },
  { key: "metricas",  label: "Métricas",   Icon: ChartBar,   desc: "Cómo va tu operación. Toca un número para ver los pedidos que lo forman." },
  { key: "pendientes", label: "Pendientes", Icon: ChatsCircle, desc: "Chats de Chatea que quedaron a medias: qué columnas trabaja el agente y con qué reglas." },
  { key: "casillas",  label: "Plantillas", Icon: ListChecks, desc: "Pon en cada casilla la plantilla de WhatsApp que tú quieras usar." },
  { key: "secuencia", label: "Secuencia",  Icon: Path,       desc: "Qué se hace con cada estado: mensaje, llamada y WhatsApp de seguimiento." },
];
const CANAL = {
  chatea_mensaje:       { txt: "Mensaje por Chatea",        Icon: ChatText },
  llamada:              { txt: "Llamada",                   Icon: PhoneCall },
  whatsapp_seguimiento: { txt: "WhatsApp de seguimiento",   Icon: WhatsappLogo },
  humano:               { txt: "Persona del equipo",        Icon: User },
};
const cop = (v) => (v ? `$${Number(v).toLocaleString("es-CO")}` : "—");
const espera = (m) => (!m ? "de inmediato" : m < 60 ? `a los ${m} min` : m < 1440 ? `a las ${Math.round(m / 60)} h` : `al día ${Math.round(m / 1440)}`);
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";

function Tarjeta({ titulo, n, sub, activa, onClick, testId }) {
  return (
    <button type="button" onClick={onClick} data-testid={testId} aria-pressed={activa}
            className={`text-left p-4 rounded-sm border transition-colors min-h-[88px] min-w-0 ${
              activa ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
      <div className="text-2xl sm:text-3xl font-semibold text-white tabular-nums break-words">{n}</div>
      <div className="text-xs text-zinc-200 mt-1">{titulo}</div>
      {sub && <div className="text-[11px] text-zinc-400 mt-0.5">{sub}</div>}
    </button>
  );
}

function Lista({ clave, titulo, onCerrar, dias }) {
  const [filas, setFilas] = useState(null);
  useEffect(() => {
    setFilas(null);
    const metrica = clave.startsWith("m:");
    api.get(metrica ? "/zcall/motor/metricas/lista" : "/zcall/motor/lista", { params: metrica ? { clave, dias } : { clave } })
      .then((r) => setFilas(r.data.filas || []))
      .catch((e) => { toast.error(errorText(e)); setFilas([]); });
  }, [clave, dias]);
  return (
    <div className={`${caja} p-5`} data-testid="log-lista">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className={rotulo}>{titulo}{filas ? ` · ${filas.length}` : ""}</div>
        <button type="button" onClick={onCerrar} aria-label="Cerrar lista"
                className="h-9 w-9 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><X size={16} /></button>
      </div>
      {filas === null ? <p className="text-sm text-zinc-400">Cargando…</p>
        : filas.length === 0 ? <p className="text-sm text-zinc-400">No hay pedidos aquí en este momento.</p>
        : (
          <div className="overflow-x-auto relative" tabIndex={0} role="region" aria-label={`Pedidos: ${titulo}`}>
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[11px] text-zinc-400 border-b border-zinc-800">
                {["Pedido", "Estado", "Ciudad", "Valor", "Transportadora", "Guía", "Días", "Qué haría", "Plantilla"].map((h) =>
                  <th key={h} scope="col" className="py-2 pr-4 font-normal whitespace-nowrap">{h}</th>)}
              </tr></thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={`${f.pedido}-${f.estado}`} className="border-b border-zinc-900 text-zinc-200">
                    <td className="py-2 pr-4 font-mono text-xs">{f.pedido}</td>
                    <td className="py-2 pr-4 text-xs whitespace-nowrap">{f.estado}</td>
                    <td className="py-2 pr-4 text-xs">{f.ciudad || "—"}</td>
                    <td className="py-2 pr-4 tabular-nums">{cop(f.valor)}</td>
                    <td className="py-2 pr-4 text-xs">{f.transportadora || "—"}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{f.guia || "—"}</td>
                    <td className={`py-2 pr-4 tabular-nums ${f.dias >= 4 ? "font-semibold underline decoration-red-500" : ""}`}>{f.dias ?? "—"}</td>
                    <td className="py-2 pr-4 text-xs whitespace-nowrap">{f.accion_txt}</td>
                    <td className="py-2 pr-4 font-mono text-[11px] text-zinc-400">{f.plantilla || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}

function Panel({ d, recargar }) {
  const [sel, setSel] = useState(null);
  const [codigo, setCodigo] = useState("");
  const [busy, setBusy] = useState(false);
  if (!d.conectado) {
    return <div className={`${caja} p-5 text-sm text-zinc-300`} data-testid="log-sin-conectar">
      El motor de logística todavía no está conectado en el servidor. Soporte de Zynex lo activa; no tienes que hacer nada aquí.</div>;
  }
  if (!d.vinculado) {
    const vincular = async () => {
      setBusy(true);
      try { const r = await api.post("/zcall/motor/vincular", { codigo }); toast.success(r.data.mensaje); await recargar(); }
      catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
    };
    return (
      <div className={`${caja} p-5 space-y-3`} data-testid="log-vincular">
        <p className="text-sm text-zinc-300">Pega el código de activación que te dio Zynex para ver tus pedidos aquí. Se usa una sola vez.</p>
        <div className="flex flex-wrap gap-2">
          <Input aria-label="Código de activación" value={codigo} onChange={(e) => setCodigo(e.target.value)}
                 placeholder="Código de activación" className="bg-black/40 border-zinc-700 text-white text-sm max-w-xs" />
          <Button disabled={busy || codigo.trim().length < 8} onClick={vincular} className="btn-cta-grad rounded-sm h-9 text-sm">
            {busy ? "Activando…" : "Activar"}</Button>
        </div>
      </div>
    );
  }
  const lat = d.latidos || {};
  const vivo = ["lector", "despachador", "vigilante"].every((k) => (lat[k]?.hace_s ?? 999) < 180);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100">
          {vivo ? <CheckCircle size={12} weight="fill" className="text-green-500" /> : <WarningCircle size={12} weight="fill" className="text-red-500" />}
          {vivo ? "Motor al día" : "Motor atrasado"}
        </span>
        <span className="px-2 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100">
          {d.modo === "vivo" ? "Enviando" : "Modo sombra: decide y anota, no envía nada"}</span>
        {(d.espacios || []).map((e) => <span key={e.id} className="px-2 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100">{e.nombre} · {e.pais}</span>)}
        {d.sin_plantilla > 0 && <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100"><WarningCircle size={12} weight="fill" className="text-red-500" />
          {d.sin_plantilla === 1 ? "1 casilla obligatoria" : `${d.sin_plantilla} casillas obligatorias`} sin plantilla</span>}
      </div>

      <div>
        <div className={`${rotulo} mb-2`}>Pedidos por estado de Dropi</div>
        <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
          {(d.por_estado || []).map((t) => (
            <Tarjeta key={t.clave} titulo={t.titulo} n={t.n} sub={`Agente: ${t.agente}`} activa={sel?.clave === t.clave}
                     testId={`log-card-${t.clave}`} onClick={() => setSel(sel?.clave === t.clave ? null : t)} />
          ))}
        </div>
      </div>
      <div>
        <div className={`${rotulo} mb-2`}>Qué decidió el motor (hoy y ayer)</div>
        <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
          {(d.tareas || []).map((t) => (
            <Tarjeta key={t.clave} titulo={t.titulo} n={t.n} activa={sel?.clave === t.clave}
                     testId={`log-card-${t.clave}`} onClick={() => setSel(sel?.clave === t.clave ? null : t)} />
          ))}
          {(d.tareas || []).length === 0 && <p className="text-sm text-zinc-400 col-span-full">Aún no hay decisiones.</p>}
        </div>
      </div>
      {sel && <Lista clave={sel.clave} titulo={sel.titulo} onCerrar={() => setSel(null)} />}
    </div>
  );
}

const PERIODOS = [7, 30, 90];
const copCorto = (v) => (Number(v) >= 1e6 ? `$${(Number(v) / 1e6).toLocaleString("es-CO", { maximumFractionDigits: 1 })} M` : cop(v));
const valorKpi = (k) => (k.valor == null ? "—" : k.tipo === "cop" ? copCorto(k.valor) : k.tipo === "pct" ? `${k.valor} %` : Number(k.valor).toLocaleString("es-CO"));

function Metricas() {
  const [dias, setDias] = useState(30);
  const [d, setD] = useState(null);
  const [sel, setSel] = useState(null);
  useEffect(() => {
    setD(null); setSel(null);
    api.get("/zcall/motor/metricas", { params: { dias } }).then((r) => setD(r.data))
      .catch((e) => setD({ error: e?.response?.status === 501 ? "pendiente" : errorText(e) }));
  }, [dias]);
  if (d === null) return <p className="text-sm text-zinc-400">Cargando…</p>;
  if (d.error === "pendiente") return <div className={`${caja} p-5 text-sm text-zinc-300`} data-testid="log-metricas-pendiente">Las métricas aún no están activadas en la base de datos. Soporte de Zynex las activa; no tienes que hacer nada aquí.</div>;
  if (d.error) return <div className={`${caja} p-5 text-sm text-zinc-300`}>{d.error}</div>;
  if (!(d.kpis || []).length) return <p className="text-sm text-zinc-400">Activa tu espacio en la pestaña Panel para ver tus métricas.</p>;
  return (
    <div className="space-y-5" data-testid="log-metricas">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Periodo">
        <span className={rotulo}>Periodo</span>
        {PERIODOS.map((p) => (
          <button key={p} type="button" aria-pressed={dias === p} onClick={() => setDias(p)}
                  className={`h-9 px-3 rounded-sm border text-sm ${dias === p ? "border-fuchsia-400/70 bg-fuchsia-500/10 text-white" : "border-zinc-800 text-zinc-300 hover:bg-zinc-900"}`}>
            Últimos {p} días</button>
        ))}
      </div>
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
        {d.kpis.map((k) => (k.clave ? (
          <Tarjeta key={k.titulo} titulo={k.titulo} n={valorKpi(k)} sub={k.nota} activa={sel?.clave === k.clave}
                   testId={`log-kpi-${k.clave}`} onClick={() => setSel(sel?.clave === k.clave ? null : k)} />
        ) : (
          <div key={k.titulo} className="p-4 rounded-sm border border-zinc-800 bg-zinc-900/40 min-h-[88px] min-w-0">
            <div className="text-2xl sm:text-3xl font-semibold text-white tabular-nums break-words">{valorKpi(k)}</div>
            <div className="text-xs text-zinc-200 mt-1">{k.titulo}</div>
            <div className="text-[11px] text-zinc-400 mt-0.5">{k.nota}</div>
          </div>
        )))}
      </div>
      {sel && <Lista clave={sel.clave} titulo={sel.titulo} dias={dias} onCerrar={() => setSel(null)} />}
      {(d.transportadoras || []).length > 0 && (
        <div className={`${caja} p-5`}>
          <div className={`${rotulo} mb-3`}>Entrega por transportadora · pedidos ya cerrados</div>
          <div className="overflow-x-auto relative" tabIndex={0} role="region" aria-label="Entrega por transportadora">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[11px] text-zinc-400 border-b border-zinc-800">
                {["Transportadora", "Entregados", "Devueltos", "Tasa de entrega"].map((h) => <th key={h} scope="col" className="py-2 pr-4 font-normal whitespace-nowrap">{h}</th>)}
              </tr></thead>
              <tbody>
                {d.transportadoras.map((t) => (
                  <tr key={t.nombre} className="border-b border-zinc-900 text-zinc-200">
                    <td className="py-2 pr-4 text-xs">{t.nombre}</td>
                    <td className="py-2 pr-4 tabular-nums">{t.entregados}</td>
                    <td className="py-2 pr-4 tabular-nums">{t.devueltos}</td>
                    <td className="py-2 pr-4">
                      <div className="flex items-center gap-2"><span className="tabular-nums w-14">{t.tasa} %</span>
                        <span className="h-2 flex-1 min-w-[80px] rounded-sm bg-zinc-800"><span className="block h-2 rounded-sm bg-fuchsia-400" style={{ width: `${t.tasa}%` }} /></span></div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Casillas() {
  const [cas, setCas] = useState(null);
  const [edit, setEdit] = useState({});
  const [busy, setBusy] = useState("");
  const cargar = useCallback(() => api.get("/zcall/motor/casillas")
    .then((r) => { setCas(r.data.casillas || []); setEdit({}); })
    .catch((e) => { toast.error(errorText(e)); setCas([]); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  const grupos = useMemo(() => {
    const g = {};
    (cas || []).forEach((c) => { const k = c.estado_dropi || "OTROS"; (g[k] = g[k] || []).push(c); });
    return Object.entries(g);
  }, [cas]);
  const guardar = async (c) => {
    setBusy(c.slot);
    try {
      const r = await api.put(`/zcall/motor/casillas/${c.slot}`, { plantilla: edit[c.slot] ?? "" });
      toast.success(r.data.mensaje); await cargar();
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(""); }
  };
  if (cas === null) return <p className="text-sm text-zinc-400">Cargando…</p>;
  if (cas.length === 0) return <p className="text-sm text-zinc-400">Activa tu espacio en la pestaña Panel para configurar tus plantillas.</p>;
  return (
    <div className="space-y-5">
      <p className="text-sm text-zinc-400 max-w-3xl">
        Escribe el nombre exacto de tu plantilla aprobada en WhatsApp (como aparece en Chatea Pro). Usa plantillas de
        utilidad: cuestan mucho menos que las de marketing. Si una casilla obligatoria queda vacía, ese pedido pasa a una persona.
      </p>
      {grupos.map(([estado, items]) => (
        <div key={estado} className={`${caja} p-5`}>
          <div className={`${rotulo} mb-3`}>{estado}</div>
          <div className="space-y-3">
            {items.map((c) => {
              const val = edit[c.slot] ?? c.plantilla ?? "";
              const cambio = edit[c.slot] !== undefined && edit[c.slot] !== (c.plantilla ?? "");
              const llena = c.activo && c.plantilla;
              return (
                <div key={c.slot} className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_auto] md:items-center" data-testid={`log-casilla-${c.slot}`}>
                  <div className="min-w-0">
                    <div className="text-sm text-white flex flex-wrap items-center gap-2">
                      {c.titulo}
                      {c.beta && <span className="text-[10px] px-1.5 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100">Beta</span>}
                      {c.obligatoria && !llena && <span className="text-[10px] px-1.5 py-0.5 rounded-sm border border-red-500 bg-zinc-800 text-zinc-100">Falta</span>}
                      {llena && <CheckCircle size={14} weight="fill" className="text-green-400" aria-label="Con plantilla" />}
                    </div>
                    {c.descripcion && <div className="text-[11px] text-zinc-400">{c.descripcion}</div>}
                  </div>
                  <Input aria-label={`Plantilla para ${c.titulo}`} value={val} placeholder="nombre_de_tu_plantilla"
                         onChange={(e) => setEdit({ ...edit, [c.slot]: e.target.value })}
                         className="bg-black/40 border-zinc-700 text-white text-sm font-mono" />
                  <Button disabled={!cambio || busy === c.slot} onClick={() => guardar(c)}
                          className="btn-cta-grad rounded-sm h-9 text-sm">{busy === c.slot ? "Guardando…" : "Guardar"}</Button>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function Secuencia() {
  const [pasos, setPasos] = useState(null);
  useEffect(() => { api.get("/zcall/motor/secuencia").then((r) => setPasos(r.data.pasos || []))
    .catch((e) => { toast.error(errorText(e)); setPasos([]); }); }, []);
  const grupos = useMemo(() => {
    const g = {}; (pasos || []).forEach((p) => { (g[p.estado_dropi] = g[p.estado_dropi] || []).push(p); }); return Object.entries(g);
  }, [pasos]);
  if (pasos === null) return <p className="text-sm text-zinc-400">Cargando…</p>;
  if (pasos.length === 0) return <p className="text-sm text-zinc-400">Activa tu espacio en la pestaña Panel para ver la secuencia.</p>;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {grupos.map(([estado, ps]) => (
        <div key={estado} className={`${caja} p-5`}>
          <div className={`${rotulo} mb-3`}>{estado}</div>
          <ol className="space-y-2.5">
            {ps.map((p) => {
              const c = CANAL[p.canal] || CANAL.humano;
              return (
                <li key={p.paso} className="flex gap-3 text-sm text-zinc-200">
                  <span className="h-6 w-6 shrink-0 grid place-items-center rounded-sm border border-zinc-700 text-[11px] font-mono text-zinc-300">{p.paso}</span>
                  <span className="min-w-0">
                    <span className="inline-flex items-center gap-1.5"><c.Icon size={15} weight="duotone" /> {c.txt}</span>
                    <span className="text-zinc-400"> · {espera(p.espera_min)}</span>
                    {p.slot && <div className="text-[11px] font-mono text-zinc-400 break-all">{p.plantilla || `casilla ${p.slot} sin plantilla`}</div>}
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </div>
  );
}

export default function LogisticaPage() {
  const [tab, setTab] = useState(() => new URLSearchParams(window.location.search).get("tab") || "panel");
  const [d, setD] = useState(null);
  const cargar = useCallback(() => api.get("/zcall/motor/panel").then((r) => setD(r.data))
    .catch((e) => { toast.error(errorText(e)); setD({ conectado: false }); }), []);
  useEffect(() => { cargar(); }, [cargar]);
  const actual = TABS.find((t) => t.key === tab) || TABS[0];
  return (
    <Layout>
      <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-5" data-testid="logistica-page">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-white flex items-center gap-2"><Package size={24} weight="duotone" /> Agente de Logística</h1>
            <p className="text-sm text-zinc-400 mt-1">{actual.desc}</p>
          </div>
          <Button variant="outline" onClick={cargar} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
            <ArrowsClockwise size={14} className="mr-1.5" /> Actualizar</Button>
        </div>
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Secciones de logística">
          {TABS.map(({ key, label, Icon }) => (
            <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)} data-testid={`log-tab-${key}`}
                    className={`h-10 px-3 rounded-sm border text-sm inline-flex items-center gap-1.5 ${
                      tab === key ? "border-fuchsia-400/70 bg-fuchsia-500/10 text-white" : "border-zinc-800 text-zinc-300 hover:bg-zinc-900"}`}>
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>
        {tab === "panel" && (d === null ? <p className="text-sm text-zinc-400">Cargando…</p> : <Panel d={d} recargar={cargar} />)}
        {tab === "metricas" && <Metricas />}
        {tab === "pendientes" && <PendientesChatea />}
        {tab === "casillas" && <Casillas />}
        {tab === "secuencia" && <Secuencia />}
      </div>
    </Layout>
  );
}
