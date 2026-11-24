import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Sidebar, { MenuButton, notifyThreadsChanged } from "../components/Sidebar";
import PageHelp from "../components/PageHelp";
import { api, formatDateTime } from "../lib/api";
import { useAssistantName, useOrgProfile, formatMoney, errorText } from "../lib/assistant";
import { usePacks } from "../lib/packs";
import { Toaster, toast } from "sonner";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import { Switch } from "../components/ui/switch";
import {
  Robot, PaperPlaneRight, Plus, TrashSimple, Wrench,
  CheckCircle, WarningCircle, User, Lightning, Sparkle,
  WarningDiamond, PhoneCall, Warning, Lifebuoy, ChartLineUp,
  CurrencyCircleDollar, Plug, SignOut, PlayCircle,
  Stack, CheckSquare, WhatsappLogo, HandPalm, XCircle, ClockCounterClockwise, ArrowsClockwise,
} from "@phosphor-icons/react";
import { useNavigate, useLocation } from "react-router-dom";
import MatrixRain from "../components/MatrixRain";
import Constellation from "../components/Constellation";
import ThemeToggle from "../components/ThemeToggle";

function ToolCard({ tc }) {
  const ok = tc.result?.ok !== false && !tc.result?.error;
  const inner = tc.result?.result;
  let summary = "";
  if (inner && typeof inner === "object") {
    if ("count" in inner) summary = `${inner.count} resultado(s)`;
    else if (inner.ok !== undefined) summary = inner.ok ? "OK" : (inner.error || "error");
  }
  const argsPreview = JSON.stringify(tc.args || {}).slice(0, 120);
  return (
    <div className={`border rounded-sm px-3 py-2 my-2 font-mono text-xs ${
      ok ? "border-zinc-800 bg-zinc-900/60" : "border-red-500/30 bg-red-500/5"
    }`} data-testid="tool-card">
      <div className="flex items-center gap-2 mb-1">
        {ok ? <CheckCircle size={13} className="text-green-400" />
            : <WarningCircle size={13} className="text-red-400" />}
        <Wrench size={11} className="text-zinc-500" />
        <span className="text-zinc-200">{tc.name}</span>
        {summary && <span className="text-zinc-500 ml-1">· {summary}</span>}
      </div>
      {argsPreview !== "{}" && (
        <div className="text-zinc-500 pl-5 break-all">{argsPreview}</div>
      )}
      {tc.result?.error && <div className="text-red-400 pl-5 mt-1">{tc.result.error}</div>}
    </div>
  );
}

function MessageBubble({ m, asistente = "Lyan" }) {
  const isUser = m.role === "user";
  const isAssistant = m.role === "assistant";
  return (
    <div className={`flex gap-3 py-4 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full overflow-hidden bg-zinc-800 border border-zinc-700 shrink-0 mt-1">
          <img src="/lyan.webp" alt={asistente} className="w-full h-full object-cover" />
        </div>
      )}
      <div className={`max-w-[85%] ${isUser ? "order-2" : ""}`}>
        <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1 flex items-center gap-2">
          {isUser ? "Tú" : asistente}
          {isAssistant && m.provider && (
            <span className="border border-zinc-700 bg-zinc-800/60 px-1.5 py-0.5 rounded text-[9px] tracking-widest">
              via {m.provider}
            </span>
          )}
        </div>
        {isAssistant && Array.isArray(m.tool_calls) && m.tool_calls.length > 0 && (
          <div className="mb-2">
            {m.tool_calls.map((tc, i) => <ToolCard key={i} tc={tc} />)}
          </div>
        )}
        <div className={`${isUser
            ? "border border-zinc-700 bg-zinc-800/70 px-4 py-3 rounded-sm"
            : "text-zinc-100"} text-sm leading-relaxed break-words`}
          data-testid={`msg-${m.role}`}>
          {isUser ? (
            <div className="whitespace-pre-wrap">{m.content}</div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-headings:mt-4 prose-headings:mb-2 prose-table:text-xs">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content || " "}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-sm bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0 mt-1 order-3">
          <User size={16} className="text-white" weight="duotone" />
        </div>
      )}
    </div>
  );
}

/** Etiqueta legible para una clave de parámetro: "numero_destino" → "Numero destino". */
function argLabel(k) {
  const t = String(k).replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function argValue(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "Sí" : "No";
  if (typeof v === "object") return JSON.stringify(v, null, 2);
  return String(v);
}

/**
 * Tarjeta de confirmación: el asistente propone una acción y NO la ejecuta
 * hasta que el usuario pulsa "Aplicar". Muestra el resumen y todos los
 * parámetros, sin recortar.
 */
function PendingActionCard({ action, asistente, busy, onDecide }) {
  const args = action?.args && typeof action.args === "object" ? Object.entries(action.args) : [];
  return (
    <div className="my-4 border border-yellow-500/30 bg-yellow-500/5 rounded-sm p-4"
         data-testid="pending-action-card" role="group" aria-label="Acción pendiente de confirmación">
      <div className="flex items-center gap-2 mb-2">
        <HandPalm size={18} weight="duotone" className="text-yellow-400" />
        <span className="text-sm font-semibold text-white">{asistente} quiere hacer esto</span>
        <span className="ml-auto text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border border-yellow-500/20 bg-yellow-500/10 text-yellow-400 rounded-sm">
          Espera tu confirmación
        </span>
      </div>
      <p className="text-sm text-zinc-100 leading-relaxed whitespace-pre-wrap" data-testid="pending-action-resumen">
        {action.resumen || "Acción propuesta por el asistente."}
      </p>

      <div className="mt-3 border border-zinc-800 rounded-sm bg-black/40">
        <div className="px-3 py-1.5 border-b border-zinc-800 text-[10px] uppercase tracking-widest font-mono text-zinc-500 flex items-center gap-1.5">
          <Wrench size={11} /> Herramienta: <span className="text-zinc-300 normal-case tracking-normal" data-testid="pending-action-tool">{action.tool}</span>
        </div>
        {args.length === 0 ? (
          <div className="px-3 py-2 text-xs text-zinc-500">Sin parámetros.</div>
        ) : (
          <dl className="divide-y divide-zinc-800" data-testid="pending-action-args">
            {args.map(([k, v]) => (
              <div key={k} className="px-3 py-2 grid grid-cols-1 sm:grid-cols-[180px_1fr] gap-1 sm:gap-3">
                <dt className="text-xs text-zinc-400">{argLabel(k)}</dt>
                <dd className="text-xs font-mono text-zinc-200 whitespace-pre-wrap break-words">{argValue(v)}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      <div className="flex flex-wrap justify-end gap-2 mt-3">
        <Button variant="outline" disabled={busy} onClick={() => onDecide(false)}
                data-testid="pending-action-cancel"
                className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
          <XCircle size={14} className="mr-1.5" /> Cancelar
        </Button>
        <Button disabled={busy} onClick={() => onDecide(true)}
                data-testid="pending-action-apply"
                className="btn-cta-grad rounded-sm">
          <CheckCircle size={14} weight="fill" className="mr-1.5" /> {busy ? "Aplicando…" : "Aplicar"}
        </Button>
      </div>
      <p className="text-[11px] text-zinc-500 mt-2">Nada cambia hasta que pulses «Aplicar».</p>
    </div>
  );
}

// ---- Acción pendiente: sobrevive a una recarga de la página -----------------
// El servidor guarda la acción y marca el mensaje con `pending_action_id`; el
// detalle (resumen y parámetros) se conserva en esta pestaña del navegador.
const PENDING_TTL_MS = 30 * 60 * 1000; // las acciones vencen a los 30 minutos
const pendingKey = (tid) => `zynex_pending_${tid}`;

function savePending(tid, action) {
  if (!tid) return;
  try {
    if (action && action.id) sessionStorage.setItem(pendingKey(tid), JSON.stringify({ ...action, saved_at: Date.now() }));
    else sessionStorage.removeItem(pendingKey(tid));
  } catch { /* almacenamiento no disponible: la tarjeta solo vive en memoria */ }
}

function readPending(tid) {
  if (!tid) return null;
  try {
    const raw = sessionStorage.getItem(pendingKey(tid));
    if (!raw) return null;
    const a = JSON.parse(raw);
    if (!a || !a.id || Date.now() - (a.saved_at || 0) > PENDING_TTL_MS) {
      sessionStorage.removeItem(pendingKey(tid));
      return null;
    }
    return a;
  } catch { return null; }
}

/** Acción pendiente de un hilo a partir de sus mensajes (y de lo guardado en la pestaña). */
function pendingFromMessages(tid, msgs) {
  const last = Array.isArray(msgs) && msgs.length ? msgs[msgs.length - 1] : null;
  if (!last || last.role !== "assistant") { savePending(tid, null); return null; }
  // 1) El servidor expone la acción completa en el último mensaje.
  if (last.pending_action && last.pending_action.id) return { ...last.pending_action, thread_id: tid };
  // 2) Solo expone el id: el detalle sale de lo guardado en esta pestaña.
  const stored = readPending(tid);
  if (stored && last.pending_action_id && stored.id === last.pending_action_id) return { ...stored, thread_id: tid };
  if (stored) savePending(tid, null); // ya se decidió o venció
  return null;
}

// ---- Bitácora: "Lo que hizo <asistente>" ------------------------------------
function activityArgs(args) {
  if (!args || typeof args !== "object") return "";
  const txt = JSON.stringify(args);
  return txt === "{}" ? "" : txt;
}

/** Lee GET /copilot/activity → {items:[{tool,args,ok,ms,created_at}],count}. */
function ActivityLog({ asistente, refreshKey }) {
  const [items, setItems] = useState([]);
  const [state, setState] = useState("loading"); // loading | ok | error | unavailable

  const load = async () => {
    setState((s) => (s === "ok" ? "ok" : "loading"));
    try {
      const r = await api.get("/copilot/activity");
      const list = Array.isArray(r.data) ? r.data : (r.data?.items || []);
      setItems(list);
      setState("ok");
    } catch (e) {
      setState(e?.response?.status === 404 ? "unavailable" : "error");
    }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [refreshKey]);

  return (
    <section data-testid="copilot-activity" aria-label={`Lo que hizo ${asistente}`}>
      <div className="flex items-center justify-between gap-2 mb-1">
        <h3 className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 flex items-center gap-2">
          <ClockCounterClockwise size={12} /> Lo que hizo {asistente}
        </h3>
        <button type="button" onClick={load} aria-label="Actualizar la bitácora"
                data-testid="copilot-activity-refresh"
                className="text-zinc-500 hover:text-white transition p-1 -m-1">
          <ArrowsClockwise size={12} />
        </button>
      </div>
      <p className="text-[11px] text-zinc-500 mb-3 leading-snug">
        Registro de cada herramienta que usó, con su resultado. Las más recientes primero.
      </p>

      {state === "loading" && <div className="text-xs text-zinc-500 font-mono">Cargando…</div>}
      {state === "unavailable" && (
        <div className="text-xs text-zinc-500" data-testid="copilot-activity-unavailable">
          La bitácora todavía no está disponible en tu servidor.
        </div>
      )}
      {state === "error" && (
        <div className="text-xs text-red-300" role="alert" data-testid="copilot-activity-error">
          No se pudo cargar la bitácora.{" "}
          <button type="button" onClick={load} className="underline underline-offset-2 hover:text-red-200">Reintentar</button>
        </div>
      )}
      {state === "ok" && items.length === 0 && (
        <div className="text-xs text-zinc-500" data-testid="copilot-activity-empty">
          Aún no ha usado ninguna herramienta. Cuando lo haga, quedará registrado aquí.
        </div>
      )}
      {state === "ok" && items.length > 0 && (
        <ol className="space-y-2" data-testid="copilot-activity-list">
          {items.map((it, i) => {
            const ok = it.ok !== false;
            const args = activityArgs(it.args);
            return (
              <li key={it.id || `${it.created_at}-${i}`}
                  className={`border rounded-sm px-2.5 py-2 text-xs ${ok ? "border-zinc-800 bg-zinc-900/40" : "border-red-500/30 bg-red-500/5"}`}
                  data-testid="copilot-activity-item">
                <div className="flex items-center gap-1.5">
                  {ok ? <CheckCircle size={12} weight="fill" className="text-green-400 shrink-0" />
                      : <WarningCircle size={12} weight="fill" className="text-red-400 shrink-0" />}
                  <span className="font-mono text-zinc-200 break-all">{it.tool || "herramienta"}</span>
                  <span className="sr-only">{ok ? "correcto" : "con error"}</span>
                </div>
                {args && (
                  <div className="font-mono text-[11px] text-zinc-500 mt-1 break-all" title={args}>
                    {args.length > 140 ? `${args.slice(0, 140)}…` : args}
                  </div>
                )}
                {!ok && it.error && <div className="text-red-300 mt-1 break-words">{it.error}</div>}
                <div className="font-mono text-[10px] text-zinc-500 mt-1 flex flex-wrap gap-x-2">
                  <span>{formatDateTime(it.created_at)}</span>
                  {it.ms != null && <span>{it.ms} ms</span>}
                  {it.confirmed && <span className="text-yellow-400">confirmada por ti</span>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

// Ideas para empezar: solo rellenan el cuadro de texto, no ejecutan nada.
const STARTERS = [
  "Crea un agente que llame a mis clientes para recordarles su cita de mañana.",
  "Dame un resumen de cómo va mi operación hoy y qué debo atender primero.",
  "Revisa mi configuración y dime qué me falta para empezar.",
  "Agrega a mi catálogo un producto o servicio. Te dicto el nombre y el precio.",
];

/**
 * Envía un mensaje al asistente. Usa POST /copilot/run (devuelve
 * `pending_action` cuando hay algo que confirmar); si el servidor aún no lo
 * tiene, cae al endpoint anterior /agent/run.
 */
async function runCopilot(body) {
  try {
    return await api.post("/copilot/run", body, { timeout: 120000 });
  } catch (e) {
    if (e?.response?.status === 404 || e?.response?.status === 405) {
      return api.post("/agent/run", body, { timeout: 120000 });
    }
    throw e;
  }
}

function ThreadsPanel({ threads, activeId, onSelect, onNew, onDelete }) {
  return (
    <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-950/70 flex flex-col h-screen sticky top-0">
      <div className="p-4 border-b border-zinc-800">
        <Button onClick={onNew} data-testid="copilot-new-thread"
          className="w-full btn-cta-grad rounded-sm h-9">
          <Plus size={14} className="mr-1" /> Nueva conversación
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 pt-4 pb-2 text-[10px] uppercase tracking-widest font-mono text-zinc-500">
          Conversaciones · {threads.length}
        </div>
        {threads.length === 0 && (
          <div className="px-4 text-xs text-zinc-500 py-8 text-center font-mono">Sin conversaciones aún.</div>
        )}
        {threads.map(t => (
          <div key={t.id}
            className={`group px-4 py-2.5 border-l-2 cursor-pointer transition-colors ${
              activeId === t.id
                ? "bg-zinc-800/60 border-white"
                : "border-transparent hover:bg-zinc-800/30 hover:border-zinc-600"
            }`}
            onClick={() => onSelect(t.id)}
            data-testid={`copilot-thread-${t.id}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-zinc-200 truncate flex-1">{t.title}</span>
              <button onClick={(e) => { e.stopPropagation(); onDelete(t.id); }}
                className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 transition"
                data-testid={`copilot-thread-delete-${t.id}`}>
                <TrashSimple size={12} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

export default function CopilotPage() {
  const navigate = useNavigate();
  const asistente = useAssistantName();
  const profile = useOrgProfile();
  const { hasCod } = usePacks();
  const [activityOpen, setActivityOpen] = useState(false);
  const [activityTick, setActivityTick] = useState(0); // fuerza la recarga de la bitácora
  const [pendingAction, setPendingActionState] = useState(null); // {id, tool, resumen, args, thread_id}
  const [menuOpen, setMenuOpen] = useState(false);               // menú lateral en celular
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const [confirming, setConfirming] = useState(false);
  const [threads, setThreads] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [skills, setSkills] = useState([]);
  const [skillId, setSkillId] = useState("none");
  const [modelOverride, setModelOverride] = useState("auto");
  const [autoMode, setAutoMode] = useState(false);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [me, setMe] = useState(null);
  const [connectors, setConnectors] = useState([]);
  const [kpi, setKpi] = useState({ recuperados: 0, total: 0, dinero: 0, tasa_pct: 0 });
  const [hitl, setHitl] = useState(null); // {agent, message, payload}
  const [orchestrating, setOrchestrating] = useState(false);
  const [cascadeOpen, setCascadeOpen] = useState(false);
  const [cascadeSegment, setCascadeSegment] = useState("red_this_week");
  const [cascadeLimit, setCascadeLimit] = useState(25);
  const [cascadeBusy, setCascadeBusy] = useState(false);
  const [cascadeHitl, setCascadeHitl] = useState(null); // {segment, hitl_required[], report}
  const [ceoOpen, setCeoOpen] = useState(false);
  const [ceoTarget, setCeoTarget] = useState("");
  const [ceoBusy, setCeoBusy] = useState(false);
  const scrollRef = useRef(null);

  const loadThreads = async () => {
    const r = await api.get("/threads");
    setThreads(r.data || []);
  };
  const loadSkills = async () => {
    const r = await api.get("/skills");
    setSkills(r.data || []);
  };
  const loadMe = async () => {
    try {
      const r = await api.get("/auth/me");
      setMe(r.data?.user || null);
    } catch { /* AuthGate should redirect */ }
  };
  const loadConnectors = async () => {
    try {
      const r = await api.get("/connectors");
      setConnectors(r.data || []);
    } catch { setConnectors([]); }
  };
  const connectedCount = (connectors || []).filter(
    c => c.status === "connected" || c.status === "configured" || c.status === "sip_registered"
  ).length;
  const needsOnboarding = !!me && connectors && connectors.length > 0 && connectedCount === 0;
  const loadKpi = async () => {
    try {
      const r = await api.get("/metrics");
      const d = r.data || {};
      const norte = d.norte || {};
      const roi = norte.roi || {};
      const recRate = norte.recovery_rate || {};
      // Try to derive counts from the queue_by_status legacy map.
      const qbs = d.queue_by_status || {};
      const recovered = (qbs.confirmado || 0) + (qbs.ya_recogio || 0);
      setKpi({
        recuperados: recovered,
        total:       d.queue_total ?? d.orders_total ?? 0,
        dinero:      roi.recovered_value ?? 0,
        tasa_pct:    recRate.value ?? 0,
      });
    } catch { /* metrics endpoint optional */ }
  };
  const loadMessages = async (tid) => {
    if (!tid) { setMessages([]); return; }
    const r = await api.get(`/threads/${tid}/messages`);
    const msgs = r.data || [];
    setMessages(msgs);
    // Recupera la tarjeta de acción pendiente (por ejemplo tras recargar la página).
    let restored = pendingFromMessages(tid, msgs);
    // La fuente de verdad es el servidor: así la tarjeta sobrevive a recargar la
    // página, a cerrar la pestaña y a abrir la conversación en otro dispositivo.
    let fromServer = false;
    try {
      const t = await api.get(`/copilot/threads/${tid}`);
      const pa = t.data?.pending_action;
      restored = pa && pa.id ? { ...pa, thread_id: tid } : null;
      savePending(tid, restored);
      fromServer = true;
    } catch { /* servidor antiguo o sin red: queda lo guardado en esta pestaña */ }
    setPendingActionState((prev) => (!fromServer && prev && prev.thread_id === tid ? prev : restored));
  };

  const location = useLocation();
  const urlThreadId = new URLSearchParams(location.search).get("thread");
  const urlPrompt = new URLSearchParams(location.search).get("prompt");
  const inputRef = useRef(null);

  // ?prompt=... (botones "Pídeselo a …") → precarga el cuadro de texto, sin enviarlo.
  useEffect(() => {
    if (!urlPrompt) return;
    setInput(urlPrompt);
    const params = new URLSearchParams(location.search);
    params.delete("prompt");
    const qs = params.toString();
    navigate(`${location.pathname}${qs ? `?${qs}` : ""}`, { replace: true });
    setTimeout(() => {
      const el = inputRef.current;
      if (el) { el.focus(); try { el.setSelectionRange(el.value.length, el.value.length); } catch { /* noop */ } }
    }, 50);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlPrompt]);

  useEffect(() => {
    loadThreads();
    loadSkills();
    loadMe();
    loadConnectors();
    loadKpi();
  }, []);

  // Sync active thread with the URL (?thread=<id>) — Sidebar drives it now.
  useEffect(() => {
    if (urlThreadId && urlThreadId !== activeId) setActiveId(urlThreadId);
    if (!urlThreadId && activeId) setActiveId(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlThreadId]);

  useEffect(() => { loadMessages(activeId); }, [activeId]);

  // Una acción pendiente pertenece a su conversación: al cambiar de hilo se oculta.
  useEffect(() => {
    // Solo se oculta en pantalla: lo guardado en la pestaña sigue ahí para cuando vuelvas al hilo.
    setPendingActionState((pa) => (pa && pa.thread_id && pa.thread_id !== activeId ? null : pa));
  }, [activeId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, running, pendingAction]);

  const newThread = () => {
    setActiveId(null); setMessages([]); setInput(""); setPendingActionState(null);
    navigate("/app"); // clear ?thread=
    notifyThreadsChanged();
  };
  const removeThread = async (id) => {
    await api.delete(`/threads/${id}`);
    if (activeId === id) newThread();
    loadThreads();
    notifyThreadsChanged();
  };

  // Envío único: lo usan el cuadro de texto y los atajos.
  const runText = async (text, { withSkill = true } = {}) => {
    if (!text || running) return;
    setInput("");
    setRunning(true);
    // Optimistic append
    setMessages(m => [...m, { id: `tmp-${Date.now()}`, role: "user", content: text, tool_calls: [] }]);
    try {
      const r = await runCopilot({
        thread_id: activeId,
        text,
        skill_id: withSkill && skillId !== "none" ? skillId : undefined,
        model_override: modelOverride !== "auto" ? modelOverride : undefined,
        auto_mode: autoMode,
      });
      const tid = r.data?.thread_id || activeId;
      if (!activeId && tid) setActiveId(tid);
      const pa = r.data?.pending_action;
      const nextPending = pa && pa.id ? { ...pa, thread_id: tid } : null;
      savePending(tid, nextPending);
      setPendingActionState(nextPending);
      await loadMessages(tid);
      setActivityTick((n) => n + 1);
      loadThreads();
      notifyThreadsChanged();
    } catch (e) {
      toast.error(errorText(e, "El asistente no pudo responder. Inténtalo de nuevo."));
      loadMessages(activeId);
    } finally { setRunning(false); }
  };

  const send = () => runText(input.trim());

  // Aplicar / Cancelar una acción propuesta: POST /copilot/confirm.
  const decidePending = async (approve) => {
    if (!pendingAction || confirming) return;
    const action = pendingAction;
    setConfirming(true);
    try {
      const r = await api.post("/copilot/confirm",
        { action_id: action.id, approve }, { timeout: 120000 });
      const d = r.data || {};
      const content = d.final_text || d.respuesta || d.message || d.detail
        || (approve ? "Listo, apliqué la acción." : "De acuerdo, no hice ningún cambio.");
      setMessages(m => [
        ...m,
        { id: `decision-${action.id}`, role: "user",
          content: approve ? `Aplicar: ${action.resumen || action.tool}` : `Cancelar: ${action.resumen || action.tool}`,
          tool_calls: [] },
        { id: `confirm-${action.id}`, role: "assistant", content: String(content),
          tool_calls: Array.isArray(d.tool_calls) ? d.tool_calls : [], provider: d.provider },
      ]);
      const next = d.pending_action;
      const tid = d.thread_id || action.thread_id;
      const nextPending = next && next.id ? { ...next, thread_id: tid } : null;
      savePending(tid, nextPending);
      setPendingActionState(nextPending);
      setActivityTick((n) => n + 1);
      loadThreads();
      notifyThreadsChanged();
    } catch (e) {
      const code = e?.response?.status;
      if (code === 404 || code === 409 || code === 410) {
        // La acción ya se aplicó, se canceló o venció: la tarjeta deja de ser válida.
        savePending(action.thread_id, null);
        setPendingActionState(null);
        toast.error(errorText(e, "Esta acción ya no está disponible (ya se decidió o venció). Pídela de nuevo."));
        loadMessages(action.thread_id);
        return;
      }
      // La tarjeta se queda para que el usuario pueda reintentar.
      toast.error(errorText(e, approve
        ? "No se pudo aplicar la acción. No se hizo ningún cambio; inténtalo de nuevo."
        : "No se pudo cancelar la acción. Inténtalo de nuevo."));
    } finally { setConfirming(false); }
  };

  const applySkill = (s) => {
    setSkillId(s.id);
    setInput(prev => prev ? prev : `/${s.trigger} `);
    toast.info(`Skill activada: ${s.name}`);
  };

  const doLogout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("zynex_session_ok");
    navigate("/login", { replace: true });
  };

  // Paquete de contra entrega: 5 agentes operativos del panel derecho.
  // Solo se pintan si el paquete está instalado (ver `hasCod`).
  const AGENTS = [
    { key: "riesgo_rto",          name: "Riesgo RTO",
      icon: WarningDiamond, tone: "text-orange-300",
      hint: "Detecta qué pedidos tienen más riesgo de devolución.",
      prompt: "Ejecuta Riesgo RTO sobre los últimos 50 pedidos y muéstrame los de riesgo alto." },
    { key: "confirmacion_cod",    name: "Confirmación COD",
      icon: PhoneCall, tone: "text-sky-300",
      hint: "Llama y escribe al cliente para confirmar entrega.",
      prompt: "Programa Confirmación COD para los pedidos nuevos de hoy y prioriza los de riesgo medio." },
    { key: "novedades",           name: "Novedades",
      icon: Warning, tone: "text-yellow-300",
      hint: "Detecta qué pedidos esperan en la oficina de envíos y necesitan rescate.",
      prompt: "Corre el sweep de Novedades y dame el semáforo por transportadora." },
    { key: "rescate_oficina",     name: "Rescate Oficina",
      icon: Lifebuoy, tone: "text-emerald-300",
      hint: "Recupera pedidos varados con WhatsApp + llamadas.",
      prompt: "Recupera los pedidos en rojo que esperan en la oficina de envíos y muéstrame el impacto." },
    { key: "analitica_operativa", name: "Analítica Operativa",
      icon: ChartLineUp, tone: "text-fuchsia-300",
      hint: "Muestra el valor recuperado y las devoluciones evitadas del día.",
      prompt: "Dame el reporte de hoy: recuperación, devoluciones evitadas y valor recuperado." },
  ];

  const runAgent = async (agent) => {
    // 1) Ask the orchestrator (deterministic; returns a HITL flag for money actions).
    setOrchestrating(true);
    try {
      const r = await api.post("/agents/orchestrate", {
        require_confirm_for_money: true,
      });
      const data = r.data;
      const line = (data?.chain?.[agent.key]);
      const summary = line ? JSON.stringify(line, null, 2) : "Orquestador ejecutado sin cambios.";
      const requires = !!data?.requires_human_confirmation
        && (agent.key === "rescate_oficina" || agent.key === "confirmacion_cod");
      if (requires) {
        setHitl({
          agent,
          summary,
          note: data?.note || "Acción con costo. Confirma para ejecutar.",
        });
      } else {
        // Auto-run: send the agent prompt to the assistant (LLM) so it can act using tools.
        await sendPrompt(agent.prompt);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falló el orquestador.");
    } finally { setOrchestrating(false); }
  };

  const confirmHitl = async () => {
    if (!hitl) return;
    const a = hitl.agent;
    setHitl(null);
    toast.success(`Ejecutando ${a.name}…`);
    await sendPrompt(a.prompt);
  };

  const sendPrompt = (text) => runText(text, { withSkill: false });

  // ---- Cascade: run the 5 agents across a segment ------------------
  const SEGMENTS = [
    { key: "red_this_week", label: "Rojos esta semana",  hint: "quedan 3 días o menos para recogerlo" },
    { key: "new_today",     label: "Nuevos hoy",         hint: "pedidos creados en las últimas 24 horas" },
    { key: "office_all",    label: "Todos los pendientes", hint: "todo pedido activo por recoger" },
  ];

  const runCascade = async () => {
    setCascadeBusy(true);
    try {
      const r = await api.post("/agents/cascade", {
        segment: cascadeSegment,
        limit: Number(cascadeLimit) || 25,
        require_confirm_for_money: true,
      });
      const rep = r.data || {};
      setCascadeOpen(false);
      // If there are HITL items → open a big confirmation dialog. Otherwise
      // pipe the summary straight to the assistant so it narrates it in the chat.
      if ((rep.hitl_required || []).length > 0) {
        setCascadeHitl(rep);
      } else {
        toast.success(`Cascada ejecutada · ${rep.processed} pedidos`);
        const s = rep.summary || {};
        const seg = SEGMENTS.find(x => x.key === rep.segment)?.label || rep.segment;
        await sendPrompt(
          `Corrí la cascada sobre "${seg}" (${rep.processed} pedidos). ` +
          `Riesgo alto: ${s.high_risk || 0}. Rescate planificado: ${s.rescate_planned || 0}. ` +
          `Muéstrame el resumen accionable en español y sugiere los próximos pasos.`
        );
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falló la cascada.");
    } finally { setCascadeBusy(false); }
  };

  const confirmCascadeHitl = async () => {
    const rep = cascadeHitl;
    setCascadeHitl(null);
    if (!rep) return;
    toast.success(`Ejecutando ${rep.hitl_required.length} acciones confirmadas…`);
    const seg = SEGMENTS.find(x => x.key === rep.segment)?.label || rep.segment;
    await sendPrompt(
      `Autorizo las ${rep.hitl_required.length} acciones con costo del segmento "${seg}". ` +
      `Ejecuta Rescate Oficina (cadencia + WhatsApp templates) y muéstrame el resultado por pedido.`
    );
  };

  // ---- Reporte diario → WhatsApp (paquete de contra entrega) --------
  const openCeoDialog = async () => {
    setCeoOpen(true);
    try {
      const r = await api.get("/agents/ceo-report/target");
      setCeoTarget(r.data?.target || "");
    } catch { /* keep empty */ }
  };

  const saveCeoTarget = async () => {
    setCeoBusy(true);
    try {
      await api.put("/agents/ceo-report/target", { target: ceoTarget.trim() });
      toast.success("Destinatario guardado.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "No se pudo guardar.");
    } finally { setCeoBusy(false); }
  };

  const sendCeoNow = async () => {
    if (!ceoTarget.trim()) { toast.error("Ingresa el número WhatsApp."); return; }
    setCeoBusy(true);
    try {
      // Save first so the cron uses the same target.
      await api.put("/agents/ceo-report/target", { target: ceoTarget.trim() });
      const r = await api.post("/agents/ceo-report/send-wa");
      if (r.data?.ok) {
        toast.success("Reporte enviado por WhatsApp.");
        setCeoOpen(false);
      } else {
        toast.error(r.data?.error || "Tu proveedor de WhatsApp rechazó el envío.");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falló el envío.");
    } finally { setCeoBusy(false); }
  };

  const activeSkill = skills.find(s => s.id === skillId);

  return (
    <div className="min-h-screen flex bg-zinc-950 text-zinc-100 relative">
      <Constellation density={55} />
      <MatrixRain />
      <Sidebar open={menuOpen} onClose={closeMenu} />
      <div className="flex-1 flex flex-col min-w-0 h-screen">
        <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-xl sticky top-0 z-10">
          <div className="px-4 py-3 md:px-8 md:py-4 flex flex-wrap items-center justify-between gap-3 md:gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <MenuButton onClick={() => setMenuOpen(true)} />
              <div className="w-9 h-9 shrink-0 rounded-full overflow-hidden border border-zinc-700 bg-zinc-800">
                <img src="/lyan.webp" alt={asistente} className="w-full h-full object-cover" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white" data-testid="copilot-title">{asistente} · Asistente</h2>
                <p className="text-[11px] font-mono text-zinc-500">
                  Propone · tú aplicas
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 md:gap-3 max-w-full">
              <Select value={modelOverride} onValueChange={setModelOverride}>
                <SelectTrigger data-testid="copilot-model-select"
                  className="w-32 bg-zinc-900 border-zinc-800 rounded-sm text-xs font-mono">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-zinc-800">
                  <SelectItem value="auto">Auto</SelectItem>
                  <SelectItem value="groq">Groq</SelectItem>
                  <SelectItem value="gemini">Gemini</SelectItem>
                  <SelectItem value="mistral">Mistral</SelectItem>
                  <SelectItem value="cerebras">Cerebras</SelectItem>
                  <SelectItem value="claude">Claude</SelectItem>
                </SelectContent>
              </Select>
              <Select value={skillId} onValueChange={setSkillId}>
                <SelectTrigger data-testid="copilot-skill-select"
                  className="w-36 md:w-56 bg-zinc-900 border-zinc-800 rounded-sm text-sm">
                  <Sparkle size={13} className="mr-1" />
                  <SelectValue placeholder="Sin skill" />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-zinc-800">
                  <SelectItem value="none">Sin skill</SelectItem>
                  {skills.map(s => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
                </SelectContent>
              </Select>
              <div className="flex items-center gap-2 border border-zinc-800 rounded-sm px-3 py-1.5 bg-zinc-900">
                <Lightning size={13} className={autoMode ? "text-yellow-400" : "text-zinc-500"} />
                <span className="text-xs text-zinc-300">Auto</span>
                <Switch checked={autoMode} onCheckedChange={setAutoMode}
                  data-testid="copilot-auto-toggle" />
              </div>
              <Button variant="outline" onClick={() => setActivityOpen(true)}
                      data-testid="copilot-activity-open"
                      className="xl:hidden h-8 text-xs rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
                <ClockCounterClockwise size={13} className="mr-1" /> Bitácora
              </Button>
              <ThemeToggle />
              {me && (
                <Button
                  variant="outline"
                  onClick={doLogout}
                  data-testid="copilot-logout"
                  className="h-8 text-xs rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
                  <SignOut size={12} className="mr-1" />
                  {me.nombre?.split(" ")[0] || "Salir"}
                </Button>
              )}
            </div>
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 md:px-8">
          <div className="max-w-3xl mx-auto py-6">
            {messages.length === 0 && !running && (
              <div className="py-12 text-center">
                <div className="mx-auto mb-5 flex items-center justify-center gap-2">
                  <img src="/lyan.webp" alt={asistente}
                       data-testid="copilot-mascot"
                       className="w-9 h-9 rounded-full object-cover ring-1 ring-cyan-400/40" />
                  <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
                    {asistente} · Asistente
                  </span>
                </div>

                <h1 className="text-3xl md:text-4xl font-semibold text-white mb-3 tracking-tight"
                    data-testid="copilot-greeting">
                  Hola{me?.nombre ? <span className="text-white"> {me.nombre}</span> : ""}, soy{" "}
                  <span className="neon-text">{asistente}</span>
                  <span className="text-white">, tu asistente.</span>
                </h1>
                <p className="text-sm text-zinc-400 mb-6 max-w-lg mx-auto">
                  Dime qué necesitas con tus palabras. Antes de cambiar algo te muestro qué voy a hacer
                  y espero a que pulses «Aplicar».
                </p>

                <div className="max-w-3xl mx-auto mb-6 text-left" data-testid="copilot-howitworks-slot">
                  <PageHelp helpKey="copilot" />
                </div>

                {needsOnboarding && (
                  <div className="max-w-3xl mx-auto mb-8 border border-cyan-500/40 bg-cyan-500/5 rounded-sm p-4 text-left flex items-center gap-4"
                       data-testid="onboarding-banner">
                    <div className="w-10 h-10 rounded-sm bg-cyan-500/15 border border-cyan-500/40 grid place-items-center shrink-0">
                      <Lightning size={18} weight="fill" className="text-cyan-300" />
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-semibold text-white">Termina de configurar tu cuenta.</div>
                      <p className="text-xs text-zinc-400 leading-snug">
                        3 pasos rápidos: el perfil de tu negocio, tu llave de inteligencia artificial y tu primer agente.
                      </p>
                    </div>
                    <Button onClick={() => navigate("/app/onboarding")}
                            data-testid="onboarding-start-btn"
                            className="btn-cta-grad rounded-sm h-9 whitespace-nowrap">
                      Empezar
                    </Button>
                  </div>
                )}

                {/* Ideas para empezar — rellenan el cuadro de texto, no ejecutan nada */}
                <div className="max-w-3xl mx-auto mb-8 text-left">
                  <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3 text-center">
                    Ideas para empezar — pulsa una y ajústala
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {STARTERS.map((t, i) => (
                      <button key={i} type="button"
                              onClick={() => { setInput(t); inputRef.current?.focus(); }}
                              data-testid={`copilot-starter-${i}`}
                              className="zx-suggest-card text-left text-sm text-zinc-200 leading-snug">
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Skill chips */}
                {skills.length > 0 && (
                  <div className="max-w-2xl mx-auto">
                    <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3">
                      Skills — haz clic para usar
                    </div>
                    <div className="flex flex-wrap gap-2 justify-center">
                      {skills.map((s) => (
                        <button key={s.id} onClick={() => applySkill(s)}
                          className="zx-skill-chip"
                          data-testid={`copilot-skill-quick-${s.trigger}`}>
                          <Sparkle size={11} weight="fill" /> {s.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            {messages.map(m => <MessageBubble key={m.id} m={m} asistente={asistente} />)}
            {pendingAction && !running && (
              <PendingActionCard action={pendingAction} asistente={asistente}
                                 busy={confirming} onDecide={decidePending} />
            )}
            {running && (
              <div className="flex gap-3 py-4 items-center">
                <div className="w-7 h-7 rounded-sm bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                  <img src="/lyan.webp" alt={asistente} className="w-4 h-4 rounded-full object-cover" />
                </div>
                <div className="text-sm font-mono text-zinc-500">{asistente} está pensando…</div>
                <div className="flex gap-1 ml-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse" />
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            )}
          </div>
        </div>

        <footer className="border-t border-zinc-800 bg-zinc-950 px-4 md:px-8 py-3 md:py-4" data-bottom-bar="tall">
          <div className="max-w-3xl mx-auto">
            {activeSkill && activeSkill.id !== "none" && (
              <div className="mb-2 text-[11px] font-mono text-zinc-500 flex items-center gap-2">
                <Sparkle size={11} /> Skill activa: <span className="text-zinc-300">{activeSkill.name}</span>
              </div>
            )}
            <div className="border border-zinc-800 bg-zinc-900 rounded-sm focus-within:border-zinc-600 transition">
              <Textarea data-testid="copilot-input"
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
                }}
                placeholder={`Escríbele a ${asistente}…  (Enter para enviar · Shift+Enter para salto de línea)`}
                className="border-0 bg-transparent focus-visible:ring-0 min-h-[60px] resize-none text-sm rounded-none" />
              <div className="border-t border-zinc-800 px-3 py-2 flex items-center justify-between">
                <div className="text-[10px] font-mono text-zinc-500">
                  {input.length} caracteres · {running ? "ejecutando…" : "listo"}
                </div>
                <Button onClick={send} disabled={!input.trim() || running}
                  data-testid="copilot-send"
                  className="btn-cta-grad rounded-sm h-8 text-white">
                  <PaperPlaneRight size={13} className="mr-1" /> Enviar
                </Button>
              </div>
            </div>
          </div>
        </footer>
      </div>

      {/* Panel derecho: bitácora siempre; lo de contra entrega solo con su paquete. */}
      <aside className="hidden xl:flex w-72 shrink-0 border-l border-zinc-800 bg-zinc-950/70 flex-col h-screen sticky top-0 overflow-y-auto"
             data-testid="copilot-right-rail">
        <div className="p-5 border-b border-zinc-800">
          <ActivityLog asistente={asistente} refreshKey={activityTick} />
        </div>

        {hasCod && (kpi.total > 0 || kpi.dinero > 0) && (
        <div className="p-5 border-b border-zinc-800" data-testid="copilot-cod-kpi">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-2 flex items-center gap-2">
            <CurrencyCircleDollar size={12} /> Valor de pedidos recuperados
          </div>
          <div className="text-2xl font-semibold text-white" data-testid="kpi-dinero">
            {formatMoney(kpi.dinero, profile?.moneda)}
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            <span data-testid="kpi-recuperados">{kpi.recuperados}</span>
            {" / "}
            <span data-testid="kpi-total">{kpi.total}</span> pedidos
            {" · "}
            <span className="text-emerald-400" data-testid="kpi-tasa">{kpi.tasa_pct}%</span>
          </div>

          <Button
            onClick={openCeoDialog}
            data-testid="ceo-wa-btn"
            variant="outline"
            className="w-full mt-3 h-8 text-xs rounded-sm border-emerald-700/60 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-200">
            <WhatsappLogo size={13} weight="fill" className="mr-1 text-emerald-300" />
            Enviar reporte diario por WhatsApp
          </Button>
        </div>
        )}

        <div className="p-5 border-b border-zinc-800">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3 flex items-center gap-2">
            <Plug size={12} /> Tus conexiones
          </div>
          <div className="space-y-1.5">
            {(connectors || []).slice(0, 8).map((c) => {
              const ok = c.status === "connected" || c.status === "configured";
              return (
                <div key={c.key} className="flex items-center justify-between text-xs"
                     data-testid={`connector-${c.key}`}>
                  <span className="text-zinc-300 truncate">{c.name || c.key}</span>
                  <span className={`text-[10px] font-mono uppercase tracking-widest ${
                    ok ? "text-emerald-400" : "text-zinc-500"}`}>
                    {ok ? "OK" : "—"}
                  </span>
                </div>
              );
            })}
            {(!connectors || connectors.length === 0) && (
              <div className="text-xs text-zinc-500">Sin conectores configurados.</div>
            )}
          </div>
          <Button
            variant="outline"
            onClick={() => navigate("/app/config")}
            data-testid="copilot-open-credentials"
            className="w-full mt-3 h-8 text-xs rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
            Configurar credenciales
          </Button>
        </div>

        {hasCod && (
        <div className="p-5" data-testid="copilot-cod-agents">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1 flex items-center justify-between">
            <span>Contra entrega · 5 agentes</span>
            <span className="px-1.5 py-0.5 border border-yellow-500/20 bg-yellow-500/10 text-yellow-400 rounded-sm"
                  data-testid="agents-simulation-badge">Simulación</span>
          </div>
          <p className="text-[11px] text-zinc-500 mb-3 leading-snug">
            Estos botones calculan un plan y se lo pasan al asistente. No llaman ni escriben a nadie por sí solos.
          </p>
          <div className="space-y-2">
            {AGENTS.map(a => (
              <button
                key={a.key}
                onClick={() => runAgent(a)}
                disabled={orchestrating}
                data-testid={`agent-rail-${a.key}`}
                className="w-full text-left border border-zinc-800 bg-zinc-900/40 hover:bg-zinc-800/60 rounded-sm px-3 py-2 flex items-center gap-2 transition">
                <a.icon size={16} className={a.tone} weight="duotone" />
                <span className="text-sm text-zinc-200 flex-1 truncate">{a.name}</span>
                <span className="text-[9px] font-mono uppercase tracking-widest text-yellow-400/80">Simulación</span>
              </button>
            ))}
          </div>

          <Button
            onClick={() => setCascadeOpen(true)}
            data-testid="cascade-rail-btn"
            className="w-full mt-4 h-9 rounded-sm btn-cta-grad text-white text-xs font-semibold">
            <Stack size={14} className="mr-1" /> Simular cascada
          </Button>
        </div>
        )}

        <div className="mt-auto border-t border-zinc-800 p-4 text-[10px] font-mono text-zinc-500">
          {me?.email ? <div className="truncate">{me.email}</div> : null}
          <div>org · <span className="text-zinc-300">{me?.org_id?.slice(0, 22)}</span></div>
        </div>
      </aside>

      {/* Bitácora en pantallas donde no cabe el panel derecho */}
      <Dialog open={activityOpen} onOpenChange={setActivityOpen}>
        <DialogContent data-testid="copilot-activity-dialog"
                       className="bg-zinc-950 border-zinc-800 text-white max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Bitácora</DialogTitle>
            <DialogDescription className="text-zinc-400">
              Todo lo que {asistente} hizo en tu cuenta queda registrado.
            </DialogDescription>
          </DialogHeader>
          {activityOpen && <ActivityLog asistente={asistente} refreshKey={activityTick} />}
        </DialogContent>
      </Dialog>

      {/* Human-in-the-loop confirmation modal (money / mass actions) */}
      <Dialog open={!!hitl} onOpenChange={(o) => !o && setHitl(null)}>
        <DialogContent data-testid="hitl-dialog" className="bg-zinc-950 border-zinc-800 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <WarningDiamond size={18} className="text-yellow-400" weight="duotone" />
              Confirmar acción con costo
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              {hitl?.note} — Agente: <b className="text-white">{hitl?.agent?.name}</b>
            </DialogDescription>
          </DialogHeader>
          <pre className="text-[11px] font-mono bg-black/40 border border-zinc-800 rounded-sm p-3 max-h-52 overflow-auto whitespace-pre-wrap"
               data-testid="hitl-summary">
{hitl?.summary}
          </pre>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setHitl(null)}
                    data-testid="hitl-no"
                    className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
              No, cancelar
            </Button>
            <Button onClick={confirmHitl}
                    data-testid="hitl-yes"
                    className="btn-cta-grad rounded-sm">
              Sí, ejecutar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cascade segment picker */}
      <Dialog open={cascadeOpen} onOpenChange={setCascadeOpen}>
        <DialogContent data-testid="cascade-dialog" className="bg-zinc-950 border-zinc-800 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Stack size={18} weight="duotone" />
              Simular los 5 agentes en cascada
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              Simulación: calcula el plan sobre el segmento que elijas y se lo pasa al asistente.
              Ninguna llamada ni mensaje sale sin tu confirmación.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            {SEGMENTS.map((s) => (
              <button
                key={s.key}
                onClick={() => setCascadeSegment(s.key)}
                data-testid={`cascade-segment-${s.key}`}
                className={`w-full text-left border rounded-sm px-3 py-2.5 transition flex items-start gap-3 ${
                  cascadeSegment === s.key
                    ? "border-white bg-white/5"
                    : "border-zinc-800 bg-zinc-900/40 hover:bg-zinc-800/60"
                }`}>
                <CheckSquare
                  size={16}
                  weight={cascadeSegment === s.key ? "fill" : "regular"}
                  className={cascadeSegment === s.key ? "text-white" : "text-zinc-500"}
                />
                <div>
                  <div className="text-sm font-semibold text-white">{s.label}</div>
                  <div className="text-[11px] text-zinc-400">{s.hint}</div>
                </div>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-2">
            <span className="text-xs font-mono text-zinc-500">Máx. pedidos:</span>
            <input
              type="number"
              min={1}
              max={100}
              value={cascadeLimit}
              onChange={(e) => setCascadeLimit(e.target.value)}
              data-testid="cascade-limit"
              className="w-20 h-8 rounded-sm bg-black/40 border border-zinc-800 px-2 text-sm text-white focus:outline-none focus:border-zinc-500"
            />
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setCascadeOpen(false)}
                    data-testid="cascade-cancel"
                    className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
              Cancelar
            </Button>
            <Button onClick={runCascade} disabled={cascadeBusy}
                    data-testid="cascade-run"
                    className="btn-cta-grad rounded-sm">
              {cascadeBusy ? "Simulando…" : "Simular cascada"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cascade HITL — batch confirmation for money actions across many orders */}
      <Dialog open={!!cascadeHitl} onOpenChange={(o) => !o && setCascadeHitl(null)}>
        <DialogContent data-testid="cascade-hitl-dialog" className="bg-zinc-950 border-zinc-800 text-white max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <WarningDiamond size={18} className="text-yellow-400" weight="duotone" />
              {cascadeHitl?.hitl_required?.length || 0} pedidos requieren tu confirmación
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              La cascada procesó <b className="text-white">{cascadeHitl?.processed}</b> pedidos.
              Los listados abajo implican costo (llamadas, WhatsApp o prepago).
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-64 overflow-y-auto border border-zinc-800 rounded-sm bg-black/40 divide-y divide-zinc-800"
               data-testid="cascade-hitl-list">
            {(cascadeHitl?.hitl_required || []).map((h) => (
              <div key={h.order_id} className="px-3 py-2 text-xs">
                <div className="text-white font-mono">{h.order_id?.slice(0, 12)} · {h.customer || "—"}</div>
                <div className="text-zinc-400">{h.reason}</div>
              </div>
            ))}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setCascadeHitl(null)}
                    data-testid="cascade-hitl-no"
                    className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
              No, revisar 1×1
            </Button>
            <Button onClick={confirmCascadeHitl}
                    data-testid="cascade-hitl-yes"
                    className="btn-cta-grad rounded-sm">
              Sí, ejecutar todo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CEO Report → WhatsApp destination + send-now */}
      <Dialog open={ceoOpen} onOpenChange={setCeoOpen}>
        <DialogContent data-testid="ceo-wa-dialog" className="bg-zinc-950 border-zinc-800 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <WhatsappLogo size={18} weight="fill" className="text-emerald-400" />
              Reporte diario por WhatsApp
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              El snapshot del día se enviará automáticamente a las <b className="text-white">08:15 hora Bogotá</b>.
              Ingresa el número del grupo/lider en formato internacional (ej. <code>+573001234567</code>).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 mt-2">
            <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500">
              Número WhatsApp destino
            </label>
            <input
              type="text"
              value={ceoTarget}
              onChange={(e) => setCeoTarget(e.target.value)}
              placeholder="+573001234567"
              data-testid="ceo-wa-target"
              className="w-full h-10 rounded-sm bg-black/40 border border-zinc-800 px-3 text-sm text-white focus:outline-none focus:border-zinc-500"
            />
            <p className="text-[11px] text-zinc-500 leading-snug">
              Tu proveedor de WhatsApp debe estar conectado en{" "}
              <b className="text-zinc-300">Conexiones → Credenciales</b>.
            </p>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={saveCeoTarget} disabled={ceoBusy || !ceoTarget.trim()}
                    data-testid="ceo-wa-save"
                    className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
              Guardar destinatario
            </Button>
            <Button onClick={sendCeoNow} disabled={ceoBusy || !ceoTarget.trim()}
                    data-testid="ceo-wa-send"
                    className="btn-cta-grad rounded-sm">
              <WhatsappLogo size={13} weight="fill" className="mr-1" />
              {ceoBusy ? "Enviando…" : "Enviar ahora"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Toaster theme="dark" position="top-right"
        toastOptions={{ style: { background: "#18181b", border: "1px solid #27272a", color: "#f4f4f5" } }} />
    </div>
  );
}
