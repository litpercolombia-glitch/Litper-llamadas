import { NavLink } from "react-router-dom";
import {
  ChartBar, Queue, ClockCountdown, ChatCircleDots, ListChecks,
  Plugs, Truck, House, Microphone, PhoneCall, Warning, Robot, Sparkle,
  FileXls,
} from "@phosphor-icons/react";

const NAV = [
  { to: "/",           label: "Copilot",    icon: Robot,           testId: "sidebar-nav-copilot" },
  { to: "/skills",     label: "Habilidades", icon: Sparkle,        testId: "sidebar-nav-skills" },
  { to: "/metrics",    label: "Métricas",   icon: ChartBar,        testId: "sidebar-nav-metrics" },
  { to: "/queue",      label: "Cola",       icon: Queue,           testId: "sidebar-nav-queue" },
  { to: "/import",     label: "Importar",   icon: FileXls,         testId: "sidebar-nav-import" },
  { to: "/cadence",    label: "Cadencia",   icon: ClockCountdown,  testId: "sidebar-nav-cadence" },
  { to: "/tasks",      label: "Tickets",    icon: ListChecks,      testId: "sidebar-nav-tasks" },
  { to: "/messages",   label: "Mensajes",   icon: ChatCircleDots,  testId: "sidebar-nav-messages" },
  { to: "/voices",     label: "Voces",      icon: Microphone,      testId: "sidebar-nav-voices" },
  { to: "/numbers",    label: "Números",    icon: PhoneCall,       testId: "sidebar-nav-numbers" },
  { to: "/carriers",   label: "Transportadoras", icon: Truck,      testId: "sidebar-nav-carriers" },
  { to: "/novedades",  label: "Novedades",  icon: Warning,         testId: "sidebar-nav-novedades" },
  { to: "/connectors", label: "Conectores", icon: Plugs,           testId: "sidebar-nav-connectors" },
];

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-zinc-800 bg-zinc-950 h-screen sticky top-0 flex flex-col">
      <div className="px-5 py-6 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <House size={20} weight="duotone" className="text-white" />
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-zinc-500">Litper</span>
        </div>
        <h1 className="text-lg font-semibold text-white mt-1">Connect Hub</h1>
        <p className="text-[11px] font-mono text-zinc-500 mt-1">COD · LATAM · v1.1</p>
      </div>

      <nav className="flex-1 py-3">
        {NAV.map(({ to, label, icon: Icon, testId }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            data-testid={testId}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors duration-150 border-l-2 ${
                isActive
                  ? "bg-zinc-800 text-white border-white"
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
