import { useEffect, useState, useMemo } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import {
  CheckCircle, Circle, ArrowRight, ArrowSquareOut, Key, TestTube,
  FloppyDisk, Rocket, Sparkle, Eye, EyeSlash,
} from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";

// Field lists per step (mirrors backend PROVIDER_SCHEMAS for the wizard scope)
const STEP_FIELDS = {
  chatea_pro: [
    { name: "api_key",  label: "API Token", is_secret: true },
    { name: "base_url", label: "Base URL (opcional)", is_secret: false, placeholder: "https://chateapro.app/api" },
  ],
  elevenlabs: [
    { name: "api_key",          label: "API Key",            is_secret: true },
    { name: "default_voice_id", label: "Voice ID por defecto", is_secret: false },
  ],
  telnyx: [
    { name: "api_key",       label: "API Key",       is_secret: true },
    { name: "connection_id", label: "Connection ID", is_secret: true },
    { name: "phone_number",  label: "Número E.164",  is_secret: false },
    { name: "sip_username",  label: "SIP username",  is_secret: false },
    { name: "sip_password",  label: "SIP password",  is_secret: true },
  ],
};
// The LLM step lets the user pick 1 of 5 providers.
const LLM_OPTIONS = [
  { key: "groq",     label: "Groq (gratis, rápido)",   doc: "https://console.groq.com/keys" },
  { key: "gemini",   label: "Gemini",   doc: "https://aistudio.google.com/apikey" },
  { key: "claude",   label: "Claude",   doc: "https://console.anthropic.com/" },
  { key: "mistral",  label: "Mistral",  doc: "https://console.mistral.ai/api-keys/" },
  { key: "cerebras", label: "Cerebras", doc: "https://cloud.cerebras.ai/" },
];

export default function OnboardingPage() {
  const [state, setState] = useState(null);
  const [current, setCurrent] = useState(0);
  const [drafts, setDrafts] = useState({});   // { provider: { field: value } }
  const [visible, setVisible] = useState({});
  const [llmProvider, setLlmProvider] = useState("groq");
  const [busy, setBusy] = useState({});
  const nav = useNavigate();

  const load = async () => {
    const r = await api.get("/config/onboarding");
    setState(r.data);
  };
  useEffect(() => { load(); }, []);

  const steps = state?.steps || [];
  const connected = state?.connected || 0;
  const total = state?.total || 5;

  const step = steps[current];
  const provKey = step?.key === "llm" ? llmProvider : step?.key;
  const fields = step?.key === "llm"
    ? [{ name: "api_key", label: "API Key", is_secret: true }]
    : (STEP_FIELDS[provKey] || []);

  const setField = (p, f, v) => setDrafts((d) => ({ ...d, [p]: { ...(d[p] || {}), [f]: v } }));

  const save = async () => {
    if (!step || step.key === "dropi") { setCurrent((i) => Math.min(i + 1, steps.length - 1)); return; }
    setBusy((b) => ({ ...b, save: true }));
    try {
      await api.put(`/config/credentials/${provKey}`, { values: drafts[provKey] || {} });
      toast.success(`${step.label}: guardado (encriptado).`);
      await load();
      setDrafts((d) => { const c = { ...d }; delete c[provKey]; return c; });
      // auto-advance if now connected
      const r = await api.get("/config/onboarding");
      const s = r.data.steps.find((x) => x.key === step.key);
      if (s?.connected && current < steps.length - 1) setCurrent(current + 1);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error guardando.");
    } finally { setBusy((b) => ({ ...b, save: false })); }
  };

  const test = async () => {
    if (!step || step.key === "dropi") return;
    setBusy((b) => ({ ...b, test: true }));
    try {
      const r = await api.post(`/config/credentials/${provKey}/test`);
      const detail = r.data?.detail;
      const detailText = (typeof detail === "string") ? detail
        : (detail ? JSON.stringify(detail).slice(0, 160) : "");
      if (r.data?.ok) toast.success(`${step.label}: ${detailText || "OK"}`);
      else toast.error(`${step.label}: ${detailText || "falló"}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error probando.");
    } finally { setBusy((b) => ({ ...b, test: false })); }
  };

  const progressPct = useMemo(() => Math.round((connected / total) * 100), [connected, total]);

  if (!state) return <Layout title="Onboarding"><div className="text-zinc-400">Cargando…</div></Layout>;

  return (
    <Layout
      title="Conecta tus herramientas"
      subtitle="Paso a paso — trae tus llaves (BYOK). Nada sale del backend en texto plano."
    >
      {/* Progress header */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] backdrop-blur-xl p-5 mb-6"
           data-testid="onboarding-progress">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-muted)]">
              Progreso {connected}/{total} conectado
            </div>
            <h2 className={`text-2xl font-semibold ${state.minimum_ok ? "grad-text" : ""}`}
                data-testid="onboarding-ready-message">
              {state.ready_message}
            </h2>
          </div>
          {state.minimum_ok && (
            <Button className="btn-cta-grad" onClick={() => nav("/app")} data-testid="onboarding-launch-btn">
              <Rocket size={14} weight="fill" /> Ir al Copilot
            </Button>
          )}
        </div>
        <div className="h-2 rounded-full bg-[var(--border)] overflow-hidden">
          <div className="h-full transition-all duration-500"
               style={{ width: `${progressPct}%`, background: "var(--accent-grad)" }}
               data-testid="onboarding-progress-bar" />
        </div>

        {/* Stepper */}
        <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-2">
          {steps.map((s, i) => (
            <button key={s.key}
              onClick={() => setCurrent(i)}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 border text-xs text-left transition
                ${i === current
                  ? "border-transparent bg-gradient-to-r from-[color-mix(in_oklab,var(--accent)_20%,var(--surface))] to-[var(--surface)] shadow-[0_0_16px_-4px_color-mix(in_oklab,var(--accent)_55%,transparent)]"
                  : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)]"}`}
              data-testid={`onboarding-step-${s.key}`}>
              {s.connected
                ? <CheckCircle size={16} className="text-emerald-400 shrink-0" weight="fill" />
                : <Circle size={16} className="text-[var(--text-muted)] shrink-0" />}
              <span className="min-w-0 truncate">{s.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Current step editor */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] backdrop-blur-xl p-6"
           data-testid={`onboarding-current-${step?.key}`}>
        <div className="flex items-center gap-2 mb-1">
          <Key size={16} className="text-[var(--text-secondary)]" weight="duotone" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-muted)]">
            Paso {current + 1} de {total}
          </span>
        </div>
        <h3 className="text-xl font-semibold">{step?.label}</h3>
        <p className="text-sm text-[var(--text-secondary)] mt-1">{step?.instructions}</p>
        {step?.doc && (
          <a href={step.doc} target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-1 text-[13px] text-blue-300 hover:text-blue-200 mt-2">
            Obtener la llave <ArrowSquareOut size={12} />
          </a>
        )}

        {step?.key === "llm" && (
          <div className="mt-4">
            <label className="text-[10px] uppercase font-mono tracking-widest text-[var(--text-muted)]">Elige tu motor de IA</label>
            <div className="flex flex-wrap gap-2 mt-1">
              {LLM_OPTIONS.map((o) => (
                <button key={o.key}
                  onClick={() => setLlmProvider(o.key)}
                  className={`px-3 py-1.5 rounded-full text-xs border transition ${
                    llmProvider === o.key
                      ? "border-transparent bg-[var(--text-primary)] text-[var(--bg-primary)]"
                      : "border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]"
                  }`}
                  data-testid={`onboarding-llm-${o.key}`}>
                  {o.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {step?.key === "dropi" ? (
          <div className="mt-6 rounded-lg border border-blue-500/30 bg-blue-500/5 p-4 text-sm text-blue-200"
               data-testid="onboarding-dropi-info">
            Dropi no requiere API. Solo exporta el archivo <b>Reclamos en Oficina</b> desde tu panel y súbelo en
            <a href="/app/import" className="text-blue-100 underline underline-offset-2 ml-1">Importar</a>.
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            {fields.map((f) => {
              const draft = drafts[provKey] || {};
              const showKey = `${provKey}-${f.name}`;
              const vis = !!visible[showKey];
              return (
                <div key={f.name}>
                  <label className="text-[10px] uppercase font-mono tracking-widest text-[var(--text-muted)]">
                    {f.label}{f.is_secret ? " (secreto)" : ""}
                  </label>
                  <div className="flex items-center gap-1.5">
                    <Input
                      type={f.is_secret && !vis ? "password" : "text"}
                      placeholder={f.placeholder || `Pega tu ${f.label}`}
                      value={draft[f.name] ?? ""}
                      onChange={(e) => setField(provKey, f.name, e.target.value)}
                      className="h-9 text-sm font-mono"
                      data-testid={`onboarding-input-${provKey}-${f.name}`}
                    />
                    {f.is_secret && (
                      <button type="button" tabIndex={-1}
                        className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                        onClick={() => setVisible((v) => ({ ...v, [showKey]: !vis }))}>
                        {vis ? <EyeSlash size={14} /> : <Eye size={14} />}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="flex items-center justify-between mt-6 pt-4 border-t border-[var(--border)]">
          <Button variant="ghost"
            disabled={current === 0}
            onClick={() => setCurrent(current - 1)}
            data-testid="onboarding-prev">
            ← Anterior
          </Button>
          <div className="flex gap-2">
            {step?.key !== "dropi" && (
              <Button variant="outline" disabled={busy.test} onClick={test}
                data-testid="onboarding-test">
                <TestTube size={13} /> {busy.test ? "…" : "Probar"}
              </Button>
            )}
            {step?.key !== "dropi" && (
              <Button className="btn-cta-grad" disabled={busy.save} onClick={save}
                data-testid="onboarding-save-next">
                <FloppyDisk size={13} /> {busy.save ? "…" : "Guardar & siguiente"}
              </Button>
            )}
            {step?.key === "dropi" && (
              <Button className="btn-cta-grad" onClick={() => setCurrent(Math.min(current + 1, total - 1))}
                data-testid="onboarding-skip-dropi">
                Continuar <ArrowRight size={13} weight="bold" />
              </Button>
            )}
          </div>
        </div>
      </div>

      <p className="text-center text-[11px] text-[var(--text-muted)] mt-4">
        <Sparkle size={11} className="inline mr-1 text-emerald-400" weight="fill" />
        BYOK · Tus llaves se guardan encriptadas en el servidor. Nunca las vemos en texto plano.
      </p>
    </Layout>
  );
}
