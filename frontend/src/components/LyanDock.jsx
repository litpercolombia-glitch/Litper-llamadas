import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import { errorText, useAssistantName } from "../lib/assistant";
import { PaperPlaneRight, X, ArrowSquareOut, Sparkle } from "@phosphor-icons/react";

/** Asistente a la mano en toda la app: un botón fijo abre un panel lateral para
 *  pedirle cosas sin salir de la pantalla. Sugiere preguntas según dónde estés.
 *  Lo que cambia datos se confirma en la conversación completa. */
const IDEAS = {
  "/app/logistica": ["¿Cómo va mi operación hoy?", "Muéstrame los pedidos en NOVEDAD", "¿Qué pedidos llevan más días sin moverse?"],
  "/app/clientes": ["¿Qué clientes necesitan a una persona?", "¿Quiénes han comprado 2 veces o más?", "Busca al cliente con teléfono…"],
  "/app/llamadas": ["¿Cómo van mis agentes de voz?", "¿Qué llamadas están en cola y por qué?"],
  "/app/conexiones": ["¿Qué me falta conectar para empezar?"],
  "/app/metricas": ["Resume mis métricas de los últimos 30 días y dime qué mejorar primero."],
};
const GENERAL = ["¿Cómo va mi operación hoy?", "¿Qué debo atender primero?", "Revisa mi configuración y dime qué me falta."];

export default function LyanDock() {
  const { pathname } = useLocation();
  const nombre = useAssistantName();
  const [abierto, setAbierto] = useState(false);
  const [tid, setTid] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [texto, setTexto] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [porConfirmar, setPorConfirmar] = useState(false);
  const fin = useRef(null);
  const campo = useRef(null);

  useEffect(() => { if (abierto) { campo.current?.focus(); fin.current?.scrollIntoView({ block: "end" }); } }, [abierto, msgs]);
  useEffect(() => {
    if (!abierto) return undefined;
    const esc = (e) => { if (e.key === "Escape") setAbierto(false); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [abierto]);
  if (pathname === "/app") return null; // en la conversación completa no hace falta

  const enviar = async (t) => {
    const msg = (t ?? texto).trim();
    if (!msg || busy) return;
    setTexto(""); setError(""); setBusy(true);
    setMsgs((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: msg }]);
    try {
      const r = await api.post("/copilot/run", { thread_id: tid || undefined, text: msg }, { timeout: 120000 });
      const nuevo = r.data?.thread_id || tid;
      setTid(nuevo);
      setPorConfirmar(!!r.data?.pending_action?.id);
      if (nuevo) {
        const h = await api.get(`/threads/${nuevo}/messages`);
        const lista = (h.data?.messages || h.data || []).filter((x) => (x.role === "user" || x.role === "assistant") && x.content);
        if (lista.length) setMsgs(lista);
      }
    } catch (e) { setError(errorText(e, "No pude responder. Inténtalo de nuevo.")); }
    finally { setBusy(false); }
  };
  const ideas = IDEAS[pathname] || GENERAL;

  return (
    <>
      {!abierto && (
        <button type="button" onClick={() => setAbierto(true)} data-testid="lyan-dock-abrir" aria-label={`Abrir a ${nombre}`}
                className="fixed z-40 right-4 bottom-20 h-12 pl-1.5 pr-4 rounded-full border border-zinc-600 bg-zinc-900 text-white shadow-lg inline-flex items-center gap-2 hover:bg-zinc-800">
          <img src="/lyan.webp" alt="" className="w-9 h-9 rounded-full object-cover" />
          <span className="text-sm font-medium">Pregúntale a {nombre}</span>
        </button>
      )}
      {abierto && (
        <aside role="dialog" aria-label={`Asistente ${nombre}`} data-testid="lyan-dock"
               className="fixed z-[90] inset-y-0 right-0 w-full sm:w-[400px] bg-zinc-950 border-l border-zinc-800 flex flex-col shadow-2xl">
          <header className="flex items-center justify-between gap-2 px-4 py-3 border-b border-zinc-800">
            <div className="flex items-center gap-2 min-w-0">
              <img src="/lyan.webp" alt="" className="w-8 h-8 rounded-full object-cover" />
              <div className="min-w-0">
                <div className="text-sm font-semibold text-white truncate">{nombre}</div>
                <div className="text-[11px] text-zinc-400">Ve tus datos y te ayuda desde cualquier pantalla</div>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <Link to={tid ? `/app?thread=${tid}` : "/app"} aria-label="Abrir la conversación completa" title="Conversación completa"
                    className="h-9 w-9 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><ArrowSquareOut size={15} /></Link>
              <button type="button" onClick={() => setAbierto(false)} aria-label="Cerrar asistente"
                      className="h-9 w-9 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><X size={16} /></button>
            </div>
          </header>
          <div className="flex-1 overflow-y-auto p-4 space-y-3" aria-live="polite">
            {msgs.length === 0 && (
              <div className="space-y-2">
                <p className="text-sm text-zinc-300 flex items-center gap-1.5"><Sparkle size={15} /> Prueba con una de estas:</p>
                {ideas.map((i) => (
                  <button key={i} type="button" onClick={() => (i.endsWith("…") ? (setTexto(i.replace("…", " ")), campo.current?.focus()) : enviar(i))}
                          className="block w-full text-left text-sm text-zinc-100 border border-zinc-800 rounded-sm px-3 py-2 hover:bg-zinc-900">{i}</button>
                ))}
              </div>
            )}
            {msgs.map((m) => (
              <div key={m.id || `${m.role}-${m.content.slice(0, 24)}`} className={m.role === "user" ? "flex justify-end" : ""}>
                <div className={`max-w-[90%] text-sm rounded-sm px-3 py-2 whitespace-pre-wrap break-words ${
                  m.role === "user" ? "bg-zinc-800 text-white" : "border border-zinc-800 bg-zinc-900/60 text-zinc-100"}`}>{m.content}</div>
              </div>
            ))}
            {busy && <p className="text-sm text-zinc-400">{nombre} está revisando…</p>}
            {porConfirmar && (
              <p className="text-sm text-zinc-100 border border-amber-500/50 rounded-sm px-3 py-2">
                Hay una acción esperando tu confirmación.{" "}
                <Link to={tid ? `/app?thread=${tid}` : "/app"} className="underline">Ábrela para aplicarla o descartarla</Link>.
              </p>
            )}
            {error && <p className="text-sm text-zinc-100 border border-red-500/50 rounded-sm px-3 py-2" role="alert">{error}</p>}
            <div ref={fin} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); enviar(); }} className="p-3 border-t border-zinc-800 flex gap-2">
            <label htmlFor="lyan-dock-texto" className="sr-only">Mensaje para {nombre}</label>
            <input id="lyan-dock-texto" ref={campo} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={2000}
                   placeholder={`Pídele algo a ${nombre}`} autoComplete="off"
                   className="flex-1 min-w-0 h-10 rounded-sm bg-black/40 border border-zinc-700 text-white text-sm px-3" />
            <button type="submit" disabled={busy || !texto.trim()} aria-label="Enviar"
                    className="h-10 w-10 shrink-0 grid place-items-center rounded-sm btn-cta-grad text-white disabled:opacity-50"><PaperPlaneRight size={16} weight="fill" /></button>
          </form>
        </aside>
      )}
    </>
  );
}
