import { useMemo, useState } from "react";
import Layout from "../components/Layout";
import { HubContext } from "../components/HubContext";
import { Package, ChatText, ClockCountdown, Truck, Sparkle, UsersThree } from "@phosphor-icons/react";
import ProductsPage  from "./Products";
import PromptsPage   from "./Prompts";
import CadencePage   from "./Cadence";
import CarriersPage  from "./Carriers";
import SkillsPage    from "./Skills";
import VipLeadsPage  from "./VipLeads";

const TABS = [
  { key: "productos",      label: "Productos",       Icon: Package,        desc: "Catálogo con precios y promociones." },
  { key: "prompts",        label: "Prompts",         Icon: ChatText,       desc: "El guion de tu IA por país (antifluido · nunca 'impermeable')." },
  { key: "cadencia",       label: "Cadencia",        Icon: ClockCountdown, desc: "Cuántos intentos y en qué ventanas." },
  { key: "transportadoras",label: "Transportadoras", Icon: Truck,          desc: "Plazos de oficina por carrier." },
  { key: "habilidades",    label: "Habilidades",     Icon: Sparkle,        desc: "Skills adicionales del Copilot." },
  { key: "vip",            label: "Leads VIP",       Icon: UsersThree,     desc: "Bandeja de prospectos VIP." },
];

export default function AjustesPage() {
  const initial = new URLSearchParams(window.location.search).get("tab") || "productos";
  const [tab, setTab] = useState(TABS.find(t => t.key === initial) ? initial : "productos");
  const current = useMemo(() => TABS.find(t => t.key === tab) || TABS[0], [tab]);
  const switchTab = (k) => {
    setTab(k);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", k);
    window.history.replaceState({}, "", url.toString());
  };

  return (
    <Layout title="Ajustes" subtitle={current.desc}>
      <div className="flex flex-wrap gap-1 border-b border-zinc-800 mb-6" data-testid="ajustes-tabs">
        {TABS.map(({ key, label, Icon }) => (
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

      <HubContext.Provider value={true}>
        {tab === "productos"       && <ProductsPage />}
        {tab === "prompts"         && <PromptsPage />}
        {tab === "cadencia"        && <CadencePage />}
        {tab === "transportadoras" && <CarriersPage />}
        {tab === "habilidades"     && <SkillsPage />}
        {tab === "vip"             && <VipLeadsPage />}
      </HubContext.Provider>
    </Layout>
  );
}
