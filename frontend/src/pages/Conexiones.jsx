import { useMemo, useState } from "react";
import Layout from "../components/Layout";
import { helpForTab } from "../constants/help";
import { HubContext } from "../components/HubContext";
import { PlugsConnected, Key, Microphone, PhoneCall, Plugs, Sparkle } from "@phosphor-icons/react";
import ConnectorsPage from "./Connectors";
import ConfigPage     from "./Config";
import VoicesPage     from "./Voices";
import NumbersPage    from "./Numbers";
import McpConnectors  from "../components/McpConnectors";
import ConectarClaude from "../components/ConectarClaude";

// Orden pensado para alguien que entra por primera vez: primero lo que TODOS
// conectan, después lo de voz, y al final lo avanzado (casi nadie lo necesita).
const TABS = [
  { key: "conectores",   label: "Tus conexiones",    Icon: PlugsConnected, desc: "Aquí conectas WhatsApp, la voz y tus pedidos. Cada tarjeta te dice qué hacer, paso a paso." },
  { key: "claude",       label: "Asistentes de IA",  Icon: Sparkle,        desc: "Maneja tu negocio hablando con Claude, ChatGPT, Grok o Gemini. Se conecta con un enlace." },
  { key: "voces",        label: "Voces",             Icon: Microphone,     desc: "Elige la voz con la que hablan tus agentes cuando llaman." },
  { key: "numeros",      label: "Números",           Icon: PhoneCall,      desc: "Los números de teléfono desde los que llaman tus agentes." },
  { key: "credenciales", label: "Todas las llaves",  Icon: Key,            avanzado: true, desc: "La lista completa de llaves guardadas. Lo normal es conectar desde «Tus conexiones»; entra aquí solo para revisar o borrar una." },
  { key: "mcp",          label: "Herramientas extra", Icon: Plugs,         avanzado: true, desc: "Para usuarios avanzados: dale al asistente herramientas de otros sistemas." },
];

export default function ConexionesPage() {
  const initial = new URLSearchParams(window.location.search).get("tab") || "conectores";
  const [tab, setTab] = useState(TABS.find(t => t.key === initial) ? initial : "conectores");

  const current = useMemo(() => TABS.find(t => t.key === tab) || TABS[0], [tab]);
  const switchTab = (k) => {
    setTab(k);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", k);
    window.history.replaceState({}, "", url.toString());
  };

  return (
    <Layout title="Conexiones" subtitle={current.desc}>
      <div className="flex flex-wrap gap-1 border-b border-zinc-800 mb-6" data-testid="conexiones-tabs">
        {TABS.map(({ key, label, Icon, avanzado }) => (
          <button key={key} onClick={() => switchTab(key)}
            data-testid={`conexiones-tab-${key}`}
            className={`px-4 py-2.5 text-sm font-medium flex items-center gap-2 border-b-2 -mb-px transition ${
              tab === key
                ? "text-white border-white"
                : "text-zinc-400 border-transparent hover:text-white hover:border-zinc-600"
            }`}>
            <Icon size={16} weight="duotone" /> {label}
            {avanzado && <span className="text-[10px] uppercase tracking-wide text-zinc-400 border border-zinc-700 rounded-sm px-1">Avanzado</span>}
          </button>
        ))}
      </div>

      <HubContext.Provider value={helpForTab("conexiones", tab) || true}>
        {tab === "claude"       && <ConectarClaude />}
        {tab === "conectores"   && <ConnectorsPage />}
        {tab === "mcp"          && <McpConnectors />}
        {tab === "credenciales" && <ConfigPage />}
        {tab === "voces"        && <VoicesPage />}
        {tab === "numeros"      && <NumbersPage />}
      </HubContext.Provider>
    </Layout>
  );
}
