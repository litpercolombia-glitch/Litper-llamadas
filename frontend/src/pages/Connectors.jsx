import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  PlugsConnected, Plugs, WarningCircle, CheckCircle, CaretDown,
  ArrowSquareOut, Copy, WhatsappLogo, Robot, PhoneCall, Cloud,
  ShoppingBag, Sparkle,
} from "@phosphor-icons/react";
import { toast } from "sonner";

const STATUS_STYLES = {
  connected:    { cls: "text-green-400 border-green-500/30 bg-green-500/5",   Icon: CheckCircle,   label: "Conectado" },
  sip_registered: { cls: "text-green-400 border-green-500/30 bg-green-500/5", Icon: CheckCircle,   label: "SIP registrado" },
  error:        { cls: "text-red-400 border-red-500/30 bg-red-500/5",         Icon: WarningCircle, label: "Error" },
  unconfigured: { cls: "text-zinc-400 border-zinc-700 bg-zinc-900/50",        Icon: Plugs,         label: "Sin configurar" },
  disconnected: { cls: "text-zinc-400 border-zinc-700 bg-zinc-900/50",        Icon: Plugs,         label: "Desconectado" },
};

// -----------------------------------------------------------------------
// Connector cards (front-end catalog with real endpoints wired).
// -----------------------------------------------------------------------
const CATALOG = [
  {
    key: "chatea_pro", label: "Chatea Pro · WhatsApp", Icon: WhatsappLogo,
    testEndpoint: "/connectors/chatea_pro/test",
    envVars: ["CHATEA_PRO_API_KEY", "CHATEA_PRO_BASE_URL"],
    docUrl: "https://chateapro.app/",
    howto: [
      "Entra a chateapro.app → Configuración → API tokens y crea uno.",
      "Copia el token y pégalo en backend/.env como CHATEA_PRO_API_KEY.",
      "Reinicia el backend (sudo supervisorctl restart backend).",
      "Toca 'Probar' — deberías ver tu workspace_name.",
    ],
  },
  {
    key: "telnyx", label: "Telnyx · SIP trunk (Primario)", Icon: PhoneCall,
    testEndpoint: "/numbers/telnyx/register",
    envVars: ["TELNYX_API_KEY", "TELNYX_CONNECTION_ID",
              "TELNYX_PHONE_NUMBER", "TELNYX_SIP_USERNAME",
              "TELNYX_SIP_PASSWORD", "TELNYX_SIP_DOMAIN"],
    docUrl: "https://portal.telnyx.com/#/app/api-keys",
    configEndpoint: "/numbers/telnyx/config",
    howto: [
      "Portal Telnyx → API Keys · crea una V2 → copia el api_key en TELNYX_API_KEY.",
      "SIP Connections · crea una tipo 'Credentials' → guarda TELNYX_CONNECTION_ID + username/password en .env.",
      "Numbers · Buy number en tu país → E.164 en TELNYX_PHONE_NUMBER.",
      "Reinicia backend y haz clic en 'Registrar en ElevenLabs'.",
    ],
    testLabel: "Registrar en ElevenLabs",
    isPost: true,
  },
  {
    key: "elevenlabs", label: "ElevenLabs · Voz IA", Icon: Robot,
    testEndpoint: "/connectors/elevenlabs/test",
    envVars: ["ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID"],
    docUrl: "https://elevenlabs.io/app/settings/api-keys",
    howto: [
      "elevenlabs.io → Settings → API Keys → New Key (con permisos convai + tts).",
      "Guarda en ELEVENLABS_API_KEY.",
      "Crea un Agent en ConvAI y guarda su ID en ELEVENLABS_AGENT_ID.",
      "Toca 'Probar' — verás cuántas voces trae tu cuenta.",
    ],
  },
  {
    key: "twilio", label: "Twilio · Verificación Caller ID (Secundario)", Icon: PhoneCall,
    testEndpoint: "/connectors/twilio/test",
    envVars: ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
    docUrl: "https://console.twilio.com/",
    howto: [
      "twilio.com → Console → API keys & tokens.",
      "Copia el ACCOUNT_SID + AUTH_TOKEN en backend/.env.",
      "Toca 'Probar' — verás la lista de tus Caller IDs verificados.",
    ],
  },
  {
    key: "supabase", label: "Supabase · Postgres externo", Icon: Cloud,
    testEndpoint: "/connectors/supabase/test",
    envVars: ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY"],
    docUrl: "https://supabase.com/dashboard",
    howto: [
      "supabase.com → tu proyecto → Settings → API.",
      "Copia URL, anon key y service_role en las tres variables de .env.",
      "El sync automático publica órdenes/queue a tu Postgres externo.",
    ],
  },
  {
    key: "dropi", label: "Dropi · Fuente de pedidos", Icon: ShoppingBag,
    envVars: [],
    docUrl: "https://dropi.co/",
    howto: [
      "Litper importa desde el export XLSX de Dropi (Reclamos en Oficina).",
      "En Litper → Importar → arrastra el archivo (.xlsx/.xls/.csv).",
      "El importador agrupa combos por ID y toma el recaudo una sola vez.",
    ],
    // no testEndpoint — file-based
  },
  {
    key: "groq", label: "Groq · LLM primario", Icon: Sparkle,
    testEndpoint: "/llm/ping/groq", envVars: ["GROQ_API_KEY"],
    docUrl: "https://console.groq.com/keys",
    howto: [
      "console.groq.com → API Keys → Create.",
      "Pégala en GROQ_API_KEY en backend/.env.",
      "Reinicia y prueba desde Copilot (chat).",
    ],
  },
  {
    key: "gemini", label: "Gemini · Análisis largos", Icon: Sparkle,
    testEndpoint: "/llm/ping/gemini", envVars: ["GEMINI_API_KEY"],
    docUrl: "https://aistudio.google.com/apikey",
    howto: [
      "aistudio.google.com → Get API Key → Create.",
      "Pégala en GEMINI_API_KEY en backend/.env.",
    ],
  },
  {
    key: "claude", label: "Claude · Redacción", Icon: Sparkle,
    testEndpoint: "/llm/ping/claude", envVars: ["EMERGENT_LLM_KEY"],
    docUrl: "https://console.anthropic.com/",
    howto: [
      "Litper usa la Universal Emergent LLM Key para Claude (ya configurada por defecto).",
      "Si quieres tu propia key, define ANTHROPIC_API_KEY en .env.",
    ],
  },
  {
    key: "mistral", label: "Mistral · Alternativa", Icon: Sparkle,
    testEndpoint: "/llm/ping/mistral", envVars: ["MISTRAL_API_KEY"],
    docUrl: "https://console.mistral.ai/api-keys/",
    howto: [
      "console.mistral.ai → API Keys → Create.",
      "Pégala en MISTRAL_API_KEY en backend/.env.",
    ],
  },
  {
    key: "cerebras", label: "Cerebras · Alta velocidad", Icon: Sparkle,
    testEndpoint: "/llm/ping/cerebras", envVars: ["CEREBRAS_API_KEY"],
    docUrl: "https://cloud.cerebras.ai/",
    howto: [
      "cloud.cerebras.ai → API Keys → Create.",
      "Pégala en CEREBRAS_API_KEY en backend/.env.",
    ],
  },
];

export default function ConnectorsPage() {
  const [conns, setConns] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [testing, setTesting] = useState({});
  const [telnyxCfg, setTelnyxCfg] = useState(null);

  const load = async () => {
    const r = await api.get("/connectors");
    setConns(r.data || []);
    api.get("/numbers/telnyx/config").then(res => setTelnyxCfg(res.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const statusFor = (key) => {
    const c = conns.find((x) => x.key === key);
    return c || { status: "unconfigured" };
  };

  const testConnector = async (spec) => {
    if (!spec.testEndpoint) {
      toast.info("Conector basado en archivo. Ve a /import para probar.");
      return;
    }
    setTesting((t) => ({ ...t, [spec.key]: true }));
    try {
      const r = spec.isPost
        ? await api.post(spec.testEndpoint, {})
        : await api.post(spec.testEndpoint);
      if (r.data?.ok || r.data?.status === "connected" || r.data?.elevenlabs_phone_number_id) {
        toast.success(`${spec.label}: OK`);
      } else {
        toast.error(`${spec.label}: ${r.data?.error || `HTTP ${r.data?.status_code || r.data?.status}`}`);
      }
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally {
      setTesting((t) => ({ ...t, [spec.key]: false }));
    }
  };

  return (
    <Layout title="Conexiones"
            subtitle="Cada conector con instrucciones paso a paso · en español · variables de .env">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {CATALOG.map((spec) => {
          const c = statusFor(spec.key);
          const st = STATUS_STYLES[c.status] || STATUS_STYLES.unconfigured;
          const StatusIcon = st.Icon;
          const isExp = expanded === spec.key;
          const ProviderIcon = spec.Icon;
          return (
            <div key={spec.key}
                 className="rounded-lg border border-zinc-800 bg-zinc-900/40 backdrop-blur-md overflow-hidden"
                 data-testid={`connector-card-${spec.key}`}>
              <div className="p-4 flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-zinc-800 border border-zinc-700 grid place-items-center shrink-0">
                  <ProviderIcon size={20} className="text-zinc-200" weight="duotone" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-white font-semibold text-sm">{spec.label}</h3>
                    <Badge variant="outline" className={`text-[10px] py-0 px-1.5 ${st.cls}`}>
                      <StatusIcon size={10} className="inline mr-1" />{st.label}
                    </Badge>
                  </div>
                  {c.last_checked_at && (
                    <div className="text-[10px] font-mono text-zinc-500 mt-1">
                      Último check: {formatDateTime(c.last_checked_at)}
                    </div>
                  )}
                  {spec.key === "telnyx" && telnyxCfg && (
                    <div className="text-[10px] font-mono text-zinc-500 mt-1">
                      {telnyxCfg.api_key_present ? "API key: " + (telnyxCfg.api_key_masked || "✓") : "API key: —"}
                      {" · "}{telnyxCfg.phone_number || "sin número"}
                    </div>
                  )}
                  {c.error_message && (
                    <div className="text-[11px] text-red-400 mt-1 line-clamp-2">{c.error_message}</div>
                  )}
                </div>
                <div className="flex flex-col gap-1 items-end">
                  {spec.testEndpoint && (
                    <Button size="sm" variant="outline"
                      disabled={testing[spec.key]}
                      onClick={() => testConnector(spec)}
                      data-testid={`connector-test-${spec.key}`}>
                      {testing[spec.key] ? "…" : (spec.testLabel || "Probar")}
                    </Button>
                  )}
                  <button className="text-[11px] text-zinc-400 hover:text-white flex items-center gap-1"
                    onClick={() => setExpanded(isExp ? null : spec.key)}
                    data-testid={`connector-toggle-${spec.key}`}>
                    Cómo conectar <CaretDown size={12} className={isExp ? "rotate-180 transition" : "transition"} />
                  </button>
                </div>
              </div>
              {isExp && (
                <div className="border-t border-zinc-800 bg-zinc-950/40 p-4 space-y-3"
                     data-testid={`connector-howto-${spec.key}`}>
                  <ol className="text-sm text-zinc-300 space-y-1 list-decimal pl-5">
                    {spec.howto.map((step, i) => <li key={i}>{step}</li>)}
                  </ol>
                  {spec.envVars.length > 0 && (
                    <div>
                      <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-1">
                        Variables en backend/.env
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {spec.envVars.map((v) => (
                          <code key={v} className="text-[11px] px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 font-mono">
                            {v}
                          </code>
                        ))}
                      </div>
                    </div>
                  )}
                  <a href={spec.docUrl} target="_blank" rel="noreferrer"
                     className="inline-flex items-center gap-1 text-[12px] text-blue-300 hover:text-blue-200">
                    Abrir portal <ArrowSquareOut size={12} />
                  </a>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Layout>
  );
}
