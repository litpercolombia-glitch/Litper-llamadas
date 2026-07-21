import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Sidebar from "../components/Sidebar";
import { api } from "../lib/api";
import { Toaster, toast } from "sonner";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import {
  Robot, PaperPlaneRight, Plus, TrashSimple, Wrench,
  CheckCircle, WarningCircle, User, Lightning, Sparkle
} from "@phosphor-icons/react";

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
        <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1">
          {isUser ? "Tú" : "Marcus"}
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
          className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm h-9">
          <Plus size={14} className="mr-1" /> Nuevo chat
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
  const [threads, setThreads] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [skills, setSkills] = useState([]);
  const [skillId, setSkillId] = useState("none");
  const [autoMode, setAutoMode] = useState(false);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const scrollRef = useRef(null);

  const loadThreads = async () => {
    const r = await api.get("/threads");
    setThreads(r.data || []);
  };
  const loadSkills = async () => {
    const r = await api.get("/skills");
    setSkills(r.data || []);
  };
  const loadMessages = async (tid) => {
    if (!tid) { setMessages([]); return; }
    const r = await api.get(`/threads/${tid}/messages`);
    setMessages(r.data || []);
  };

  useEffect(() => {
    loadThreads();
    loadSkills();
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

  const activeSkill = skills.find(s => s.id === skillId);

  return (
    <div className="min-h-screen flex bg-zinc-950 text-zinc-100">
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
            </div>
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-8">
          <div className="max-w-3xl mx-auto py-6">
            {messages.length === 0 && !running && (
              <div className="py-16 text-center">
                <div className="w-14 h-14 mx-auto mb-4 rounded-sm bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                  <Robot size={28} className="text-white" weight="duotone" />
                </div>
                <h1 className="text-2xl font-semibold text-white mb-2">¿En qué te ayudo hoy?</h1>
                <p className="text-sm text-zinc-400 mb-8">Puedo consultar la cola, programar cadencias, enviar WhatsApp y crear tickets — usando datos reales del Hub.</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-left max-w-xl mx-auto">
                  {skills.map(s => (
                    <button key={s.id} onClick={() => applySkill(s)}
                      data-testid={`copilot-skill-quick-${s.trigger}`}
                      className="border border-zinc-800 hover:border-zinc-600 bg-zinc-900/50 hover:bg-zinc-900 p-4 rounded-sm text-left transition group">
                      <div className="text-sm font-medium text-white mb-1 flex items-center gap-2">
                        <Sparkle size={13} className="text-zinc-500 group-hover:text-white" />
                        {s.name}
                      </div>
                      <div className="text-xs text-zinc-500 line-clamp-2">{s.description}</div>
                    </button>
                  ))}
                </div>
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
                  className="bg-white text-black hover:bg-zinc-200 rounded-sm h-8">
                  <PaperPlaneRight size={13} className="mr-1" /> Enviar
                </Button>
              </div>
            </div>
          </div>
        </footer>
      </div>
      <Toaster theme="dark" position="top-right"
        toastOptions={{ style: { background: "#18181b", border: "1px solid #27272a", color: "#f4f4f5" } }} />
    </div>
  );
}
