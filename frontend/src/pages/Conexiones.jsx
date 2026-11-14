import { useMemo, useState } from "react";
import Layout from "../components/Layout";
import { helpForTab } from "../constants/help";
import { HubContext } from "../components/HubContext";
import { PlugsConnected, Key, Microphone, PhoneCall, Plugs } from "@phosphor-icons/react";
import ConnectorsPage from "./Connectors";
import ConfigPage     from "./Config";
import VoicesPage     from "./Voices";
import NumbersPage    from "./Numbers";
import McpConnectors  from "../components/McpConnectors";

const TABS = [
  { key: "conectores",   label: "Conectores",   Icon: PlugsConnected, desc: "Mensajería, telefonía, voz y tu sistema de pedidos o citas, con guía paso a paso." },
  { key: "mcp",          label: "Conectores MCP", Icon: Plugs,        desc: "Dale herramientas nuevas al asistente conectando servidores MCP de confianza." },
  { key: "credenciales", label: "Credenciales", Icon: Key,            desc: "Tus llaves, cifradas. Solo tu empresa las usa." },
  { key: "voces",        label: "Voces",        Icon: Microphone,     desc: "La voz con la que hablan tus agentes." },
  { key: "numeros",      label: "Números",      Icon: PhoneCall,      desc: "Los números desde los que llaman tus agentes." },
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
        {TABS.map(({ key, label, Icon }) => (
          <button key={key} onClick={() => switchTab(key)}
            data-testid={`conexiones-tab-${key}`}
            className={`px-4 py-2.5 text-sm font-medium flex items-center gap-2 border-b-2 -mb-px transition ${
              tab === key
                ? "text-white border-white"
                : "text-zinc-400 border-transparent hover:text-white hover:border-zinc-600"
            }`}>
            <Icon size={16} weight="duotone" /> {label}
          </button>
        ))}
      </div>

      <HubContext.Provider value={helpForTab("conexiones", tab) || true}>
        {tab === "conectores"   && <ConnectorsPage />}
        {tab === "mcp"          && <McpConnectors />}
        {tab === "credenciales" && <ConfigPage />}
        {tab === "voces"        && <VoicesPage />}
        {tab === "numeros"      && <NumbersPage />}
      </HubContext.Provider>
    </Layout>
  );
}
