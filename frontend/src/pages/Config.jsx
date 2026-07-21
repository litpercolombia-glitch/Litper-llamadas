import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import {
  Key, CheckCircle, WarningCircle, Plugs, FloppyDisk, TestTube,
  Trash, ArrowSquareOut, Eye, EyeSlash, Gear,
} from "@phosphor-icons/react";

const PROVIDER_META = {
  chatea_pro: {
    label: "Chatea Pro · WhatsApp",
    doc: "https://chateapro.app/settings#/api",
    hint: "Obtén el token en Chatea Pro → Configuración → API tokens.",
  },
  telnyx: {
    label: "Telnyx · SIP (primario)",
    doc: "https://portal.telnyx.com",
    hint: "Compra un número CO, crea una Voice/SIP Connection y guarda API Key + Connection ID.",
  },
  elevenlabs: {
    label: "ElevenLabs · Voz IA",
    doc: "https://elevenlabs.io/app/settings/api-keys",
    hint: "API Key con permisos ConvAI + TTS. Voice ID desde Voice Lab.",
  },
  twilio: {
    label: "Twilio · Caller ID (secundario)",
    doc: "https://console.twilio.com/",
    hint: "Account SID + Auth Token desde Twilio Console.",
  },
  groq:     { label: "Groq · LLM primario",  doc: "https://console.groq.com/keys", hint: "" },
  gemini:   { label: "Gemini · Análisis",    doc: "https://aistudio.google.com/apikey", hint: "" },
  mistral:  { label: "Mistral · Alternativa", doc: "https://console.mistral.ai/api-keys/", hint: "" },
  cerebras: { label: "Cerebras · Alta velocidad", doc: "https://cloud.cerebras.ai/", hint: "" },
  claude:   { label: "Claude · Redacción", doc: "https://console.anthropic.com/", hint: "" },
};

export default function ConfigPage() {
  const [providers, setProviders] = useState([]);
  const [schema, setSchema] = useState([]);
  const [drafts, setDrafts] = useState({}); // { provider: { field: value } }
  const [visible, setVisible] = useState({}); // { provider_field: bool }
  const [busy, setBusy] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [status, sch] = await Promise.all([
        api.get("/config/credentials"),
        api.get("/config/providers"),
      ]);
      setProviders(status.data.providers || []);
      setSchema(sch.data.providers || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const schemaOf = (p) => (schema.find((s) => s.provider === p) || {}).fields || [];

  const setDraftField = (p, f, v) => {
    setDrafts((d) => ({ ...d, [p]: { ...(d[p] || {}), [f]: v } }));
  };

  const save = async (p) => {
    setBusy((b) => ({ ...b, [`save-${p}`]: true }));
    try {
      await api.put(`/config/credentials/${p}`, { values: drafts[p] || {} });
      toast.success("Credenciales guardadas (encriptadas).");
      setDrafts((d) => { const c = { ...d }; delete c[p]; return c; });
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error guardando.");
    } finally {
      setBusy((b) => ({ ...b, [`save-${p}`]: false }));
    }
  };

  const test = async (p) => {
    setBusy((b) => ({ ...b, [`test-${p}`]: true }));
    try {
      const r = await api.post(`/config/credentials/${p}/test`);
      if (r.data?.ok) toast.success(`${p}: ${r.data.detail || "OK"}`);
      else toast.error(`${p}: ${r.data?.detail || "falló"}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error probando.");
    } finally {
      setBusy((b) => ({ ...b, [`test-${p}`]: false }));
    }
  };

  const clearProvider = async (p) => {
    if (!window.confirm(`¿Borrar credenciales de ${p}? Volverá al fallback .env.`)) return;
    await api.delete(`/config/credentials/${p}`);
    load();
  };

  return (
    <Layout
      title="Configuración · Credenciales"
      subtitle="Cada organización guarda sus propias llaves — encriptadas en el servidor. NUNCA se muestran en el navegador."
    >
      <div className="mb-4 rounded-lg border border-emerald-500/25 bg-emerald-500/5 backdrop-blur-md p-3 text-xs text-emerald-200 flex gap-2 items-start"
        data-testid="config-security-note">
        <CheckCircle size={16} className="text-emerald-400 mt-0.5" weight="duotone" />
        <div>
          <b>Encripción en reposo</b> con clave <code>ENCRYPTION_KEY</code>.
          El frontend solo ve estados (conectado/no) y una pista corta enmascarada como <code>cp_t…3456</code>.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {providers.map((p) => {
          const meta = PROVIDER_META[p.provider] || { label: p.provider, doc: "", hint: "" };
          const fields = schemaOf(p.provider);
          const draft = drafts[p.provider] || {};
          const hasDraft = Object.keys(draft).length > 0;
          return (
            <div key={p.provider}
              className="rounded-lg border border-zinc-800 bg-zinc-900/40 backdrop-blur-md p-4"
              data-testid={`config-card-${p.provider}`}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Key size={16} className="text-zinc-300" weight="duotone" />
                    <h3 className="text-sm font-semibold text-white truncate">{meta.label}</h3>
                    <Badge variant="outline" className={
                      p.origin === "org"   ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10 text-[10px]" :
                      p.origin === "env"   ? "text-blue-300 border-blue-500/40 bg-blue-500/10 text-[10px]" :
                                             "text-zinc-500 border-zinc-700 bg-zinc-800/50 text-[10px]"}>
                      {p.origin === "org" ? "org (encriptado)" :
                       p.origin === "env" ? "env fallback" : "sin configurar"}
                    </Badge>
                  </div>
                  {p.hint && <div className="text-[10px] font-mono text-zinc-500 mt-1">Hint: {p.hint}</div>}
                  {meta.hint && <p className="text-[11px] text-zinc-400 mt-1">{meta.hint}</p>}
                </div>
                {meta.doc && (
                  <a href={meta.doc} target="_blank" rel="noreferrer"
                    className="text-[11px] text-blue-300 hover:text-blue-200 flex items-center gap-1 shrink-0">
                    Portal <ArrowSquareOut size={11} />
                  </a>
                )}
              </div>

              <div className="space-y-2 mt-3">
                {fields.map((f) => {
                  const showKey = `${p.provider}-${f.name}`;
                  const vis = !!visible[showKey];
                  return (
                    <div key={f.name}>
                      <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 flex items-center gap-1.5">
                        {f.label}
                        {f.is_secret && <span className="text-[9px] text-zinc-500">(secreto)</span>}
                        {f.has_value && <CheckCircle size={11} className="text-emerald-400" />}
                      </label>
                      <div className="flex items-center gap-1.5">
                        <Input
                          type={f.is_secret && !vis ? "password" : "text"}
                          placeholder={f.has_value ? "•••••• (deja vacío para no cambiar)" : `Pega tu ${f.label}`}
                          value={draft[f.name] ?? ""}
                          onChange={(e) => setDraftField(p.provider, f.name, e.target.value)}
                          className="h-8 text-xs font-mono"
                          data-testid={`config-input-${p.provider}-${f.name}`}
                        />
                        {f.is_secret && (
                          <button
                            type="button" tabIndex={-1}
                            className="text-zinc-500 hover:text-zinc-200 shrink-0"
                            onClick={() => setVisible((v) => ({ ...v, [showKey]: !vis }))}>
                            {vis ? <EyeSlash size={14} /> : <Eye size={14} />}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-between items-center gap-2 mt-3 pt-3 border-t border-zinc-800">
                <div className="flex gap-2">
                  <Button size="sm" variant="outline"
                    disabled={busy[`test-${p.provider}`]}
                    onClick={() => test(p.provider)}
                    data-testid={`config-test-${p.provider}`}>
                    <TestTube size={13} /> {busy[`test-${p.provider}`] ? "…" : "Probar conexión"}
                  </Button>
                  {p.origin === "org" && (
                    <Button size="sm" variant="ghost" className="text-red-400 hover:text-red-300"
                      onClick={() => clearProvider(p.provider)}
                      data-testid={`config-clear-${p.provider}`}>
                      <Trash size={13} /> Limpiar
                    </Button>
                  )}
                </div>
                <Button size="sm" className="btn-cta-grad"
                  disabled={!hasDraft || busy[`save-${p.provider}`]}
                  onClick={() => save(p.provider)}
                  data-testid={`config-save-${p.provider}`}>
                  <FloppyDisk size={13} /> {busy[`save-${p.provider}`] ? "Guardando…" : "Guardar"}
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {loading && <div className="text-zinc-400 text-sm mt-4">Cargando…</div>}
    </Layout>
  );
}
