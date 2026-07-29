import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  CheckCircle, CaretDown, ArrowSquareOut, TestTube, FloppyDisk,
  Storefront, WhatsappLogo, PhoneCall, Waveform, ShoppingBag, Circle,
} from "@phosphor-icons/react";

/**
 * Each connector is described declaratively — verbatim Spanish text as
 * requested by the product owner. Fields resolve to the org_credentials
 * schema so the same PUT /config/credentials/{provider} works.
 */
const CONNECTORS = [
  {
    key: "dropi",
    label: "Dropi — Trae tus pedidos y novedades",
    Icon: ShoppingBag,
    steps: [
      "Entra a tu panel Dropi → Integraciones/API.",
      "Copia tu API Token y tu país/URL.",
      "Pégalos aquí y dale Probar.",
    ],
    tagline: "Zynex leerá los pedidos en oficina y creará tickets de extensión.",
    docUrl: "https://dropi.co/",
    fields: [
      { name: "api_token", label: "API Token de Dropi", secret: true, placeholder: "eyJ0eXAiOiJKV1Qi…" },
      { name: "country",   label: "País",  placeholder: "CO / EC / CL / MX / PE" },
      { name: "base_url",  label: "URL panel (opcional)", placeholder: "https://app.dropi.co" },
    ],
  },
  {
    key: "chatea_pro",
    label: "Chatea Pro — WhatsApp de tu operación",
    Icon: WhatsappLogo,
    steps: [
      "Entra a chateapro.app → Settings → API.",
      "Copia tu API Token.",
      "Pégalo aquí y dale Probar.",
    ],
    tagline: "Zynex enviará las plantillas aprobadas y responderá dentro de la ventana de 24h.",
    docUrl: "https://chateapro.app/settings#/api",
    fields: [
      { name: "api_key",  label: "API Token",       secret: true, placeholder: "cp_…" },
      { name: "base_url", label: "Base URL (opcional)", placeholder: "https://api.chateapro.app" },
    ],
  },
  {
    key: "telnyx",
    label: "Telnyx (voz) — Para que Sofía llame por teléfono",
    Icon: PhoneCall,
    steps: [
      "portal.telnyx.com → API Keys → crea una (empieza con KEY...).",
      "Voice → Applications → crea una Call Control App y copia el Connection ID.",
      "Numbers → compra un número de Colombia con Voz y asígnalo a esa App.",
      "Pega API Key + Connection ID + número (+57...) aquí.",
    ],
    tagline: "La operadora IA llama con voz clara y sin corte.",
    docUrl: "https://portal.telnyx.com",
    fields: [
      { name: "api_key",       label: "API Key",       secret: true, placeholder: "KEY01A…" },
      { name: "connection_id", label: "Connection ID", secret: true, placeholder: "1234567890" },
      { name: "phone_number",  label: "Número (+57...)", placeholder: "+573001234567" },
    ],
  },
  {
    key: "elevenlabs",
    label: "ElevenLabs — La voz de Sofía",
    Icon: Waveform,
    steps: [
      "elevenlabs.io → perfil → API Keys → copia la key (empieza con sk_).",
      "Elige la voz o usa la de Litper.",
      "Pega la key aquí y dale Probar.",
    ],
    tagline: "Voz natural en español latino para el confirm/rescate.",
    docUrl: "https://elevenlabs.io/app/settings/api-keys",
    fields: [
      { name: "api_key",          label: "API Key",       secret: true, placeholder: "sk_…" },
      { name: "default_voice_id", label: "Voice ID (opcional)", placeholder: "EXAVITQu4vr4xnSDxMaL" },
    ],
  },
  {
    key: "shopify",
    label: "Shopify — Conecta tu tienda",
    Icon: Storefront,
    steps: [
      "Shopify Admin → Settings → Apps → Develop apps → crea una app.",
      "Copia el Admin API access token.",
      "Pega el token + tu URL (xxx.myshopify.com) aquí.",
    ],
    tagline: "Sincroniza pedidos Shopify hacia Zynex (opcional).",
    docUrl: "https://help.shopify.com/manual/apps/custom-apps",
    fields: [
      { name: "access_token", label: "Admin API access token", secret: true, placeholder: "shpat_…" },
      { name: "store_url",    label: "URL de tu tienda", placeholder: "mitienda.myshopify.com" },
    ],
  },
];

function StatusPill({ configured }) {
  return configured ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest text-emerald-300 border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 rounded-sm">
      <CheckCircle size={11} weight="fill" /> Conectado
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest text-zinc-400 border border-zinc-700 bg-zinc-900 px-2 py-0.5 rounded-sm">
      <Circle size={9} /> Sin conectar
    </span>
  );
}

function ConnectorCard({ spec, status: srvStatus, onSaved }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState(null); // {ok, detail}

  const configured = !!srvStatus?.configured;

  const setField = (name, v) => setValues((prev) => ({ ...prev, [name]: v }));

  const save = async () => {
    setBusy(true);
    setTestResult(null);
    try {
      // Only send non-empty values (backend upserts non-secret fields as-is).
      const clean = Object.fromEntries(
        Object.entries(values).filter(([, v]) => v != null && String(v).trim() !== "")
      );
      if (Object.keys(clean).length === 0) {
        toast.error("Escribe al menos un campo.");
        return;
      }
      await api.put(`/config/credentials/${spec.key}`, { values: clean });
      toast.success("Credenciales guardadas.");
      setValues({});
      onSaved?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "No se pudo guardar.");
    } finally { setBusy(false); }
  };

  const test = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/config/credentials/${spec.key}/test`);
      setTestResult(r.data);
      if (r.data?.ok) toast.success(r.data?.detail || "Conexión OK.");
      else toast.error(r.data?.detail || "Falló la prueba.");
    } catch (e) {
      const detail = e?.response?.data?.detail || e.message;
      setTestResult({ ok: false, detail });
      toast.error(detail);
    } finally { setBusy(false); }
  };

  const Icon = spec.Icon;
  return (
    <div className="border border-zinc-800 bg-zinc-900/40 rounded-sm overflow-hidden"
         data-testid={`connector-card-${spec.key}`}>
      <div className="flex items-center justify-between gap-3 p-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-sm bg-zinc-800/70 border border-zinc-700 grid place-items-center shrink-0">
            <Icon size={18} weight="duotone" className="text-white" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-white truncate">{spec.label}</div>
            <div className="text-[11px] text-zinc-400 truncate">{spec.tagline}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusPill configured={configured} />
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpen((o) => !o)}
            data-testid={`connector-toggle-${spec.key}`}
            className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
            Cómo conectar
            <CaretDown size={12} className={`ml-1 transition ${open ? "rotate-180" : ""}`} />
          </Button>
        </div>
      </div>

      {open && (
        <div className="border-t border-zinc-800 bg-zinc-950/40 p-5 space-y-4"
             data-testid={`connector-howto-${spec.key}`}>
          <ol className="text-sm text-zinc-200 space-y-1 list-decimal pl-5">
            {spec.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>

          <a href={spec.docUrl} target="_blank" rel="noreferrer"
             className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200"
             data-testid={`connector-doc-${spec.key}`}>
            Abrir portal oficial <ArrowSquareOut size={11} />
          </a>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {spec.fields.map((f) => (
              <div key={f.name}>
                <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">
                  {f.label}
                </label>
                <Input
                  type={f.secret ? "password" : "text"}
                  autoComplete="off"
                  placeholder={f.placeholder || ""}
                  value={values[f.name] ?? ""}
                  onChange={(e) => setField(f.name, e.target.value)}
                  data-testid={`connector-input-${spec.key}-${f.name}`}
                  className="bg-black/40 border-zinc-700 h-9 text-sm rounded-sm text-white"
                />
              </div>
            ))}
          </div>

          {testResult && (
            <div className={`text-xs font-mono px-3 py-2 rounded-sm border ${
              testResult.ok
                ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-200"
                : "bg-red-500/10 border-red-500/40 text-red-200"
            }`} data-testid={`connector-testresult-${spec.key}`}>
              {testResult.ok ? "✓ " : "✗ "}{testResult.detail}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button
              variant="outline"
              onClick={save}
              disabled={busy}
              data-testid={`connector-save-${spec.key}`}
              className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-9">
              <FloppyDisk size={13} className="mr-1" /> Guardar
            </Button>
            <Button
              onClick={test}
              disabled={busy}
              data-testid={`connector-test-${spec.key}`}
              className="btn-cta-grad rounded-sm h-9">
              <TestTube size={13} className="mr-1" />
              {busy ? "Probando…" : "Probar conexión"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ConnectorsPage() {
  const [statusByKey, setStatusByKey] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/config/credentials");
      const map = {};
      (r.data?.providers || []).forEach((p) => { map[p.provider] = p; });
      setStatusByKey(map);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  return (
    <Layout
      title="Conexiones"
      subtitle="Conecta tus herramientas. Los tokens quedan cifrados y solo tú los ves."
    >
      {loading && <div className="text-zinc-500 font-mono text-sm">Cargando…</div>}
      {!loading && (
        <div className="space-y-3 max-w-4xl">
          {CONNECTORS.map((c) => (
            <ConnectorCard
              key={c.key}
              spec={c}
              status={statusByKey[c.key]}
              onSaved={load}
            />
          ))}
        </div>
      )}
    </Layout>
  );
}
