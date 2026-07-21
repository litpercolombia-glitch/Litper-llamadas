import { NavLink } from "react-router-dom";
import {
  ChartBar, Queue, ClockCountdown, ChatCircleDots, ListChecks,
  Plugs, Truck, House, Microphone, PhoneCall, Warning, Robot, Sparkle,
  FileXls, Package, UsersThree, ChatText,
} from "@phosphor-icons/react";

const NAV = [
  { to: "/app",            label: "Copilot",       icon: Robot,           testId: "sidebar-nav-copilot", exact: true },
  { to: "/app/skills",     label: "Habilidades",   icon: Sparkle,         testId: "sidebar-nav-skills" },
  { to: "/app/metrics",    label: "Métricas",      icon: ChartBar,        testId: "sidebar-nav-metrics" },
  { to: "/app/queue",      label: "Cola",          icon: Queue,           testId: "sidebar-nav-queue" },
  { to: "/app/import",     label: "Importar",      icon: FileXls,         testId: "sidebar-nav-import" },
  { to: "/app/products",   label: "Productos",     icon: Package,         testId: "sidebar-nav-products" },
  { to: "/app/prompts",    label: "Prompts",       icon: ChatText,        testId: "sidebar-nav-prompts" },
  { to: "/app/cadence",    label: "Cadencia",      icon: ClockCountdown,  testId: "sidebar-nav-cadence" },
  { to: "/app/tasks",      label: "Tickets",       icon: ListChecks,      testId: "sidebar-nav-tasks" },
  { to: "/app/messages",   label: "Mensajes",      icon: ChatCircleDots,  testId: "sidebar-nav-messages" },
  { to: "/app/voices",     label: "Voces",         icon: Microphone,      testId: "sidebar-nav-voices" },
  { to: "/app/numbers",    label: "Números",       icon: PhoneCall,       testId: "sidebar-nav-numbers" },
  { to: "/app/carriers",   label: "Transportadoras", icon: Truck,         testId: "sidebar-nav-carriers" },
  { to: "/app/novedades",  label: "Novedades",     icon: Warning,         testId: "sidebar-nav-novedades" },
  { to: "/app/vip-leads",  label: "Leads VIP",     icon: UsersThree,      testId: "sidebar-nav-vip" },
  { to: "/app/connectors", label: "Conexiones",    icon: Plugs,           testId: "sidebar-nav-connectors" },
];

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-zinc-800 bg-zinc-950 h-screen sticky top-0 flex flex-col">
      <div className="px-5 py-6 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md neon-glow grid place-items-center bg-gradient-to-br from-white/25 to-white/5 border border-white/25">
            <House size={14} weight="fill" className="text-white" />
          </div>
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-zinc-500">Litper</span>
        </div>
        <h1 className="text-lg font-semibold text-white mt-1">Connect Hub</h1>
        <p className="text-[11px] font-mono text-zinc-500 mt-1">COD · LATAM · v1.2</p>
      </div>

      <div className="px-5 pt-4 pb-1 text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500">
        Navegación
      </div>
      <nav className="flex-1 py-1 overflow-y-auto">
        {NAV.map(({ to, label, icon: Icon, testId, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            data-testid={testId}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors duration-150 border-l-2 ${
                isActive
                  ? "bg-zinc-800 text-white border-white active-nav"
                  : "text-zinc-400 border-transparent hover:text-white hover:bg-zinc-800/50"
              }`
            }
          >
            <Icon size={18} weight="duotone" />
            <span>{label}</span>
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
