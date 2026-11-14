import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { BusinessProfileForm } from "../components/BusinessProfile";
import AgentFromPrompt from "../components/AgentFromPrompt";
import { api } from "../lib/api";
import { errorText, useAssistantName } from "../lib/assistant";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  CheckCircle, Circle, ArrowRight, ArrowSquareOut, Key, TestTube,
  FloppyDisk, Rocket, Storefront, Robot, Eye, EyeSlash, ShieldCheck,
} from "@phosphor-icons/react";

// Proveedores de inteligencia artificial admitidos (una sola llave basta).
const LLM_OPTIONS = [
  { key: "openrouter", label: "OpenRouter (recomendado)", doc: "https://openrouter.ai/keys" },
  { key: "groq",       label: "Groq",     doc: "https://console.groq.com/keys" },
  { key: "gemini",     label: "Gemini",   doc: "https://aistudio.google.com/apikey" },
  { key: "claude",     label: "Claude",   doc: "https://console.anthropic.com/" },
  { key: "mistral",    label: "Mistral",  doc: "https://console.mistral.ai/api-keys/" },
  { key: "cerebras",   label: "Cerebras", doc: "https://cloud.cerebras.ai/" },
];

const STEPS = [
  { key: "perfil", label: "Tu negocio",          Icon: Storefront },
  { key: "ia",     label: "Llave de IA",         Icon: Key },
  { key: "agente", label: "Tu primer agente",    Icon: Robot },
];

const CARD = "border border-zinc-800 rounded-sm bg-zinc-900/40 p-6";

/**
 * Primeros pasos — 3 pasos, sin exigir ningún proveedor de mensajería:
 *   1) perfil del negocio  2) llave de IA  3) primer agente con un prompt.
 */
export default function OnboardingPage() {
  const nav = useNavigate();
  const asistente = useAssistantName();
  const [current, setCurrent] = useState(0);
  const [done, setDone] = useState({ perfil: false, ia: false, agente: false });

  const [llmProvider, setLlmProvider] = useState("openrouter");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [busy, setBusy] = useState({});

  const markDone = (k) => setDone((d) => ({ ...d, [k]: true }));

  // Estado inicial: ¿ya hay perfil, llave de IA o agentes?
  useEffect(() => {
    let alive = true;
    (async () => {
      const [prof, onb, ags] = await Promise.allSettled([
        api.get("/org/profile"),
        api.get("/config/onboarding"),
        api.get("/custom-agents"),
      ]);
      if (!alive) return;
      const p = prof.status === "fulfilled" ? (prof.value.data?.profile || prof.value.data || {}) : {};
      const llm = onb.status === "fulfilled"
        ? !!(onb.value.data?.steps || []).find((s) => s.key === "llm")?.connected : false;
      const agents = ags.status === "fulfilled" ? (ags.value.data?.agents || []) : [];
      const next = {
        perfil: !!(p.empresa && String(p.empresa).trim()),
        ia: llm,
        agente: agents.some((a) => a.estado !== "borrador") || false,
      };
      setDone(next);
      setCurrent(!next.perfil ? 0 : !next.ia ? 1 : 2);
    })();
    return () => { alive = false; };
  }, []);

  const saveKey = async () => {
    if (!apiKey.trim()) { toast.error("Pega tu llave primero."); return; }
    setBusy((b) => ({ ...b, save: true }));
    try {
      await api.put(`/config/credentials/${llmProvider}`, { values: { api_key: apiKey.trim() } });
      setApiKey("");
      markDone("ia");
      toast.success("Llave guardada y cifrada.");
      setCurrent(2);
    } catch (e) {
      toast.error(errorText(e, "No se pudo guardar la llave."));
    } finally { setBusy((b) => ({ ...b, save: false })); }
  };

  const testKey = async () => {
    setBusy((b) => ({ ...b, test: true }));
    try {
      const r = await api.post(`/config/credentials/${llmProvider}/test`);
      const detail = r.data?.detail;
      const text = typeof detail === "string" ? detail : "";
      if (r.data?.ok) toast.success(text || "La llave funciona.");
      else toast.error(text || "La llave no funcionó. Revisa que esté completa y con saldo.");
    } catch (e) {
      toast.error(errorText(e, "No se pudo probar la llave. Guárdala primero."));
    } finally { setBusy((b) => ({ ...b, test: false })); }
  };

  const doneCount = Object.values(done).filter(Boolean).length;
  const allDone = doneCount === STEPS.length;
  const llm = LLM_OPTIONS.find((o) => o.key === llmProvider);

  return (
    <Layout
      title="Primeros pasos"
      subtitle="Tres pasos y tu primer agente queda listo."
    >
      {/* Progreso */}
      <div className={`${CARD} mb-6`} data-testid="onboarding-progress">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
              {doneCount} de {STEPS.length} pasos completos
            </div>
            <h2 className="text-xl font-medium text-zinc-100" data-testid="onboarding-ready-message">
              {allDone ? "Todo listo. Ya puedes trabajar con tu asistente." : "Vamos paso a paso."}
            </h2>
          </div>
          <Button className={allDone ? "btn-cta-grad rounded-sm" : "rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800"}
                  variant={allDone ? "default" : "outline"}
                  onClick={() => nav("/app")} data-testid="onboarding-launch-btn">
            <Rocket size={14} weight="fill" className="mr-1.5" /> Ir con {asistente}
          </Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          {STEPS.map((s, i) => (
            <button key={s.key} onClick={() => setCurrent(i)}
                    data-testid={`onboarding-step-${s.key}`}
                    className={`flex items-center gap-2 rounded-sm px-3 py-2.5 border text-sm text-left transition ${
                      i === current
                        ? "border-white bg-white/5 text-white"
                        : "border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white hover:border-zinc-600"
                    }`}>
              {done[s.key]
                ? <CheckCircle size={16} className="text-green-500 shrink-0" weight="fill" />
                : <Circle size={16} className="text-zinc-600 shrink-0" />}
              <span className="font-mono text-[10px] text-zinc-500">{i + 1}</span>
              <span className="truncate">{s.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Paso 1 — perfil del negocio */}
      {current === 0 && (
        <div className={CARD} data-testid="onboarding-current-perfil">
          <h3 className="text-lg font-medium text-zinc-200">1. Cuéntanos de tu negocio</h3>
          <p className="text-sm text-zinc-400 mt-1 mb-4">
            Con esto el asistente habla como tu empresa: en tu idioma, con tu moneda y tu horario.
          </p>
          <BusinessProfileForm
            testIdPrefix="onboarding-profile"
            submitLabel="Guardar y continuar"
            onSaved={() => { markDone("perfil"); setCurrent(1); }}
          />
        </div>
      )}

      {/* Paso 2 — llave de IA */}
      {current === 1 && (
        <div className={CARD} data-testid="onboarding-current-ia">
          <h3 className="text-lg font-medium text-zinc-200">2. Conecta la inteligencia artificial</h3>
          <p className="text-sm text-zinc-400 mt-1">
            El asistente necesita una llave de un proveedor de inteligencia artificial. Tú la creas en la página del
            proveedor, la pegas aquí y pagas directamente al proveedor solo lo que uses.
          </p>
          {done.ia && (
            <div className="mt-3 text-sm px-3 py-2 rounded-sm border border-green-500/20 bg-green-500/10 text-green-400 flex items-center gap-2"
                 data-testid="onboarding-ia-connected">
              <CheckCircle size={15} weight="fill" /> Ya tienes una llave conectada. Puedes cambiarla o continuar.
            </div>
          )}

          <div className="mt-4">
            <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500">Elige tu proveedor</label>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {LLM_OPTIONS.map((o) => (
                <button key={o.key} onClick={() => setLlmProvider(o.key)}
                        data-testid={`onboarding-llm-${o.key}`}
                        className={`px-3 py-1.5 rounded-sm text-xs border transition ${
                          llmProvider === o.key
                            ? "border-white bg-white/10 text-white"
                            : "border-zinc-700 bg-zinc-950 text-zinc-400 hover:text-white"
                        }`}>
                  {o.label}
                </button>
              ))}
            </div>
            {llm?.doc && (
              <a href={llm.doc} target="_blank" rel="noreferrer"
                 className="inline-flex items-center gap-1 text-[13px] text-cyan-300 hover:text-cyan-200 mt-3">
                Crear mi llave en {llm.label.replace(" (recomendado)", "")} <ArrowSquareOut size={12} />
              </a>
            )}
          </div>

          <div className="mt-4 max-w-xl">
            <label className="text-xs text-zinc-400 block mb-1">Llave (secreta)</label>
            <div className="flex items-center gap-2">
              <Input type={showKey ? "text" : "password"} autoComplete="new-password"
                     value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                     placeholder="Pega aquí tu llave"
                     data-testid="onboarding-input-api-key"
                     className="bg-black/40 border-zinc-700 text-white font-mono text-sm" />
              <button type="button" tabIndex={-1} aria-label={showKey ? "Ocultar llave" : "Mostrar llave"}
                      className="text-zinc-500 hover:text-white"
                      onClick={() => setShowKey((v) => !v)}>
                {showKey ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1.5 flex items-center gap-1">
              <ShieldCheck size={12} className="text-green-500" weight="fill" />
              Se guarda cifrada y no se vuelve a mostrar.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 mt-6 pt-4 border-t border-zinc-800">
            <Button variant="ghost" onClick={() => setCurrent(0)} data-testid="onboarding-prev">← Anterior</Button>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={busy.test} onClick={testKey} data-testid="onboarding-test"
                      className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
                <TestTube size={13} className="mr-1" /> {busy.test ? "Probando…" : "Probar"}
              </Button>
              <Button className="btn-cta-grad rounded-sm" disabled={busy.save || !apiKey.trim()} onClick={saveKey}
                      data-testid="onboarding-save-next">
                <FloppyDisk size={13} className="mr-1" /> {busy.save ? "Guardando…" : "Guardar y continuar"}
              </Button>
              {done.ia && (
                <Button variant="outline" onClick={() => setCurrent(2)} data-testid="onboarding-ia-skip"
                        className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
                  Continuar <ArrowRight size={13} className="ml-1" />
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Paso 3 — primer agente con un prompt */}
      {current === 2 && (
        <div data-testid="onboarding-current-agente">
          {!done.ia && (
            <div className="mb-4 text-sm px-3 py-2 rounded-sm border border-yellow-500/20 bg-yellow-500/10 text-yellow-400"
                 data-testid="onboarding-agente-needs-ia">
              Para generar el agente primero conecta tu llave de inteligencia artificial (paso 2).
            </div>
          )}
          <h3 className="text-lg font-medium text-zinc-200 mb-3">3. Crea tu primer agente</h3>
          <AgentFromPrompt
            assistantName={asistente}
            onApplied={() => {
              markDone("agente");
              toast.success("Tu primer agente está guardado. Completa voz y número en Agentes.");
              nav("/app/ajustes?tab=agentes");
            }}
          />
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setCurrent(1)} data-testid="onboarding-prev">← Anterior</Button>
            <Button variant="ghost" onClick={() => nav("/app")} data-testid="onboarding-skip-agent">
              Lo haré después
            </Button>
          </div>
        </div>
      )}

      <p className="text-center text-[11px] text-zinc-500 mt-6">
        Las conexiones de mensajería, telefonía y voz son opcionales y se agregan después en Conexiones.
      </p>
    </Layout>
  );
}
