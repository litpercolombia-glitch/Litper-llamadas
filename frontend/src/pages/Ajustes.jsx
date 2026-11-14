import { useMemo, useState } from "react";
import Layout from "../components/Layout";
import { helpForTab } from "../constants/help";
import { HubContext } from "../components/HubContext";
import { UserCircle, Robot, PhoneCall, Package, ChatText, ClockCountdown, Truck, Sparkle, UsersThree } from "@phosphor-icons/react";
import PerfilPage    from "./Perfil";
import AgentesPage   from "./Agentes";
import LlamadasPage  from "./Llamadas";
import ProductsPage  from "./Products";
import PromptsPage   from "./Prompts";
import CadencePage   from "./Cadence";
import CarriersPage  from "./Carriers";
import SkillsPage    from "./Skills";
import VipLeadsPage  from "./VipLeads";
import PackNotice    from "../components/PackNotice";
import { usePacks }  from "../lib/packs";

const TABS = [
  { key: "perfil",         label: "Perfil",          Icon: UserCircle,     desc: "Tu cuenta y el perfil de tu negocio." },
  { key: "agentes",        label: "Agentes",         Icon: Robot,          desc: "Crea un agente describiendo tu negocio en una frase." },
  { key: "llamadas",       label: "Llamadas",        Icon: PhoneCall,      desc: "Historial de llamadas con grabación y conversación escrita." },
  { key: "productos",      label: "Productos",       Icon: Package,        desc: "Catálogo con precios y promociones." },
  { key: "prompts",        label: "Guiones",         Icon: ChatText,       desc: "Lo que dicen tus agentes y cómo lo dicen." },
  { key: "cadencia",       label: "Cadencia",        Icon: ClockCountdown, desc: "Plan de intentos de contacto por pedido.", pack: "cod_colombia" },
  { key: "transportadoras",label: "Transportadoras", Icon: Truck,          desc: "Empresas de envío y sus plazos.", pack: "cod_colombia" },
  { key: "habilidades",    label: "Habilidades",     Icon: Sparkle,        desc: "Instrucciones guardadas que el asistente puede repetir." },
  { key: "vip",            label: "Clientes VIP",    Icon: UsersThree,     desc: "Interesados que merecen atención prioritaria.", pack: "cod_colombia" },
];

export default function AjustesPage() {
  const initial = new URLSearchParams(window.location.search).get("tab") || "perfil";
  const [tab, setTab] = useState(TABS.find(t => t.key === initial) ? initial : "perfil");
  const { loaded, has } = usePacks();
  // Las pestañas de un paquete solo aparecen si el paquete está instalado.
  const tabs = TABS.filter((t) => !t.pack || has(t.pack));
  const current = useMemo(() => TABS.find(t => t.key === tab) || TABS[0], [tab]);
  const blocked = !!current.pack && !has(current.pack);
  const switchTab = (k) => {
    setTab(k);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", k);
    window.history.replaceState({}, "", url.toString());
  };

  return (
    <Layout title="Ajustes" subtitle={current.desc}>
      <div className="flex flex-wrap gap-1 border-b border-zinc-800 mb-6" data-testid="ajustes-tabs">
        {tabs.map(({ key, label, Icon }) => (
          <button key={key} onClick={() => switchTab(key)}
            data-testid={`ajustes-tab-${key}`}
            className={`px-4 py-2.5 text-sm font-medium flex items-center gap-2 border-b-2 -mb-px transition ${
              tab === key
                ? "text-white border-white"
                : "text-zinc-400 border-transparent hover:text-white hover:border-zinc-600"
            }`}>
            <Icon size={16} weight="duotone" /> {label}
          </button>
        ))}
      </div>

      <HubContext.Provider value={helpForTab("ajustes", tab) || true}>
        {tab === "perfil"          && <PerfilPage />}
        {tab === "agentes"         && <AgentesPage />}
        {tab === "llamadas"        && <LlamadasPage />}
        {tab === "productos"       && <ProductsPage />}
        {tab === "prompts"         && <PromptsPage />}
        {tab === "cadencia"        && !blocked && <CadencePage />}
        {tab === "transportadoras" && !blocked && <CarriersPage />}
        {blocked && loaded && <PackNotice />}
        {tab === "habilidades"     && <SkillsPage />}
        {tab === "vip"             && !blocked && <VipLeadsPage />}
      </HubContext.Provider>
    </Layout>
  );
}
