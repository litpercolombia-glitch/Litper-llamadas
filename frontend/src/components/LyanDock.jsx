import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../lib/api";
import { errorText, useAssistantName } from "../lib/assistant";
import { PaperPlaneRight, X, ArrowSquareOut, Sparkle, Paperclip, File as FileIcon, Microphone, Stop, ClockCounterClockwise, Plus } from "@phosphor-icons/react";

/** Asistente a la mano en toda la app: un botón fijo abre un panel lateral para
 *  pedirle cosas sin salir de la pantalla. Sugiere preguntas según dónde estés.
 *  Adjunta archivos, imágenes y audios; guarda las conversaciones; deja elegir
 *  habilidad y modelo; y lo que cambia datos espera «Aplicar» o «Cancelar». */
const MODELOS = [["auto", "Automático"], ["openrouter", "OpenRouter"], ["gemini", "Gemini"], ["claude", "Claude"],
  ["groq", "Groq"], ["mistral", "Mistral"], ["cerebras", "Cerebras"]];
const visibles = (l) => (l || []).filter((x) => (x.role === "user" || x.role === "assistant") && (x.content || (x.attachments || []).length));
const IDEAS = {
  "/app/logistica": ["¿Cómo va mi operación hoy?", "Muéstrame los pedidos en NOVEDAD", "¿Qué pedidos llevan más días sin moverse?"],
  "/app/clientes": ["¿Qué clientes necesitan a una persona?", "¿Quiénes han comprado 2 veces o más?", "Busca al cliente con teléfono…"],
  "/app/llamadas": ["¿Cómo van mis agentes de voz?", "¿Qué llamadas están en cola y por qué?"],
  "/app/conexiones": ["¿Qué me falta conectar para empezar?"],
  "/app/metricas": ["Resume mis métricas de los últimos 30 días y dime qué mejorar primero."],
};
const ACEPTA = "image/*,audio/*,video/*,.csv,.xlsx,.xls,.pdf,.txt,.md,.json";
const esVoz = (f) => /^(audio|video)\//.test(f.type || "");
const MAX_MB = 15;
const peso = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round((n || 0) / 1024))} KB`);
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
  const [pendiente, setPendiente] = useState(null);   // acción que espera Aplicar/Cancelar
  const [decidiendo, setDecidiendo] = useState(false);
  const [vista, setVista] = useState("chat");         // chat | historial
  const [hilos, setHilos] = useState(null);
  const [skills, setSkills] = useState([]);
  const [skillId, setSkillId] = useState("");
  const [modelo, setModelo] = useState("auto");
  const [adjuntos, setAdjuntos] = useState([]);   // subidos y listos para enviar
  const [subiendo, setSubiendo] = useState(false);
  const [grabando, setGrabando] = useState(false);
  const [oyendo, setOyendo] = useState(false);     // pasando el audio a texto
  const grabadora = useRef(null);
  const archivo = useRef(null);
  const fin = useRef(null);
  const campo = useRef(null);

  useEffect(() => { if (abierto) { campo.current?.focus(); fin.current?.scrollIntoView({ block: "end" }); } }, [abierto, msgs]);
  useEffect(() => {
    if (!abierto) return undefined;
    const esc = (e) => { if (e.key === "Escape") setAbierto(false); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [abierto]);
  useEffect(() => {
    if (!abierto || skills.length) return;
    api.get("/skills").then((r) => setSkills(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, [abierto, skills.length]);
  if (pathname === "/app") return null; // en la conversación completa no hace falta

  const nueva = () => { setTid(null); setMsgs([]); setPendiente(null); setError(""); setVista("chat"); };
  const verHistorial = async () => {
    setVista("historial"); setError("");
    try { const r = await api.get("/threads", { params: { limit: 30 } }); setHilos(Array.isArray(r.data) ? r.data : []); }
    catch (e) { setHilos([]); setError(errorText(e, "No pude traer tus conversaciones.")); }
  };
  const abrirHilo = async (id) => {
    setVista("chat"); setError(""); setBusy(true);
    try {
      const [h, t] = await Promise.all([api.get(`/threads/${id}/messages`), api.get(`/copilot/threads/${id}`).catch(() => null)]);
      setTid(id); setMsgs(visibles(h.data?.messages || h.data)); setPendiente(t?.data?.pending_action || null);
    } catch (e) { setError(errorText(e, "No pude abrir esa conversación.")); }
    finally { setBusy(false); }
  };
  const decidir = async (approve) => {
    if (!pendiente || decidiendo) return;
    setDecidiendo(true); setError("");
    try {
      const r = await api.post("/copilot/confirm", { action_id: pendiente.id, approve }, { timeout: 120000 });
      const d = r.data || {};
      setMsgs((m) => [...m,
        { id: `d-${pendiente.id}`, role: "user", content: `${approve ? "Aplicar" : "Cancelar"}: ${pendiente.resumen || pendiente.tool}` },
        { id: `c-${pendiente.id}`, role: "assistant", content: d.final_text || (approve ? "Listo, apliqué la acción." : "De acuerdo, no hice ningún cambio.") }]);
      setPendiente(d.pending_action?.id ? d.pending_action : null);
    } catch (e) { setError(errorText(e, "No pude aplicar la acción. Puede que haya vencido: pídela de nuevo.")); setPendiente(null); }
    finally { setDecidiendo(false); }
  };

  // Audio o video → texto en la caja, para revisarlo antes de enviar.
  const transcribir = async (blob, nombreArchivo) => {
    setError(""); setOyendo(true);
    try {
      const fd = new FormData();
      fd.append("file", blob, nombreArchivo);
      const r = await api.post("/files/transcribir", fd, { timeout: 180000 });
      setTexto((t) => `${t ? `${t} ` : ""}${r.data?.texto || ""}`.slice(0, 2000));
      campo.current?.focus();
    } catch (e) { setError(errorText(e, "No pude pasar el audio a texto. Inténtalo de nuevo.")); }
    finally { setOyendo(false); }
  };
  const grabar = async () => {
    if (grabando) { grabadora.current?.stop(); return; }
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Este navegador no deja grabar audio. Sube el audio con el clip."); return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const partes = [];
      rec.ondataavailable = (e) => { if (e.data?.size) partes.push(e.data); };
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        setGrabando(false);
        const blob = new Blob(partes, { type: rec.mimeType || "audio/webm" });
        if (blob.size) transcribir(blob, "dictado.webm");
      };
      grabadora.current = rec; rec.start(); setGrabando(true);
    } catch (e) { setError("No tengo permiso para usar el micrófono. Actívalo en el navegador e inténtalo de nuevo."); }
  };

  const subir = async (lista) => {
    const todos = Array.from(lista || []);
    const voces = todos.filter(esVoz);
    for (const v of voces) {
      if (v.size > 25 * 1048576) { setError(`«${v.name}» pesa más de 25 MB.`); continue; }
      await transcribir(v, v.name);   // eslint-disable-line no-await-in-loop
    }
    lista = todos.filter((f) => !esVoz(f));
    const files = Array.from(lista || []).slice(0, 5 - adjuntos.length);
    if (!files.length) return;
    setError(""); setSubiendo(true);
    try {
      for (const f of files) {
        if (f.size > MAX_MB * 1048576) { setError(`«${f.name}» pesa más de ${MAX_MB} MB.`); continue; }
        const fd = new FormData();
        fd.append("file", f);
        if (tid) fd.append("thread_id", tid);
        const r = await api.post("/files", fd, { timeout: 120000 });
        setAdjuntos((a) => [...a, { id: r.data.id, filename: r.data.filename, kind: r.data.kind, size: r.data.size }]);
      }
    } catch (e) { setError(errorText(e, "No pude subir el archivo. Inténtalo de nuevo.")); }
    finally { setSubiendo(false); if (archivo.current) archivo.current.value = ""; }
  };

  const enviar = async (t) => {
    const msg = (t ?? texto).trim();
    const mios = adjuntos;
    if ((!msg && !mios.length) || busy || subiendo || oyendo || grabando) return;
    setTexto(""); setError(""); setBusy(true); setAdjuntos([]);
    setMsgs((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: msg, attachments: mios }]);
    try {
      const r = await api.post("/copilot/run", { thread_id: tid || undefined, text: msg, file_ids: mios.map((a) => a.id),
        skill_id: skillId || undefined, model_override: modelo !== "auto" ? modelo : undefined }, { timeout: 180000 });
      const nuevo = r.data?.thread_id || tid;
      setTid(nuevo);
      setPendiente(r.data?.pending_action?.id ? r.data.pending_action : null);
      if (nuevo) {
        const h = await api.get(`/threads/${nuevo}/messages`);
        const lista = visibles(h.data?.messages || h.data);
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
              <button type="button" onClick={nueva} aria-label="Conversación nueva" title="Conversación nueva"
                      className="h-9 w-9 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><Plus size={15} /></button>
              <button type="button" onClick={() => (vista === "historial" ? setVista("chat") : verHistorial())}
                      aria-label="Mis conversaciones" title="Mis conversaciones" aria-pressed={vista === "historial"} data-testid="lyan-dock-historial"
                      className="h-9 w-9 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><ClockCounterClockwise size={15} /></button>
              <Link to={tid ? `/app?thread=${tid}` : "/app"} aria-label="Abrir la conversación completa" title="Conversación completa"
                    className="h-9 w-9 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><ArrowSquareOut size={15} /></Link>
              <button type="button" onClick={() => setAbierto(false)} aria-label="Cerrar asistente"
                      className="h-9 w-9 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><X size={16} /></button>
            </div>
          </header>
          <div className="grid grid-cols-2 gap-2 px-4 py-2 border-b border-zinc-800">
            <label className="text-[11px] text-zinc-300">Habilidad
              <select value={skillId} onChange={(e) => setSkillId(e.target.value)} data-testid="lyan-dock-skill"
                      className="mt-0.5 block w-full h-8 rounded-sm bg-zinc-900 border border-zinc-700 text-white text-xs px-1.5">
                <option value="">Ninguna</option>
                {skills.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
              </select>
            </label>
            <label className="text-[11px] text-zinc-300">Modelo
              <select value={modelo} onChange={(e) => setModelo(e.target.value)} data-testid="lyan-dock-modelo"
                      className="mt-0.5 block w-full h-8 rounded-sm bg-zinc-900 border border-zinc-700 text-white text-xs px-1.5">
                {MODELOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select>
            </label>
          </div>
          {vista === "historial" && (
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              <p className="text-sm text-zinc-300">Tus conversaciones</p>
              {hilos === null && <p className="text-sm text-zinc-400">Cargando…</p>}
              {hilos?.length === 0 && <p className="text-sm text-zinc-400">Todavía no hay conversaciones.</p>}
              {(hilos || []).map((h) => (
                <button key={h.id} type="button" onClick={() => abrirHilo(h.id)}
                        className={`block w-full text-left text-sm border rounded-sm px-3 py-2 hover:bg-zinc-900 ${
                          h.id === tid ? "border-zinc-500 text-white" : "border-zinc-800 text-zinc-100"}`}>
                  <span className="block truncate">{h.title || "Conversación"}</span>
                </button>
              ))}
              {error && <p className="text-sm text-zinc-100 border border-red-500/50 rounded-sm px-3 py-2" role="alert">{error}</p>}
            </div>
          )}
          {vista === "chat" && (
          <div className="flex-1 overflow-y-auto p-4 space-y-3" aria-live="polite">
            {msgs.length === 0 && !busy && (
              <div className="space-y-2">
                <p className="text-sm text-zinc-300 flex items-center gap-1.5"><Sparkle size={15} /> Prueba con una de estas:</p>
                {ideas.map((i) => (
                  <button key={i} type="button" onClick={() => (i.endsWith("…") ? (setTexto(i.replace("…", " ")), campo.current?.focus()) : enviar(i))}
                          className="block w-full text-left text-sm text-zinc-100 border border-zinc-800 rounded-sm px-3 py-2 hover:bg-zinc-900">{i}</button>
                ))}
              </div>
            )}
            {msgs.map((m) => (
              <div key={m.id || `${m.role}-${(m.content || "").slice(0, 24)}`} className={m.role === "user" ? "flex justify-end" : ""}>
                <div className={`max-w-[92%] text-sm rounded-sm px-3 py-2 break-words ${
                  m.role === "user" ? "bg-zinc-800 text-white whitespace-pre-wrap" : "border border-zinc-800 bg-zinc-900/60 text-zinc-100"}`}>
                  {m.role === "user" ? m.content : (
                    <div className="prose prose-invert prose-sm max-w-none prose-p:my-1.5 prose-headings:mt-3 prose-headings:mb-1.5 prose-table:text-xs overflow-x-auto [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content || " "}</ReactMarkdown>
                    </div>
                  )}
                  {(m.attachments || []).map((a) => (
                    <span key={a.id} className="mt-1 flex items-center gap-1.5 text-xs text-zinc-200">
                      <FileIcon size={13} /> <span className="truncate">{a.filename}</span>
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {busy && <p className="text-sm text-zinc-400">{nombre} está revisando…</p>}
            {pendiente && (
              <div className="border border-amber-500/60 rounded-sm px-3 py-2 space-y-2" data-testid="lyan-dock-pendiente">
                <p className="text-sm text-white">Antes de hacerlo, confirma:</p>
                <p className="text-sm text-zinc-100">{pendiente.resumen || pendiente.tool}</p>
                <div className="flex gap-2">
                  <button type="button" onClick={() => decidir(true)} disabled={decidiendo}
                          className="h-9 px-3 rounded-sm btn-cta-grad text-white text-sm disabled:opacity-50">Aplicar</button>
                  <button type="button" onClick={() => decidir(false)} disabled={decidiendo}
                          className="h-9 px-3 rounded-sm border border-zinc-600 text-zinc-100 text-sm hover:bg-zinc-800 disabled:opacity-50">Cancelar</button>
                </div>
              </div>
            )}
            {error && <p className="text-sm text-zinc-100 border border-red-500/50 rounded-sm px-3 py-2" role="alert">{error}</p>}
            <div ref={fin} />
          </div>
          )}
          {(adjuntos.length > 0 || subiendo) && (
            <ul className="px-3 pt-2 flex flex-wrap gap-1.5" aria-label="Archivos para enviar">
              {adjuntos.map((a) => (
                <li key={a.id} className="inline-flex items-center gap-1.5 max-w-full text-xs text-zinc-100 border border-zinc-700 rounded-sm pl-2 pr-1 py-1">
                  <FileIcon size={13} /> <span className="truncate max-w-[180px]">{a.filename}</span>
                  <span className="text-zinc-400">{peso(a.size)}</span>
                  <button type="button" onClick={() => setAdjuntos((l) => l.filter((x) => x.id !== a.id))}
                          aria-label={`Quitar ${a.filename}`} className="h-6 w-6 grid place-items-center rounded-sm hover:bg-zinc-800"><X size={12} /></button>
                </li>
              ))}
              {subiendo && <li className="text-xs text-zinc-300 py-1">Subiendo…</li>}
            </ul>
          )}
          {(grabando || oyendo) && (
            <p className="px-3 pt-2 text-xs text-zinc-200" role="status">
              {grabando ? "Grabando… pulsa el cuadro para terminar." : "Pasando el audio a texto…"}
            </p>
          )}
          <form onSubmit={(e) => { e.preventDefault(); enviar(); }} className="p-3 border-t border-zinc-800 flex gap-2"
                onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); subir(e.dataTransfer.files); }}>
            <input ref={archivo} type="file" multiple accept={ACEPTA} className="sr-only" tabIndex={-1} aria-hidden="true"
                   data-testid="lyan-dock-archivo" onChange={(e) => subir(e.target.files)} />
            <button type="button" onClick={() => archivo.current?.click()} disabled={subiendo || adjuntos.length >= 5}
                    aria-label="Adjuntar archivo, imagen, audio o video" title="Adjuntar archivo, imagen, audio o video"
                    className="h-10 w-10 shrink-0 grid place-items-center rounded-sm border border-zinc-700 text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"><Paperclip size={16} /></button>
            <button type="button" onClick={grabar} disabled={oyendo} data-testid="lyan-dock-voz"
                    aria-label={grabando ? "Terminar de grabar" : "Dictar con la voz"} aria-pressed={grabando}
                    title={grabando ? "Terminar de grabar" : "Dictar con la voz"}
                    className={`h-10 w-10 shrink-0 grid place-items-center rounded-sm border text-zinc-100 disabled:opacity-50 ${
                      grabando ? "border-red-400 bg-red-950" : "border-zinc-700 hover:bg-zinc-800"}`}>
              {grabando ? <Stop size={16} weight="fill" /> : <Microphone size={16} />}</button>
            <label htmlFor="lyan-dock-texto" className="sr-only">Mensaje para {nombre}</label>
            <input id="lyan-dock-texto" ref={campo} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={2000}
                   onPaste={(e) => { const fs = Array.from(e.clipboardData?.files || []); if (fs.length) { e.preventDefault(); subir(fs); } }}
                   placeholder={`Pídele algo a ${nombre}`} autoComplete="off"
                   className="flex-1 min-w-0 h-10 rounded-sm bg-black/40 border border-zinc-700 text-white text-sm px-3" />
            <button type="submit" disabled={busy || subiendo || (!texto.trim() && !adjuntos.length)} aria-label="Enviar"
                    className="h-10 w-10 shrink-0 grid place-items-center rounded-sm btn-cta-grad text-white disabled:opacity-50"><PaperPlaneRight size={16} weight="fill" /></button>
          </form>
        </aside>
      )}
    </>
  );
}
