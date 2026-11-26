import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Package, PlugsConnected, ChartLineUp, Gear, House, Plus, TrashSimple,
  Envelope, WhatsappLogo, List, X, PhoneCall, Truck, UsersThree,
} from "@phosphor-icons/react";
import { api } from "../lib/api";
import LogoZynex from "./LogoZynex";
import { useAssistantName } from "../lib/assistant";
import { usePacks } from "../lib/packs";

const NAV = [
  { to: "/app",            label: "Lyan",       lyan: true,   testId: "nav-copilot",    exact: true,
    hint: "Pídele lo que necesites" },
  { to: "/app/logistica",  label: "Logística",  icon: Truck,          testId: "nav-logistica", grupo: "Logística",
    hint: "Pedidos · Seguimiento · Pendientes · Plantillas" },
  { to: "/app/clientes",   label: "Clientes",   icon: UsersThree,     testId: "nav-clientes",
    hint: "Fichas · Notas · Quién necesita ayuda" },
  { to: "/app/pedidos",    label: "Pendientes", icon: Package,        testId: "nav-pedidos",
    hint: "Cola · Tickets", hintCod: "Cola · Importar · Novedades · Tickets" },
  { to: "/app/llamadas",   label: "Llamadas",   icon: PhoneCall,      testId: "nav-llamadas", grupo: "Llamadas",
    hint: "Agentes de voz · Logística y otros usos" },
  { to: "/app/conexiones", label: "Conexiones", icon: PlugsConnected, testId: "nav-conexiones", grupo: "Tu cuenta",
    hint: "Claude · Chatea Pro · Voces · Números" },
  { to: "/app/metricas",   label: "Métricas",   icon: ChartLineUp,    testId: "nav-metricas",
    hint: "Resultados de tu operación" },
  { to: "/app/ajustes",    label: "Ajustes",    icon: Gear,           testId: "nav-ajustes",
    hint: "Perfil · Agentes · Productos · más" },
];

const THREADS_CHANGED = "zynex-threads-changed";

export function notifyThreadsChanged() {
  window.dispatchEvent(new Event(THREADS_CHANGED));
}

/** Botón de menú (solo en pantallas pequeñas) que abre el menú lateral. */
export function MenuButton({ onClick, className = "" }) {
  return (
    <button type="button" onClick={onClick} aria-label="Abrir menú" data-testid="mobile-menu-open"
            className={`md:hidden shrink-0 h-10 w-10 grid place-items-center rounded-sm border border-zinc-700 bg-zinc-900 text-zinc-200 hover:bg-zinc-800 ${className}`}>
      <List size={20} />
    </button>
  );
}

/**
 * Menú lateral. En escritorio (md+) es una columna fija. En celular es un
 * cajón: oculto por defecto, se abre con <MenuButton> (`open`) y se cierra al
 * tocar fuera, con la X, con Escape o al cambiar de pantalla (`onClose`).
 */
export default function Sidebar({ open = false, onClose }) {
  const location = useLocation();
  const navigate = useNavigate();
  const showChats = location.pathname === "/app";
  const asistente = useAssistantName();
  const { hasCod } = usePacks();
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

  // En celular el cajón se cierra al navegar y con Escape.
  useEffect(() => { onClose?.(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ },
            [location.pathname, location.search]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
    {open && (
      <div className="fixed inset-0 z-40 bg-black/60 md:hidden" onClick={onClose}
           data-testid="mobile-menu-backdrop" aria-hidden="true" />
    )}
    <aside data-testid="sidebar" data-open={open ? "true" : "false"}
           className={`w-64 max-w-[85vw] shrink-0 border-r border-zinc-800 bg-zinc-950 h-screen flex flex-col
             fixed inset-y-0 left-0 z-50 transform transition-transform duration-200
             ${open ? "translate-x-0" : "-translate-x-full"}
             md:sticky md:top-0 md:z-auto md:translate-x-0 md:transition-none`}>
      {/* brand */}
      <div className="px-5 py-6 border-b border-zinc-800 relative">
        <button type="button" onClick={onClose} aria-label="Cerrar menú" data-testid="mobile-menu-close"
                className="md:hidden absolute top-4 right-3 h-9 w-9 grid place-items-center rounded-sm text-zinc-400 hover:text-white hover:bg-zinc-800">
          <X size={18} />
        </button>
        <div className="text-white" style={{ "--estado": "var(--modulo, #19c8ff)", "--zx-fondo": "#09090b" }}><LogoZynex chico /></div>
        <h1 className="text-lg font-semibold text-white mt-1">Zynex OS</h1>
        <p className="text-[11px] font-mono text-zinc-500 mt-1">Agentes para tu negocio</p>
      </div>

      {/* nav — 5 top-level */}
      <nav className="py-3">
        {NAV.map(({ to, label, icon: Icon, lyan, testId, exact, hint, hintCod, grupo }) => (
          <div key={to}>
          {grupo && <div className="px-5 pt-3 pb-1 text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-400" data-testid={`nav-grupo-${grupo}`}>{grupo}</div>}
          <NavLink
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
                <img src="/lyan.webp" alt={asistente}
                     className="w-6 h-6 rounded-full object-cover ring-1 ring-cyan-400/40"
                     data-testid="sidebar-lyan-avatar" />
              ) : (
                <Icon size={18} weight="duotone" />
              )}
              <span className="text-sm font-medium">{lyan ? asistente : label}</span>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mt-0.5 ml-9">
              {hasCod && hintCod ? hintCod : hint}
            </div>
          </NavLink>
          </div>
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
        <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500">Soporte · tu asesora Sofía</div>
        <a href="mailto:zynexproai@gmail.com"
           className="flex items-center gap-1.5 min-h-[24px] hover:text-white transition"
           data-testid="support-email">
          <Envelope size={11} weight="fill" /> zynexproai@gmail.com
        </a>
        <a href="https://wa.me/573144644054" target="_blank" rel="noreferrer"
           className="flex items-center gap-1.5 min-h-[24px] hover:text-white transition"
           data-testid="support-whatsapp">
          <WhatsappLogo size={11} weight="fill" className="text-emerald-400" /> Escríbele a Sofía · 314 464 4054
        </a>
      </div>
    </aside>
    </>
  );
}
