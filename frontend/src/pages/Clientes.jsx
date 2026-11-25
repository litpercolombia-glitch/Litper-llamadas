import { useCallback, useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import TraerOperacion from "../components/TraerOperacion";
import FichaPedido from "../components/FichaPedido";
import { UsersThree, MagnifyingGlass, X, WhatsappLogo, HandPalm, CheckCircle, NotePencil, ArrowsClockwise } from "@phosphor-icons/react";

/** CRM de clientes: una ficha por teléfono, con sus pedidos, notas y
 *  la bandeja de quienes necesitan a una persona. Cada número filtra la lista. */
const FILTROS = [
  { key: "atencion", label: "Necesitan una persona", nota: "Novedad, oficina, intento o marcados por el equipo" },
  { key: "activos",  label: "Con pedido en camino",  nota: "Tienen un pedido sin cerrar" },
  { key: "recompra", label: "Compraron 2 veces o más", nota: "Buenos para ofrecerles de nuevo" },
  { key: "riesgo",   label: "Han devuelto",          nota: "Confirmar bien antes de despachar" },
  { key: "todos",    label: "Todos los clientes",    nota: "Una ficha por teléfono" },
];
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";
const pill = "text-[10px] px-1.5 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100 whitespace-nowrap";
const cop = (v) => (v ? `$${Number(v).toLocaleString("es-CO")}` : "—");
const fecha = (d) => (d ? new Date(d).toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "2-digit" }) : "—");
const tel = (t) => (t ? `${t.slice(0, 3)} ${t.slice(3, 6)} ${t.slice(6)}` : "—");

function Ficha({ telefono, onCerrar, onCambio }) {
  const [pedidoAbierto, setPedidoAbierto] = useState(null);
  const [d, setD] = useState(null);
  const [nota, setNota] = useState("");
  const [busy, setBusy] = useState(false);
  const cargar = useCallback(() => api.get(`/zcall/motor/clientes/${telefono}`).then((r) => setD(r.data))
    .catch((e) => { toast.error(errorText(e)); setD({ error: true }); }), [telefono]);
  useEffect(() => { setD(null); setNota(""); cargar(); }, [cargar]);

  const guardarNota = async () => {
    setBusy(true);
    try { const r = await api.post(`/zcall/motor/clientes/${telefono}/notas`, { texto: nota }); toast.success(r.data.mensaje); setNota(""); await cargar(); onCambio(); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };
  const caso = async (estado) => {
    setBusy(true);
    try { const r = await api.put(`/zcall/motor/clientes/${telefono}/caso`, { estado, motivo: estado === "abierto" ? nota : "" }); toast.success(r.data.mensaje); await cargar(); onCambio(); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  const abierto = d?.caso?.estado === "abierto";
  return (
    <section className={`${caja} p-5 space-y-5`} data-testid="crm-ficha" aria-label="Ficha del cliente">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className={rotulo}>Ficha del cliente</div>
          <h2 className="text-lg font-semibold text-white mt-1 break-words">{d?.nombres?.[0] || "Cliente"}</h2>
          <div className="text-sm text-zinc-300 font-mono">{tel(telefono)}</div>
        </div>
        <button type="button" onClick={onCerrar} aria-label="Cerrar ficha"
                className="h-9 w-9 shrink-0 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><X size={16} /></button>
      </div>
      {d === null ? <p className="text-sm text-zinc-400">Cargando…</p> : d.error ? <p className="text-sm text-zinc-400">No se pudo abrir la ficha.</p> : (
        <>
          {(d.nombres || []).length > 1 && (
            <p className="text-xs text-zinc-300">Este teléfono aparece con {d.nombres.length} nombres ({d.nombres.join(", ")}). Aquí quedan unidos en una sola ficha.</p>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[["Pedidos", d.resumen.pedidos], ["Entregados", d.resumen.entregados], ["Devueltos", d.resumen.devueltos], ["Ha pagado", cop(d.resumen.valor_entregado)]].map(([t, v]) => (
              <div key={t} className="border border-zinc-800 rounded-sm p-3">
                <div className="text-xl font-semibold text-white tabular-nums">{v}</div><div className="text-[11px] text-zinc-400">{t}</div>
              </div>
            ))}
          </div>
          <div className="text-xs text-zinc-400">Ciudad: <span className="text-zinc-200">{(d.ciudades || []).join(", ") || "—"}</span> · Cliente desde {fecha(d.resumen.primero)}</div>

          <div className="flex flex-wrap items-center gap-2">
            {abierto
              ? <span className={pill}><HandPalm size={11} weight="fill" className="inline mr-1 text-red-500" />Lo debe atender una persona{d.caso.motivo ? `: ${d.caso.motivo}` : ""}</span>
              : <span className={pill}>Sin caso abierto</span>}
            {abierto
              ? <Button disabled={busy} onClick={() => caso("resuelto")} className="btn-cta-grad rounded-sm h-9 text-sm"><CheckCircle size={15} className="mr-1.5" /> Ya quedó resuelto</Button>
              : <Button disabled={busy} variant="outline" onClick={() => caso("abierto")} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-sm"><HandPalm size={15} className="mr-1.5" /> Que lo atienda una persona</Button>}
            <a href={`https://wa.me/57${telefono}`} target="_blank" rel="noreferrer"
               className="h-9 px-3 inline-flex items-center rounded-sm border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-sm text-zinc-100">
              <WhatsappLogo size={15} className="mr-1.5" /> Abrir WhatsApp</a>
          </div>

          <div>
            <label htmlFor="crm-nota" className={`${rotulo} block mb-2`}>Notas del equipo</label>
            <div className="flex flex-col sm:flex-row gap-2">
              <Input id="crm-nota" value={nota} maxLength={1000} onChange={(e) => setNota(e.target.value)} placeholder="Ej.: pide que la llamen después de las 5 p. m."
                     className="bg-black/40 border-zinc-700 text-white text-sm" />
              <Button disabled={busy || !nota.trim()} onClick={guardarNota} className="btn-cta-grad rounded-sm h-9 text-sm shrink-0"><NotePencil size={15} className="mr-1.5" /> Guardar nota</Button>
            </div>
            {(d.notas || []).length === 0 ? <p className="text-xs text-zinc-400 mt-2">Sin notas todavía.</p> : (
              <ul className="mt-3 space-y-2">
                {d.notas.map((n) => (
                  <li key={n.id} className="text-sm text-zinc-200 border-l-2 border-zinc-700 pl-3">
                    {n.texto}<div className="text-[11px] text-zinc-400">{n.autor || "Equipo"} · {fecha(n.creado)}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <div className={`${rotulo} mb-2`}>Sus pedidos · {(d.pedidos || []).length} · toca uno para ver todo</div>
            {pedidoAbierto && <FichaPedido pedido={pedidoAbierto} onCerrar={() => setPedidoAbierto(null)} />}
            <div className="overflow-x-auto relative" tabIndex={0} role="region" aria-label="Pedidos del cliente">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[11px] text-zinc-400 border-b border-zinc-800">
                  {["Fecha", "Pedido", "Estado", "Valor", "Transportadora", "Guía", "El agente"].map((h) => <th key={h} scope="col" className="py-2 pr-4 font-normal whitespace-nowrap">{h}</th>)}
                </tr></thead>
                <tbody>
                  {(d.pedidos || []).map((p) => (
                    <tr key={p.pedido} className="border-b border-zinc-900 text-zinc-200">
                      <td className="py-2 pr-4 text-xs whitespace-nowrap">{fecha(p.creado)}</td>
                      <td className="py-2 pr-4 font-mono text-xs"><button type="button" onClick={() => setPedidoAbierto(p.pedido)} className="underline decoration-zinc-600 hover:decoration-fuchsia-400">{p.pedido}</button></td>
                      <td className="py-2 pr-4 text-xs whitespace-nowrap">{p.estado}</td>
                      <td className="py-2 pr-4 tabular-nums">{cop(p.valor)}</td>
                      <td className="py-2 pr-4 text-xs">{p.transportadora || "—"}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{p.guia || "—"}</td>
                      <td className="py-2 pr-4 text-xs whitespace-nowrap">{p.accion_txt || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

export default function ClientesPage() {
  const [filtro, setFiltro] = useState("atencion");
  const [q, setQ] = useState("");
  const [buscado, setBuscado] = useState("");
  const [d, setD] = useState(null);
  const [sel, setSel] = useState(null);
  const cargar = useCallback(() => api.get("/zcall/motor/clientes", { params: { filtro, q: buscado } }).then((r) => setD(r.data))
    .catch((e) => setD({ error: e?.response?.status === 501 ? "pendiente" : errorText(e) })), [filtro, buscado]);
  useEffect(() => { cargar(); }, [cargar]);
  const buscar = (e) => { e.preventDefault(); setBuscado(q.trim()); };
  const filas = d?.filas || [];
  const res = d?.resumen || {};

  return (
    <Layout>
      <div className="p-4 md:p-8 max-w-6xl mx-auto space-y-5" data-testid="clientes-page">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-white flex items-center gap-2"><UsersThree size={24} weight="duotone" /> Clientes</h1>
            <p className="text-sm text-zinc-400 mt-1">Una ficha por teléfono con todos sus pedidos. Toca un número para filtrar y un cliente para abrir su ficha.</p>
          </div>
          <Button variant="outline" onClick={cargar} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
            <ArrowsClockwise size={14} className="mr-1.5" /> Actualizar</Button>
        </div>

        {d === null ? <p className="text-sm text-zinc-400">Cargando…</p>
          : d.error === "pendiente" ? <div className={`${caja} p-5 text-sm text-zinc-300`} data-testid="crm-pendiente">Esta pantalla aún no está activada en la base de datos. Soporte de Zynex la activa; no tienes que hacer nada aquí.</div>
          : d.error ? <div className={`${caja} p-5 text-sm text-zinc-300`}>{d.error}</div>
          : !d.vinculado && filas.length === 0 && !res.todos ? <div className={`${caja} p-5 text-sm text-zinc-300`}>Tu espacio se está preparando. Abre Logística y vuelve aquí.</div>
          : (
            <>
              <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
                {FILTROS.map((f) => (
                  <button key={f.key} type="button" onClick={() => { setFiltro(f.key); setSel(null); }} aria-pressed={filtro === f.key} data-testid={`crm-filtro-${f.key}`}
                          className={`text-left p-4 rounded-sm border transition-colors min-h-[96px] ${filtro === f.key ? "border-emerald-400/70 bg-emerald-500/10" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"}`}>
                    <div className="text-3xl font-semibold text-white tabular-nums">{(res[f.key] ?? 0).toLocaleString("es-CO")}</div>
                    <div className="text-xs text-zinc-200 mt-1">{f.label}</div>
                    <div className="text-[11px] text-zinc-400 mt-0.5">{f.nota}</div>
                  </button>
                ))}
              </div>

              <form onSubmit={buscar} className="flex flex-wrap gap-2" role="search">
                <Input aria-label="Buscar cliente por nombre, teléfono o ciudad" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre, teléfono o ciudad"
                       className="bg-black/40 border-zinc-700 text-white text-sm max-w-sm" />
                <Button type="submit" className="btn-cta-grad rounded-sm h-9 text-sm"><MagnifyingGlass size={15} className="mr-1.5" /> Buscar</Button>
                {buscado && <Button type="button" variant="outline" onClick={() => { setQ(""); setBuscado(""); }} className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-sm">Quitar búsqueda</Button>}
              </form>

              {sel && <Ficha telefono={sel} onCerrar={() => setSel(null)} onCambio={cargar} />}

              <div className={`${caja} p-5`} data-testid="crm-lista">
                <div className={`${rotulo} mb-3`}>{FILTROS.find((f) => f.key === filtro)?.label}{buscado ? ` · “${buscado}”` : ""} · {filas.length}{filas.length >= 100 ? " primeros" : ""}</div>
                {filas.length === 0 ? <p className="text-sm text-zinc-400">No hay clientes aquí en este momento.</p> : (
                  <div className="overflow-x-auto relative" tabIndex={0} role="region" aria-label="Lista de clientes">
                    <table className="w-full text-sm">
                      <thead><tr className="text-left text-[11px] text-zinc-400 border-b border-zinc-800">
                        {["Cliente", "Teléfono", "Ciudad", "Pedidos", "Entregados", "Devueltos", "Último pedido", "Último estado", ""].map((h, i) =>
                          <th key={h || i} scope="col" className="py-2 pr-4 font-normal whitespace-nowrap">{h || <span className="sr-only">Señales</span>}</th>)}
                      </tr></thead>
                      <tbody>
                        {filas.map((c) => (
                          <tr key={c.tel} className={`border-b border-zinc-900 text-zinc-200 ${sel === c.tel ? "bg-emerald-500/10" : ""}`}>
                            <td className="py-2 pr-4">
                              <button type="button" onClick={() => { setSel(c.tel); window.scrollTo({ top: 0, behavior: "smooth" }); }} data-testid={`crm-abrir-${c.tel}`}
                                      className="text-left underline decoration-zinc-600 underline-offset-2 hover:decoration-emerald-400 min-h-[32px]">{c.nombre || "Sin nombre"}</button>
                            </td>
                            <td className="py-2 pr-4 font-mono text-xs whitespace-nowrap">{tel(c.tel)}</td>
                            <td className="py-2 pr-4 text-xs">{c.ciudad || "—"}</td>
                            <td className="py-2 pr-4 tabular-nums">{c.pedidos}</td>
                            <td className="py-2 pr-4 tabular-nums">{c.entregados}</td>
                            <td className="py-2 pr-4 tabular-nums">{c.devueltos}</td>
                            <td className="py-2 pr-4 text-xs whitespace-nowrap">{fecha(c.ultimo)}</td>
                            <td className="py-2 pr-4 text-xs whitespace-nowrap">{c.ultimo_estado}</td>
                            <td className="py-2 pr-4"><span className="flex flex-wrap gap-1">
                              {c.caso_abierto && <span className={pill}>Persona</span>}
                              {c.por_resolver > 0 && <span className={pill}>{c.por_resolver} por resolver</span>}
                              {c.notas > 0 && <span className={pill}>{c.notas} {c.notas === 1 ? "nota" : "notas"}</span>}
                            </span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <TraerOperacion onListo={cargar} />
            </>
          )}
      </div>
    </Layout>
  );
}
