import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Package, PlugsConnected, ChartLineUp, Gear, House, Plus, TrashSimple,
  Envelope, WhatsappLogo,
} from "@phosphor-icons/react";
import { api } from "../lib/api";

const NAV = [
  { to: "/app",            label: "Lyan",       lyan: true,   testId: "nav-copilot",    exact: true,
    hint: "Chat con tus 5 agentes" },
  { to: "/app/pedidos",    label: "Pedidos",    icon: Package,        testId: "nav-pedidos",
    hint: "Cola · Importar · Novedades · Tickets" },
  { to: "/app/conexiones", label: "Conexiones", icon: PlugsConnected, testId: "nav-conexiones",
    hint: "Credenciales · Voces · Números" },
  { to: "/app/metricas",   label: "Métricas",   icon: ChartLineUp,    testId: "nav-metricas",
    hint: "$ recuperado y entrega efectiva" },
  { to: "/app/ajustes",    label: "Ajustes",    icon: Gear,           testId: "nav-ajustes",
    hint: "Perfil · Agentes · Productos · más" },
];

const THREADS_CHANGED = "zynex-threads-changed";

export function notifyThreadsChanged() {
  window.dispatchEvent(new Event(THREADS_CHANGED));
}

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const showChats = location.pathname === "/app";
  const [threads, setThreads] = useState([]);
  const activeId = new URLSearchParams(location.search).get("thread");

  const loadThreads = async () => {
    try {
      const r = await api.get("/threads");
      setThreads(r.data || []);
    } catch { setThreads([]); }
  };
  useEffect(() => {
    if (showChats) loadThreads();
    const on = () => showChats && loadThreads();
    window.addEventListener(THREADS_CHANGED, on);
    return () => window.removeEventListener(THREADS_CHANGED, on);
  }, [showChats]);

  const newThread = async () => {
    try {
      const r = await api.post("/threads", {});
      navigate(`/app?thread=${r.data.id}`);
      await loadThreads();
    } catch {}
  };
  const selectThread = (id) => navigate(`/app?thread=${id}`);
  const deleteThread = async (id, e) => {
    e?.stopPropagation?.();
    if (!window.confirm("¿Borrar esta conversación?")) return;
    try {
      await api.delete(`/threads/${id}`);
      if (activeId === id) navigate("/app");
      await loadThreads();
    } catch {}
  };

  return (
    <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-950 h-screen sticky top-0 flex flex-col">
      {/* brand */}
      <div className="px-5 py-6 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md neon-glow grid place-items-center bg-gradient-to-br from-white/25 to-white/5 border border-white/25">
            <House size={14} weight="fill" className="text-white" />
          </div>
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-zinc-500">Zynex</span>
        </div>
        <h1 className="text-lg font-semibold text-white mt-1">Litper OS</h1>
        <p className="text-[11px] font-mono text-zinc-500 mt-1">COD · LATAM · v2.6</p>
      </div>

      {/* nav — 5 top-level */}
      <nav className="py-3">
        {NAV.map(({ to, label, icon: Icon, lyan, testId, exact, hint }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            data-testid={testId}
            className={({ isActive }) =>
              `block px-5 py-2.5 border-l-2 transition-colors duration-150 ${
                isActive
                  ? "bg-zinc-800 text-white border-white active-nav"
                  : "text-zinc-400 border-transparent hover:text-white hover:bg-zinc-800/50"
              }`
            }
          >
            <div className="flex items-center gap-3">
              {lyan ? (
                <img src="/lyan.webp" alt="Lyan"
                     className="w-6 h-6 rounded-full object-cover ring-1 ring-cyan-400/40"
                     data-testid="sidebar-lyan-avatar" />
              ) : (
                <Icon size={18} weight="duotone" />
              )}
              <span className="text-sm font-medium">{label}</span>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mt-0.5 ml-9">
              {hint}
            </div>
          </NavLink>
        ))}
      </nav>

      {/* Chats (Claude-style) — only on /app */}
      {showChats && (
        <div className="flex-1 flex flex-col min-h-0 border-t border-zinc-800"
             data-testid="sidebar-chats">
          <div className="px-4 pt-3 pb-2">
            <button
              onClick={newThread}
              data-testid="sidebar-new-chat"
              className="w-full btn-cta-grad rounded-sm h-9 text-sm font-medium text-white inline-flex items-center justify-center gap-1">
              <Plus size={14} /> Nueva conversación
            </button>
          </div>
          <div className="px-5 pb-1 pt-2 text-[10px] uppercase tracking-widest font-mono text-zinc-500">
            Conversaciones · {threads.length}
          </div>
          <div className="flex-1 overflow-y-auto">
            {threads.length === 0 && (
              <div className="px-5 py-6 text-xs text-zinc-500 text-center font-mono">
                Sin conversaciones aún.
              </div>
            )}
            {threads.map((t) => (
              <div key={t.id}
                onClick={() => selectThread(t.id)}
                data-testid={`sidebar-thread-${t.id}`}
                className={`group px-5 py-2 border-l-2 cursor-pointer transition-colors flex items-center gap-2 ${
                  activeId === t.id
                    ? "bg-zinc-800/60 border-white"
                    : "border-transparent hover:bg-zinc-800/30 hover:border-zinc-600"
                }`}>
                <span className="text-sm text-zinc-200 truncate flex-1">{t.title || "Sin título"}</span>
                <button onClick={(e) => deleteThread(t.id, e)}
                  className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 transition"
                  aria-label="Borrar conversación">
                  <TrashSimple size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filler on non-chat pages so the footer sticks to the bottom */}
      {!showChats && <div className="flex-1" />}

      {/* Support footer — visible on every page */}
      <div className="border-t border-zinc-800 px-5 py-3 text-[11px] text-zinc-400 space-y-1"
           data-testid="sidebar-support">
        <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500">Soporte</div>
        <a href="mailto:zynexproai@gmail.com"
           className="flex items-center gap-1.5 hover:text-white transition"
           data-testid="support-email">
          <Envelope size={11} weight="fill" /> zynexproai@gmail.com
        </a>
        <a href="https://wa.me/573144754115" target="_blank" rel="noreferrer"
           className="flex items-center gap-1.5 hover:text-white transition"
           data-testid="support-whatsapp">
          <WhatsappLogo size={11} weight="fill" className="text-emerald-400" /> WhatsApp 3144754115
        </a>
      </div>
    </aside>
  );
}
