import { useMemo, useState } from "react";
import Layout from "../components/Layout";
import { HubContext } from "../components/HubContext";
import { Package, FileXls, Warning, ListChecks } from "@phosphor-icons/react";
import QueuePage    from "./Queue";
import ImportPage   from "./Import";
import NovedadesPage from "./Novedades";
import TasksPage    from "./Tasks";

const TABS = [
  { key: "cola",       label: "Cola",       Icon: Package,     desc: "Todos tus pedidos con semáforo por urgencia." },
  { key: "importar",   label: "Importar",   Icon: FileXls,     desc: "Sube el Excel de Dropi (combo-safe)." },
  { key: "novedades",  label: "Novedades",  Icon: Warning,     desc: "Estatus por transportadora." },
  { key: "tickets",    label: "Tickets",    Icon: ListChecks,  desc: "Casos abiertos con clientes." },
];

export default function PedidosPage() {
  const initial = new URLSearchParams(window.location.search).get("tab") || "cola";
  const [tab, setTab] = useState(TABS.find(t => t.key === initial) ? initial : "cola");

  const current = useMemo(() => TABS.find(t => t.key === tab) || TABS[0], [tab]);

  const switchTab = (k) => {
    setTab(k);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", k);
    window.history.replaceState({}, "", url.toString());
  };

  return (
    <Layout title="Pedidos" subtitle={current.desc}>
      <div className="flex flex-wrap gap-1 border-b border-zinc-800 mb-6" data-testid="pedidos-tabs">
        {TABS.map(({ key, label, Icon }) => (
          <button key={key} onClick={() => switchTab(key)}
            data-testid={`pedidos-tab-${key}`}
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
        {tab === "cola"      && <QueuePage />}
        {tab === "importar"  && <ImportPage />}
        {tab === "novedades" && <NovedadesPage />}
        {tab === "tickets"   && <TasksPage />}
      </HubContext.Provider>
    </Layout>
  );
}
