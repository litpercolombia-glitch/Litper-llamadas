import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Sidebar from "../components/Sidebar";
import { api, formatCOP } from "../lib/api";
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
} from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";
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

function MessageBubble({ m }) {
  const isUser = m.role === "user";
  const isAssistant = m.role === "assistant";
  return (
    <div className={`flex gap-3 py-4 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-sm bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0 mt-1">
          <Robot size={16} className="text-white" weight="duotone" />
        </div>
      )}
      <div className={`max-w-[85%] ${isUser ? "order-2" : ""}`}>
        <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1 flex items-center gap-2">
          {isUser ? "Tú" : "Marcus"}
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
  const [kpi, setKpi] = useState({ recuperados: 0, total: 0, dinero_cop: 0, tasa_pct: 0 });
  const [hitl, setHitl] = useState(null); // {agent, message, payload}
  const [orchestrating, setOrchestrating] = useState(false);
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
  const loadKpi = async () => {
    try {
      const r = await api.get("/metrics");
      const d = r.data || {};
      const norte = d.norte || {};
      const roi = norte.roi_cop || {};
      const recRate = norte.recovery_rate || {};
      // Try to derive counts from the queue_by_status legacy map.
      const qbs = d.queue_by_status || {};
      const recovered = (qbs.confirmado || 0) + (qbs.ya_recogio || 0);
      setKpi({
        recuperados: recovered,
        total:       d.queue_total ?? d.orders_total ?? 0,
        dinero_cop:  roi.recovered_value_cop ?? 0,
        tasa_pct:    recRate.value ?? 0,
      });
    } catch { /* metrics endpoint optional */ }
  };
  const loadMessages = async (tid) => {
    if (!tid) { setMessages([]); return; }
    const r = await api.get(`/threads/${tid}/messages`);
    setMessages(r.data || []);
  };

  useEffect(() => {
    loadThreads();
    loadSkills();
    loadMe();
    loadConnectors();
    loadKpi();
  }, []);

  useEffect(() => { loadMessages(activeId); }, [activeId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, running]);

  const newThread = () => { setActiveId(null); setMessages([]); setInput(""); };
  const removeThread = async (id) => {
    await api.delete(`/threads/${id}`);
    if (activeId === id) newThread();
    loadThreads();
  };

  const send = async () => {
    if (!input.trim() || running) return;
    const text = input.trim();
    setInput("");
    setRunning(true);
    // Optimistic append
    setMessages(m => [...m, { id: "tmp", role: "user", content: text, tool_calls: [] }]);
    try {
      const r = await api.post("/agent/run", {
        thread_id: activeId,
        text,
        skill_id: skillId !== "none" ? skillId : undefined,
        model_override: modelOverride !== "auto" ? modelOverride : undefined,
        auto_mode: autoMode,
      }, { timeout: 120000 });
      if (!activeId) setActiveId(r.data.thread_id);
      await loadMessages(r.data.thread_id);
      loadThreads();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
      loadMessages(activeId);
    } finally { setRunning(false); }
  };

  const applySkill = (s) => {
    setSkillId(s.id);
    setInput(prev => prev ? prev : `/${s.trigger} `);
    toast.info(`Skill activada: ${s.name}`);
  };

  const doLogout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("litper_operator_ok");
    navigate("/login", { replace: true });
  };

  // 5 operational agents shown on the empty state / right rail.
  const AGENTS = [
    { key: "riesgo_rto",          name: "Riesgo RTO",
      icon: WarningDiamond, tone: "text-orange-300",
      hint: "Puntúa el riesgo del pedido y decide si exigir prepago.",
      prompt: "Ejecuta Riesgo RTO sobre los últimos 50 pedidos y muéstrame los de riesgo alto (score ≥ 60)." },
    { key: "confirmacion_cod",    name: "Confirmación COD",
      icon: PhoneCall, tone: "text-sky-300",
      hint: "Verifica intención + dirección por voz y WhatsApp.",
      prompt: "Programa Confirmación COD para todos los pedidos nuevos de hoy. Prioriza los de riesgo medio." },
    { key: "novedades",           name: "Novedades",
      icon: Warning, tone: "text-yellow-300",
      hint: "Sweep del carrier, semáforo y disparo de Rescate.",
      prompt: "Corre el sweep de Novedades y dame el semáforo por transportadora." },
    { key: "rescate_oficina",     name: "Rescate Oficina",
      icon: Lifebuoy, tone: "text-emerald-300",
      hint: "Cadencia hasta 5 intentos con templates aprobados.",
      prompt: "Recupera los pedidos rojos en oficina con la cadencia 0-3d / 4-7d / 8+ y muéstrame el impacto." },
    { key: "analitica_operativa", name: "Analítica Operativa",
      icon: ChartLineUp, tone: "text-fuchsia-300",
      hint: "Recuperación, entrega efectiva y $ recuperado.",
      prompt: "Dame el reporte CEO del día: recuperación, devoluciones evitadas y $ recuperado." },
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
        // Auto-run: send the agent prompt to Marcus (LLM) so he can act using tools.
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

  const sendPrompt = async (text) => {
    if (!text) return;
    setInput("");
    setRunning(true);
    setMessages(m => [...m, { id: "tmp", role: "user", content: text, tool_calls: [] }]);
    try {
      const r = await api.post("/agent/run", {
        thread_id: activeId, text,
        model_override: modelOverride !== "auto" ? modelOverride : undefined,
        auto_mode: autoMode,
      }, { timeout: 120000 });
      if (!activeId) setActiveId(r.data.thread_id);
      await loadMessages(r.data.thread_id);
      loadThreads();
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
      loadMessages(activeId);
    } finally { setRunning(false); }
  };

  const activeSkill = skills.find(s => s.id === skillId);

  return (
    <div className="min-h-screen flex bg-zinc-950 text-zinc-100 relative">
      <Constellation density={55} />
      <MatrixRain />
      <Sidebar />
      <ThreadsPanel threads={threads} activeId={activeId}
        onSelect={setActiveId} onNew={newThread} onDelete={removeThread} />
      <div className="flex-1 flex flex-col min-w-0 h-screen">
        <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-xl sticky top-0 z-10">
          <div className="px-8 py-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-sm bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                <Robot size={20} className="text-white" weight="duotone" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Marcus · Litper Copilot</h2>
                <p className="text-[11px] font-mono text-zinc-500">
                  Agente autónomo con {skills.length} skills · claude-sonnet-4-6
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
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
                  className="w-56 bg-zinc-900 border-zinc-800 rounded-sm text-sm">
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

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-8">
          <div className="max-w-3xl mx-auto py-6">
            {messages.length === 0 && !running && (
              <div className="py-12 text-center">
                {/* 3D glowing mascot ring */}
                <div className="mx-auto mascot-ring mb-8" data-testid="copilot-mascot">
                  <Robot size={72} className="text-white drop-shadow-[0_0_10px_rgba(90,200,250,0.6)]" weight="duotone" />
                </div>

                <h1 className="text-3xl md:text-4xl font-semibold text-white mb-3 tracking-tight"
                    data-testid="copilot-greeting">
                  Hola {me?.nombre ? <span className="text-white">{me.nombre}</span> : ""}, soy{" "}
                  <span className="neon-text">Marcus</span>{" "}
                  <span className="text-white">— tu Copilot de 5 agentes.</span>
                </h1>
                <p className="text-sm text-zinc-400 mb-10 max-w-lg mx-auto">
                  Elige un agente operativo — yo pido tu confirmación cuando la acción tiene costo.
                </p>

                {/* 5 operational agents */}
                <div className="grid grid-cols-1 md:grid-cols-5 gap-3 max-w-4xl mx-auto mb-10">
                  {AGENTS.map((a) => (
                    <div key={a.key}
                         className="zx-suggest-card text-left flex flex-col gap-2 h-full"
                         onClick={() => runAgent(a)}
                         data-testid={`agent-card-${a.key}`}>
                      <a.icon size={22} className={`${a.tone} mb-1`} weight="duotone" />
                      <div className="text-sm font-semibold text-white leading-tight">{a.name}</div>
                      <div className="text-[11px] text-zinc-400 leading-snug">{a.hint}</div>
                      <div className="mt-auto pt-2 text-[10px] font-mono uppercase tracking-widest text-zinc-500 flex items-center gap-1">
                        <PlayCircle size={11} /> Ejecutar
                      </div>
                    </div>
                  ))}
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
            {messages.map(m => <MessageBubble key={m.id} m={m} />)}
            {running && (
              <div className="flex gap-3 py-4 items-center">
                <div className="w-7 h-7 rounded-sm bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                  <Robot size={16} className="text-white" weight="duotone" />
                </div>
                <div className="text-sm font-mono text-zinc-500">Marcus está pensando…</div>
                <div className="flex gap-1 ml-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse" />
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-pulse" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            )}
          </div>
        </div>

        <footer className="border-t border-zinc-800 bg-zinc-950 px-8 py-4">
          <div className="max-w-3xl mx-auto">
            {activeSkill && activeSkill.id !== "none" && (
              <div className="mb-2 text-[11px] font-mono text-zinc-500 flex items-center gap-2">
                <Sparkle size={11} /> Skill activa: <span className="text-zinc-300">{activeSkill.name}</span>
              </div>
            )}
            <div className="border border-zinc-800 bg-zinc-900 rounded-sm focus-within:border-zinc-600 transition">
              <Textarea data-testid="copilot-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
                }}
                placeholder="Pregúntale a Marcus…  (Enter para enviar · Shift+Enter para salto de línea)"
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

      {/* Right rail: $ recuperado + BYOK connectors */}
      <aside className="hidden xl:flex w-72 shrink-0 border-l border-zinc-800 bg-zinc-950/70 flex-col h-screen sticky top-0"
             data-testid="copilot-right-rail">
        <div className="p-5 border-b border-zinc-800">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-2 flex items-center gap-2">
            <CurrencyCircleDollar size={12} /> $ Recuperado (hoy)
          </div>
          <div className="text-2xl font-semibold text-white" data-testid="kpi-dinero">
            {formatCOP(kpi.dinero_cop)}
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            <span data-testid="kpi-recuperados">{kpi.recuperados}</span>
            {" / "}
            <span data-testid="kpi-total">{kpi.total}</span> pedidos
            {" · "}
            <span className="text-emerald-400" data-testid="kpi-tasa">{kpi.tasa_pct}%</span>
          </div>
        </div>

        <div className="p-5 border-b border-zinc-800">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3 flex items-center gap-2">
            <Plug size={12} /> Conectores BYOK
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

        <div className="p-5 flex-1 overflow-y-auto">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-3">
            5 agentes operativos
          </div>
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
                <PlayCircle size={12} className="text-zinc-500" />
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-zinc-800 p-4 text-[10px] font-mono text-zinc-500">
          {me?.email ? <div className="truncate">{me.email}</div> : null}
          <div>org · <span className="text-zinc-300">{me?.org_id?.slice(0, 22)}</span></div>
        </div>
      </aside>

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

      <Toaster theme="dark" position="top-right"
        toastOptions={{ style: { background: "#18181b", border: "1px solid #27272a", color: "#f4f4f5" } }} />
    </div>
  );
}
