import { NavLink } from "react-router-dom";
import {
  Robot, Package, PlugsConnected, ChartLineUp, Gear, House,
} from "@phosphor-icons/react";

// Only 5 top-level items. Everything else lives inside these hubs.
const NAV = [
  { to: "/app",            label: "Copilot",    icon: Robot,          testId: "nav-copilot",    exact: true,
    hint: "Chat con tus 5 agentes" },
  { to: "/app/pedidos",    label: "Pedidos",    icon: Package,        testId: "nav-pedidos",
    hint: "Cola · Importar · Novedades · Tickets" },
  { to: "/app/conexiones", label: "Conexiones", icon: PlugsConnected, testId: "nav-conexiones",
    hint: "Credenciales · Voces · Números" },
  { to: "/app/metricas",   label: "Métricas",   icon: ChartLineUp,    testId: "nav-metricas",
    hint: "$ recuperado y entrega efectiva" },
  { to: "/app/ajustes",    label: "Ajustes",    icon: Gear,           testId: "nav-ajustes",
    hint: "Configuración avanzada" },
];

export default function Sidebar() {
  return (
    <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-950 h-screen sticky top-0 flex flex-col">
      <div className="px-5 py-6 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md neon-glow grid place-items-center bg-gradient-to-br from-white/25 to-white/5 border border-white/25">
            <House size={14} weight="fill" className="text-white" />
          </div>
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-zinc-500">Zynex</span>
        </div>
        <h1 className="text-lg font-semibold text-white mt-1">Litper OS</h1>
        <p className="text-[11px] font-mono text-zinc-500 mt-1">COD · LATAM · v2.3</p>
      </div>

      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV.map(({ to, label, icon: Icon, testId, exact, hint }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            data-testid={testId}
            className={({ isActive }) =>
              `block px-5 py-3 border-l-2 transition-colors duration-150 ${
                isActive
                  ? "bg-zinc-800 text-white border-white active-nav"
                  : "text-zinc-400 border-transparent hover:text-white hover:bg-zinc-800/50"
              }`
            }
          >
            <div className="flex items-center gap-3">
              <Icon size={20} weight="duotone" />
              <span className="text-sm font-medium">{label}</span>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mt-0.5 ml-8">
              {hint}
            </div>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-zinc-800 px-5 py-4">
        <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono mb-1">Región</div>
        <div className="text-sm text-zinc-300">Colombia · Ecuador · Chile</div>
      </div>
    </aside>
  );
}
