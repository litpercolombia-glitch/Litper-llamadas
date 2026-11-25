import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Copy, HandPalm, CheckCircle, WhatsappLogo, X, NotePencil, ClockCounterClockwise } from "@phosphor-icons/react";

/** Ficha del pedido: se abre al tocar cualquier fila. Muestra todo el pedido, lo que hizo
 *  Zynex con él y la ficha del cliente, con las acciones a la mano (copiar, WhatsApp,
 *  nota, pasar a una persona). Desde aquí se salta a cualquier otro pedido del cliente. */
const caja = "border border-zinc-800 rounded-sm bg-zinc-900/40";
const rotulo = "text-[10px] font-mono uppercase tracking-widest text-zinc-400";
const pill = "text-[11px] px-2 py-0.5 rounded-sm border border-zinc-600 bg-zinc-800 text-zinc-100";
const cop = (v) => (v ? `$${Number(v).toLocaleString("es-CO")}` : "—");
const fecha = (v) => (v ? new Date(v).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" }) : "—");
const telBonito = (t) => (t && t.length === 10 ? `${t.slice(0, 3)} ${t.slice(3, 6)} ${t.slice(6)}` : t || "—");

async function copiar(texto, que) {
  try { await navigator.clipboard.writeText(String(texto)); toast.success(`${que} copiado.`); }
  catch { toast.error(`No se pudo copiar. ${que}: ${texto}`); }
}

function Dato({ k, v, children }) {
  return (
    <div className="min-w-0">
      <div className={rotulo}>{k}</div>
      <div className="text-sm text-zinc-100 break-words flex items-center gap-1.5 flex-wrap">{v}{children}</div>
    </div>
  );
}

function BotonIcono({ onClick, label, children }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} title={label}
            className="h-8 w-8 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800">{children}</button>
  );
}

export default function FichaPedido({ pedido, onCerrar }) {
  const [actual, setActual] = useState(pedido);
  const [d, setD] = useState(null);
  const [nota, setNota] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { setActual(pedido); }, [pedido]);
  const cargar = useCallback(() => {
    setD(null);
    return api.get(`/zcall/motor/pedidos/${actual}`).then((r) => setD(r.data))
      .catch((e) => setD({ error: e?.response?.status === 501 ? "La ficha del pedido aún no está activada. Soporte de Zynex la activa." : errorText(e) }));
  }, [actual]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    const esc = (e) => { if (e.key === "Escape") onCerrar(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onCerrar]);

  const p = d?.pedido;
  const cli = d?.cliente;
  const tel = p?.tel10;
  const abierto = cli?.caso?.estado === "abierto";

  const guardarNota = async () => {
    if (!nota.trim() || !tel) return;
    setBusy(true);
    try { const r = await api.post(`/zcall/motor/clientes/${tel}/notas`, { texto: `Pedido ${p.pedido}: ${nota.trim()}` }); toast.success(r.data.mensaje); setNota(""); await cargar(); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };
  const caso = async (estado) => {
    if (!tel) return;
    setBusy(true);
    try {
      const motivo = estado === "abierto" ? (nota.trim() || `Pedido ${p.pedido} en ${p.estado}`) : "";
      const r = await api.put(`/zcall/motor/clientes/${tel}/caso`, { estado, motivo: motivo.slice(0, 300) });
      toast.success(r.data.mensaje); setNota(""); await cargar();
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] flex justify-end" role="dialog" aria-modal="true" aria-labelledby="ficha-pedido-t" data-testid="ficha-pedido">
      <button type="button" aria-label="Cerrar ficha" onClick={onCerrar} className="absolute inset-0 bg-black/60" />
      <div className="relative h-full w-full max-w-xl overflow-y-auto bg-zinc-950 border-l border-zinc-800 p-5 space-y-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className={rotulo}>Pedido</div>
            <h2 id="ficha-pedido-t" className="text-xl font-semibold text-white font-mono break-all">{actual}</h2>
            {p && <div className="flex flex-wrap gap-2 mt-2">
              <span className={pill}>{p.estado}</span>
              {p.dias != null && <span className={`${pill} ${p.dias >= 4 ? "border-red-500" : ""}`}>{p.dias} días en este estado</span>}
            </div>}
          </div>
          <BotonIcono onClick={onCerrar} label="Cerrar ficha"><X size={16} /></BotonIcono>
        </div>

        {d === null && <p className="text-sm text-zinc-400">Cargando…</p>}
        {d?.error && <div className={`${caja} p-4 text-sm text-zinc-300`}>{d.error}</div>}

        {p && (
          <>
            <section className={`${caja} p-4 grid gap-4 grid-cols-2`} aria-label="Datos del pedido">
              <Dato k="Cliente" v={p.nombre || "—"} />
              <Dato k="Teléfono" v={telBonito(tel)}>
                {tel && <>
                  <BotonIcono onClick={() => copiar(tel, "Teléfono")} label="Copiar teléfono"><Copy size={14} /></BotonIcono>
                  <a href={`https://wa.me/57${tel}`} target="_blank" rel="noreferrer" aria-label="Abrir WhatsApp" title="Abrir WhatsApp"
                     className="h-8 w-8 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><WhatsappLogo size={15} /></a>
                </>}
              </Dato>
              <Dato k="Ciudad" v={p.ciudad || "—"} />
              <Dato k="Valor" v={cop(p.valor)} />
              <Dato k="Transportadora" v={p.transportadora || "—"} />
              <Dato k="Guía" v={<span className="font-mono">{p.guia || "—"}</span>}>
                {p.guia && <BotonIcono onClick={() => copiar(p.guia, "Guía")} label="Copiar guía"><Copy size={14} /></BotonIcono>}
              </Dato>
              <Dato k="Creado" v={fecha(p.creado)} />
              <Dato k="En este estado desde" v={fecha(p.desde)} />
            </section>

            <section className={`${caja} p-4`} aria-labelledby="ficha-hist-t">
              <div id="ficha-hist-t" className={`${rotulo} mb-3 flex items-center gap-1.5`}><ClockCounterClockwise size={13} /> Qué ha hecho Zynex con este pedido</div>
              {(d.historial || []).length === 0
                ? <p className="text-sm text-zinc-400">Todavía nada. Cuando el motor decida algo, aparece aquí con la fecha y la plantilla.</p>
                : <ol className="space-y-2.5">
                    {d.historial.map((h) => (
                      <li key={h.id} className="text-sm text-zinc-200 border-l-2 border-zinc-700 pl-3">
                        <div className="flex flex-wrap gap-x-2"><span className="font-medium">{h.accion_txt}</span><span className="text-zinc-400">· {h.estado} · {fecha(h.dia)}</span></div>
                        {(h.plantilla || h.motivo) && <div className="text-[11px] text-zinc-400 font-mono break-all">{[h.plantilla, h.motivo].filter(Boolean).join(" · ")}</div>}
                      </li>
                    ))}
                  </ol>}
            </section>

            {cli ? (
              <section className={`${caja} p-4 space-y-4`} aria-labelledby="ficha-cli-t">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div id="ficha-cli-t" className={rotulo}>Este cliente</div>
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    <span className={pill}>{cli.resumen?.pedidos ?? 0} pedidos</span>
                    <span className={pill}>{cli.resumen?.entregados ?? 0} entregados</span>
                    <span className={pill}>{cli.resumen?.devueltos ?? 0} devueltos</span>
                  </div>
                </div>
                {(cli.pedidos || []).length > 1 && (
                  <div>
                    <div className={`${rotulo} mb-2`}>Sus pedidos · toca uno para verlo</div>
                    <ul className="space-y-1.5">
                      {cli.pedidos.map((o) => (
                        <li key={o.pedido}>
                          <button type="button" onClick={() => setActual(o.pedido)} aria-current={String(o.pedido) === String(actual)}
                                  className={`w-full text-left grid grid-cols-[minmax(0,1fr)_auto] gap-2 px-3 py-2 rounded-sm border text-sm ${
                                    String(o.pedido) === String(actual) ? "border-fuchsia-400/70 bg-fuchsia-500/10" : "border-zinc-800 hover:bg-zinc-900"}`}>
                            <span className="min-w-0 truncate"><span className="font-mono text-xs">{o.pedido}</span> · {o.estado}</span>
                            <span className="tabular-nums text-zinc-300">{cop(o.valor)}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {(cli.notas || []).length > 0 && (
                  <div>
                    <div className={`${rotulo} mb-2`}>Notas del equipo</div>
                    <ul className="space-y-2">
                      {cli.notas.slice(0, 5).map((n) => (
                        <li key={n.id} className="text-sm text-zinc-200">{n.texto}<div className="text-[11px] text-zinc-400">{n.autor || "Equipo"} · {fecha(n.creado)}</div></li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="space-y-2">
                  <label htmlFor="ficha-nota" className={`${rotulo} flex items-center gap-1.5`}><NotePencil size={13} /> Nota para el equipo</label>
                  <textarea id="ficha-nota" value={nota} maxLength={900} rows={2} onChange={(e) => setNota(e.target.value)}
                            placeholder="Ej.: pidió que lo llamen después de las 5"
                            className="w-full rounded-sm bg-black/40 border border-zinc-700 text-white text-sm p-2" />
                  <div className="flex flex-wrap gap-2">
                    <Button disabled={busy || !nota.trim()} onClick={guardarNota} className="btn-cta-grad rounded-sm h-9 text-sm">Guardar nota</Button>
                    {abierto
                      ? <Button disabled={busy} onClick={() => caso("resuelto")} variant="outline" className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-sm"><CheckCircle size={15} className="mr-1.5" /> Ya quedó resuelto</Button>
                      : <Button disabled={busy} onClick={() => caso("abierto")} variant="outline" className="h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-sm"><HandPalm size={15} className="mr-1.5" /> Que lo atienda una persona</Button>}
                  </div>
                  {abierto && <p className="text-[11px] text-zinc-300">Caso abierto{cli.caso.motivo ? `: ${cli.caso.motivo}` : ""}.</p>}
                </div>
              </section>
            ) : (
              <p className="text-sm text-zinc-400">Este pedido aún no tiene teléfono. Cuando tu Claude sincronice con Dropi, aparece la ficha del cliente.</p>
            )}
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
