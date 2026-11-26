import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Lifebuoy, Lightbulb, PaperPlaneRight, ShieldCheck, WhatsappLogo } from "@phosphor-icons/react";

const S = "/zcall/motor/operacion/soporte";
const hora = (iso) => {
  try { return new Date(iso).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }); }
  catch { return ""; }
};

/**
 * Botón flotante de Ayuda, presente en toda la app.
 *  - «Escríbenos»: el cliente pregunta, queda guardado y el equipo responde aquí mismo.
 *  - Permiso temporal para que soporte entre a la cuenta (lo da y lo quita el cliente).
 *  - «Sugerir función»: el formulario de ideas de siempre (POST /api/feedback).
 *  - Si quien abre es del equipo de soporte, ve además la bandeja de todas las cuentas.
 */
export default function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("chat");
  const [datos, setDatos] = useState(null);       // {mensajes, sin_leer, permiso, es_equipo, sesion_soporte}
  const [sinLeer, setSinLeer] = useState(0);
  const [texto, setTexto] = useState("");
  const [busy, setBusy] = useState(false);
  const finRef = useRef(null);

  const cargar = useCallback(async (marcar) => {
    try {
      const r = await api.get(`${S}/mensajes`, { params: { marcar: !!marcar } });
      setDatos(r.data);
      setSinLeer(marcar ? 0 : (r.data?.sin_leer || 0));
    } catch { /* sin sesión o servidor sin soporte: el botón sigue sirviendo para sugerir */ }
  }, []);

  // Cerrado: consulta al entrar y cada 2 minutos SIN marcar como leído (para el punto rojo). Abierto: marca y refresca.
  useEffect(() => {
    if (open) return undefined;
    cargar(false);
    const t = setInterval(() => cargar(false), 120000);
    return () => clearInterval(t);
  }, [open, cargar]);
  useEffect(() => {
    if (!open) return undefined;
    cargar(true);
    const t = setInterval(() => cargar(true), 20000);
    return () => clearInterval(t);
  }, [open, cargar]);
  useEffect(() => { if (open && tab === "chat") finRef.current?.scrollIntoView({ block: "end" }); }, [datos, open, tab]);

  const enviar = async (e) => {
    e?.preventDefault?.();
    const t = texto.trim();
    if (!t) return;
    setBusy(true);
    try {
      await api.post(`${S}/mensajes`, { texto: t });
      setTexto("");
      await cargar(true);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "No se pudo enviar. Intenta de nuevo.");
    } finally { setBusy(false); }
  };

  const permiso = async (horas) => {
    setBusy(true);
    try {
      if (horas) await api.post(`${S}/acceso`, { horas });
      else await api.post(`${S}/acceso/quitar`);
      await cargar(true);
      toast.success(horas ? "Listo. Soporte puede entrar a tu cuenta por ese tiempo." : "Permiso quitado.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "No se pudo cambiar el permiso.");
    } finally { setBusy(false); }
  };

  const activo = !!datos?.permiso?.activo;
  const pestañas = [["chat", "Escríbenos"], ["idea", "Sugerir función"]];
  if (datos?.es_equipo) pestañas.push(["equipo", "Bandeja del equipo"]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="feedback-fab"
        data-testid="feedback-fab"
        aria-label={sinLeer ? `Ayuda, ${sinLeer} respuesta nueva` : "Ayuda"}
        type="button">
        <Lifebuoy size={16} weight="fill" /> Ayuda
        {sinLeer > 0 && <span className="ayuda-punto" aria-hidden="true">{sinLeer}</span>}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="feedback-dialog" className="bg-zinc-950 border-zinc-800 text-white max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lifebuoy size={18} weight="fill" className="text-cyan-300" /> ¿En qué te ayudamos?
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              Escríbenos aquí y una persona del equipo te responde en este mismo lugar.
            </DialogDescription>
          </DialogHeader>

          {datos?.sesion_soporte && (
            <div className="text-xs rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-200 px-3 py-2" role="status">
              Estás dentro de esta cuenta como soporte. La sesión se cierra sola en 30 minutos.
            </div>
          )}

          <div className="flex gap-1 border-b border-zinc-800" role="tablist" aria-label="Ayuda">
            {pestañas.map(([k, n]) => (
              <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                data-testid={`ayuda-tab-${k}`}
                className={`px-3 py-2 text-sm border-b-2 -mb-px ${tab === k ? "border-cyan-400 text-white" : "border-transparent text-zinc-400 hover:text-zinc-200"}`}>
                {n}
              </button>
            ))}
          </div>

          {tab === "chat" && (
            <div className="space-y-3">
              <div className="h-56 overflow-y-auto rounded-md border border-zinc-800 bg-zinc-900 p-3 space-y-2" data-testid="ayuda-hilo" aria-live="polite">
                {!(datos?.mensajes?.length) && (
                  <p className="text-sm text-zinc-400">
                    Cuéntanos qué necesitas: algo que no carga, una conexión, una duda de tu plan. Respondemos en horario laboral.
                  </p>
                )}
                {(datos?.mensajes || []).map((m) => (
                  <div key={m.id} className={`flex ${m.de === "cliente" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${m.de === "cliente" ? "bg-zinc-800 text-zinc-100" : "border border-cyan-500/40 bg-zinc-950 text-zinc-100"}`}>
                      <div className="text-[11px] text-zinc-300 mb-0.5">{m.de === "cliente" ? "Tú" : "Equipo Zynex"} · {hora(m.creado)}</div>
                      <div className="whitespace-pre-wrap break-words">{m.texto}</div>
                    </div>
                  </div>
                ))}
                <div ref={finRef} />
              </div>

              {!datos?.sesion_soporte && (
                <form onSubmit={enviar} className="flex gap-2">
                  <label htmlFor="ayuda-texto" className="sr-only">Tu mensaje</label>
                  <Input id="ayuda-texto" value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={2000}
                    placeholder="Escribe tu pregunta" data-testid="ayuda-texto"
                    className="bg-black/40 border-zinc-700 text-white" />
                  <Button type="submit" disabled={busy || !texto.trim()} className="btn-cta-grad rounded-sm" data-testid="ayuda-enviar">
                    <PaperPlaneRight size={16} weight="fill" /> Enviar
                  </Button>
                </form>
              )}

              {!datos?.sesion_soporte && (
                <div className="rounded-md border border-zinc-800 p-3" data-testid="ayuda-permiso">
                  <div className="flex items-start gap-2">
                    <ShieldCheck size={18} className="text-emerald-300 mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-white">
                        {activo ? "Soporte puede entrar a tu cuenta" : "¿Quieres que lo arreglemos por ti?"}
                      </div>
                      <p className="text-xs text-zinc-400 mt-0.5">
                        {activo
                          ? `Permiso vigente hasta ${hora(datos.permiso.hasta)}. Lo puedes quitar cuando quieras.`
                          : "Danos permiso para entrar a tu cuenta por un tiempo. Vence solo, y queda registro de cada entrada."}
                      </p>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {activo ? (
                          <Button type="button" variant="outline" disabled={busy} onClick={() => permiso(0)}
                            className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800" data-testid="ayuda-permiso-quitar">Quitar permiso</Button>
                        ) : (
                          [[1, "1 hora"], [24, "24 horas"], [72, "3 días"]].map(([h, n]) => (
                            <Button key={h} type="button" variant="outline" disabled={busy} onClick={() => permiso(h)}
                              className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800" data-testid={`ayuda-permiso-${h}`}>{n}</Button>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div className="text-xs text-zinc-400 flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="feedback-support">
                <span>¿Es urgente?</span>
                <a href="https://wa.me/573144644054" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-emerald-300 hover:text-emerald-200 underline">
                  <WhatsappLogo size={14} weight="fill" /> WhatsApp 314 464 4054
                </a>
                <a href="mailto:zynexproai@gmail.com" className="text-cyan-300 hover:text-cyan-200 underline">zynexproai@gmail.com</a>
              </div>
            </div>
          )}

          {tab === "idea" && <Sugerir onListo={() => setOpen(false)} />}
          {tab === "equipo" && <Bandeja />}
        </DialogContent>
      </Dialog>
    </>
  );
}

function Sugerir({ onListo }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e?.preventDefault?.();
    if (!title.trim() || !description.trim()) { toast.error("Ponle un título y descríbenos tu idea."); return; }
    setBusy(true);
    try {
      const r = await api.post("/feedback", { title: title.trim(), description: description.trim(), source: "app-fab" });
      toast.success(r.data?.message || "¡Gracias! Recibimos tu idea.");
      setTitle(""); setDescription(""); onListo?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "No se pudo enviar. Reintenta.");
    } finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-sm text-zinc-400 flex items-center gap-2">
        <Lightbulb size={16} weight="fill" className="text-yellow-300" /> Cuéntanos qué te falta. Leemos todas.
      </p>
      <div>
        <label htmlFor="idea-titulo" className="text-xs text-zinc-400 block mb-1">Título</label>
        <Input id="idea-titulo" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={140} required
          placeholder="Ej: Reintentar rescate en fin de semana" data-testid="feedback-title"
          className="bg-black/40 border-zinc-700 text-white" />
      </div>
      <div>
        <label htmlFor="idea-desc" className="text-xs text-zinc-400 block mb-1">Descripción</label>
        <Textarea id="idea-desc" rows={5} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={4000} required
          placeholder="El problema y cómo lo verías resuelto" data-testid="feedback-description"
          className="bg-black/40 border-zinc-700 text-white" />
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={busy} data-testid="feedback-submit" className="btn-cta-grad rounded-sm">
          {busy ? "Enviando…" : "Enviar sugerencia"}
        </Button>
      </div>
    </form>
  );
}

/** Solo la ve el equipo de soporte (el servidor responde 404 a cualquier otro). */
function Bandeja() {
  const [cuentas, setCuentas] = useState([]);
  const [sel, setSel] = useState(null);
  const [hilo, setHilo] = useState(null);
  const [texto, setTexto] = useState("");
  const [busy, setBusy] = useState(false);

  const lista = useCallback(() => api.get(`${S}/equipo/bandeja`).then((r) => setCuentas(r.data?.cuentas || [])).catch(() => {}), []);
  const abrir = useCallback((org) => { setSel(org); api.get(`${S}/equipo/mensajes/${encodeURIComponent(org)}`).then((r) => setHilo(r.data)).catch(() => {}); }, []);
  useEffect(() => { lista(); }, [lista]);

  const responder = async (e) => {
    e?.preventDefault?.();
    if (!texto.trim() || !sel) return;
    setBusy(true);
    try { await api.post(`${S}/equipo/responder`, { org_id: sel, texto: texto.trim() }); setTexto(""); abrir(sel); lista(); }
    catch (err) { toast.error(err?.response?.data?.detail || "No se pudo responder."); }
    finally { setBusy(false); }
  };
  const entrar = async () => {
    setBusy(true);
    try { await api.post(`${S}/equipo/entrar`, { org_id: sel }); window.location.assign("/app/logistica"); }
    catch (err) { toast.error(err?.response?.data?.detail || "No se pudo entrar."); setBusy(false); }
  };

  if (!sel) {
    return (
      <div className="space-y-2 max-h-80 overflow-y-auto" data-testid="ayuda-bandeja">
        {!cuentas.length && <p className="text-sm text-zinc-400">No hay mensajes.</p>}
        {cuentas.map((c) => (
          <button key={c.org_id} type="button" onClick={() => abrir(c.org_id)}
            className="w-full text-left rounded-md border border-zinc-800 hover:border-zinc-600 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-white truncate">{c.org_id}</span>
              {c.pendientes > 0 && <span className="text-xs rounded-full border border-amber-500/50 text-amber-300 px-2">{c.pendientes} sin responder</span>}
            </div>
            <div className="text-xs text-zinc-400 truncate">{c.ultimo_de === "cliente" ? "Cliente" : "Equipo"}: {c.ultimo}</div>
          </button>
        ))}
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <button type="button" onClick={() => { setSel(null); setHilo(null); }} className="text-sm text-cyan-300 underline">← Todas las cuentas</button>
        <Button type="button" variant="outline" disabled={busy || !hilo?.permiso?.activo} onClick={entrar}
          className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800" data-testid="ayuda-entrar">
          {hilo?.permiso?.activo ? "Entrar a esta cuenta" : "Sin permiso del cliente"}
        </Button>
      </div>
      <div className="h-48 overflow-y-auto rounded-md border border-zinc-800 bg-zinc-900 p-3 space-y-2">
        {(hilo?.mensajes || []).map((m) => (
          <div key={m.id} className="text-sm">
            <span className="text-[11px] text-zinc-400">{m.de === "cliente" ? "Cliente" : "Equipo"} · {hora(m.creado)}</span>
            <div className="whitespace-pre-wrap break-words text-zinc-100">{m.texto}</div>
          </div>
        ))}
      </div>
      <form onSubmit={responder} className="flex gap-2">
        <label htmlFor="equipo-texto" className="sr-only">Respuesta</label>
        <Input id="equipo-texto" value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={2000}
          placeholder="Respuesta para el cliente" className="bg-black/40 border-zinc-700 text-white" />
        <Button type="submit" disabled={busy || !texto.trim()} className="btn-cta-grad rounded-sm">Responder</Button>
      </form>
    </div>
  );
}
