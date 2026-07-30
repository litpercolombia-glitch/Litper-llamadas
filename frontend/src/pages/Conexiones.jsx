import { useMemo, useState } from "react";
import Layout from "../components/Layout";
import HowItWorks from "../components/HowItWorks";
import { HubContext } from "../components/HubContext";
import { PlugsConnected, Key, Microphone, PhoneCall } from "@phosphor-icons/react";
import ConnectorsPage from "./Connectors";
import ConfigPage     from "./Config";
import VoicesPage     from "./Voices";
import NumbersPage    from "./Numbers";

const TABS = [
  { key: "conectores",   label: "Conectores",   Icon: PlugsConnected, desc: "Dropi · Chatea Pro · ElevenLabs · Telnyx — con guía paso a paso." },
  { key: "credenciales", label: "Credenciales", Icon: Key,            desc: "BYOK · tus llaves cifradas y solo tú las ves." },
  { key: "voces",        label: "Voces",        Icon: Microphone,     desc: "Voz de tu operadora IA por país." },
  { key: "numeros",      label: "Números",      Icon: PhoneCall,      desc: "Caller IDs verificados." },
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
      <HowItWorks
        testIdPrefix="conexiones-howitworks"
        intro="Zynex es BYOK (Bring Your Own Keys): tú pegas tus tokens, nosotros los ciframos y solo tú los ves. Pagas solo lo que uses en tu proveedor."
        steps={[
          "Elige un conector (Dropi, Chatea Pro, Telnyx, ElevenLabs, Shopify).",
          "Sigue el paso a paso — cada tarjeta abre un instructivo corto.",
          "Pega los tokens en los campos y dale Probar conexión.",
          "Verde = listo. Rojo = revisa el token o los permisos.",
        ]}
        links={[
          { href: "https://chateapro.app/settings#/api", label: "Chatea Pro · API", external: true },
          { href: "https://portal.telnyx.com", label: "Telnyx · Portal", external: true },
          { href: "https://elevenlabs.io/app/settings/api-keys", label: "ElevenLabs · Keys", external: true },
        ]}
      />
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

      <HubContext.Provider value={true}>
        {tab === "conectores"   && <ConnectorsPage />}
        {tab === "credenciales" && <ConfigPage />}
        {tab === "voces"        && <VoicesPage />}
        {tab === "numeros"      && <NumbersPage />}
      </HubContext.Provider>
    </Layout>
  );
}
