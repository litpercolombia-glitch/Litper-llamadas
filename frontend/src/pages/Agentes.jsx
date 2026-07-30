import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import HowItWorks from "../components/HowItWorks";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import {
  Robot, Plus, PhoneCall, Waveform, Wrench, ChatText,
  CaretLeft, CaretRight, CheckCircle, Trash,
  Sparkle,
} from "@phosphor-icons/react";

const STEPS = [
  { key: "proposito",     label: "¿Qué hace?",     Icon: Sparkle  },
  { key: "personalidad",  label: "Personalidad",   Icon: ChatText },
  { key: "voz",           label: "Voz",            Icon: Waveform },
  { key: "tools",         label: "Acciones",       Icon: Wrench   },
  { key: "prueba",        label: "Número + Prueba", Icon: PhoneCall },
];

const EMPTY = {
  nombre: "", proposito: "", prompt: "",
  saludo: "", cierre: "",
  tono: "profesional-cálido", idioma: "es-CO",
  voz_id: null, tools: [], variables: [],
  numero: "", estado: "borrador",
};

function StepDots({ step, total }) {
  return (
    <div className="flex items-center gap-1.5 mb-4" data-testid="agentwiz-dots">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i}
             className={`h-1.5 rounded-full transition-all ${
               i === step ? "w-8 bg-white" :
               i <  step ? "w-4 bg-cyan-400" :
                            "w-4 bg-zinc-700"
             }`} />
      ))}
    </div>
  );
}

function Wizard({ initial, templates, tools, voices, onCancel, onSaved }) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState(initial || EMPTY);
  const [savingCall, setSavingCall] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));

  const pickTemplate = (tpl) => {
    set({
      proposito: tpl.key,
      prompt:    tpl.prompt,
      tools:     tpl.tools || [],
      variables: tpl.variables || [],
    });
  };

  const toggleTool = (key) => {
    const list = new Set(draft.tools || []);
    list.has(key) ? list.delete(key) : list.add(key);
    set({ tools: Array.from(list) });
  };

  const next = () => setStep((s) => Math.min(STEPS.length - 1, s + 1));
  const back = () => setStep((s) => Math.max(0, s - 1));

  const canNext = () => {
    if (step === 0) return !!draft.proposito;
    if (step === 1) return !!draft.nombre?.trim() && !!draft.prompt?.trim();
    if (step === 2) return !!draft.voz_id;
    return true;
  };

  const save = async (estado) => {
    setSavingCall(true);
    try {
      const body = { ...draft };
      if (estado) body.estado = estado;
      if (draft.id) {
        const r = await api.patch(`/custom-agents/${draft.id}`, body);
        toast.success("Guardado.");
        onSaved(r.data.agent);
      } else {
        const r = await api.post("/custom-agents", body);
        set({ id: r.data.agent.id });
        toast.success("Agente creado.");
        onSaved(r.data.agent);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "No se pudo guardar.");
    } finally { setSavingCall(false); }
  };

  const testCall = async () => {
    if (!draft.numero?.trim()) { toast.error("Escribe tu número."); return; }
    if (!draft.id) { toast.error("Guarda el borrador primero."); return; }
    setSavingCall(true);
    try {
      const r = await api.post(`/custom-agents/${draft.id}/test-call`, { numero: draft.numero.trim() });
      setTestResult(r.data);
      if (r.data?.ok) toast.success(r.data?.detail || "Prueba OK.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falló la prueba.");
    } finally { setSavingCall(false); }
  };

  return (
    <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-6" data-testid="agentwiz-panel">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Robot size={18} weight="duotone" className="text-cyan-300" />
          <span className="text-sm font-semibold text-white">
            {draft.id ? `Editar: ${draft.nombre || "sin nombre"}` : "Nuevo agente"}
          </span>
          <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border border-zinc-700 bg-zinc-900 rounded-sm text-zinc-300">
            {draft.estado?.replace("_", " ")}
          </span>
        </div>
        <button onClick={onCancel} data-testid="agentwiz-close"
                className="text-xs text-zinc-400 hover:text-white">Cerrar</button>
      </div>

      <StepDots step={step} total={STEPS.length} />

      {/* Step 1 — Purpose (templates) */}
      {step === 0 && (
        <div data-testid="agentwiz-step-proposito" className="space-y-3">
          <div className="text-sm text-zinc-300 mb-2">
            ¿Qué quieres que haga tu agente? Elige una plantilla — Lyan te pre-llenará el prompt.
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {templates.map((t) => (
              <button key={t.key}
                onClick={() => pickTemplate(t)}
                data-testid={`agentwiz-template-${t.key}`}
                className={`text-left border rounded-sm px-3 py-3 transition ${
                  draft.proposito === t.key
                    ? "border-cyan-400 bg-cyan-500/10"
                    : "border-zinc-800 bg-zinc-950 hover:bg-zinc-900"
                }`}>
                <div className="text-sm font-semibold text-white">{t.label}</div>
                <div className="text-[11px] text-zinc-400 line-clamp-2 mt-1">{t.prompt}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 2 — Personality + prompt */}
      {step === 1 && (
        <div data-testid="agentwiz-step-personalidad" className="space-y-3">
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Nombre del agente</label>
            <Input value={draft.nombre} onChange={(e) => set({ nombre: e.target.value })}
                   placeholder="Ej: Sofía · Rescate Envía"
                   data-testid="agentwiz-nombre"
                   className="bg-black/40 border-zinc-700 text-white" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Tono</label>
              <Input value={draft.tono} onChange={(e) => set({ tono: e.target.value })}
                     placeholder="profesional-cálido"
                     data-testid="agentwiz-tono"
                     className="bg-black/40 border-zinc-700 text-white" />
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Idioma / acento</label>
              <Input value={draft.idioma} onChange={(e) => set({ idioma: e.target.value })}
                     placeholder="es-CO"
                     data-testid="agentwiz-idioma"
                     className="bg-black/40 border-zinc-700 text-white" />
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Variables (coma-separadas)</label>
              <Input value={(draft.variables || []).join(", ")}
                     onChange={(e) => set({ variables: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })}
                     placeholder="nombre, producto, direccion, valor"
                     data-testid="agentwiz-variables"
                     className="bg-black/40 border-zinc-700 text-white" />
            </div>
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Prompt (guion)</label>
            <Textarea rows={6} value={draft.prompt}
                     onChange={(e) => set({ prompt: e.target.value })}
                     placeholder="Eres una operadora..."
                     data-testid="agentwiz-prompt"
                     className="bg-black/40 border-zinc-700 text-white font-mono text-xs" />
            <p className="text-[10px] text-zinc-500 mt-1">
              Usa <code className="text-cyan-300">{"{{variable}}"}</code>. Nunca digas "impermeable".
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Input value={draft.saludo} onChange={(e) => set({ saludo: e.target.value })}
                   placeholder="Saludo (opcional)"
                   data-testid="agentwiz-saludo"
                   className="bg-black/40 border-zinc-700 text-white" />
            <Input value={draft.cierre} onChange={(e) => set({ cierre: e.target.value })}
                   placeholder="Cierre (opcional)"
                   data-testid="agentwiz-cierre"
                   className="bg-black/40 border-zinc-700 text-white" />
          </div>
        </div>
      )}

      {/* Step 3 — Voice */}
      {step === 2 && (
        <div data-testid="agentwiz-step-voz" className="space-y-2">
          <div className="text-sm text-zinc-300 mb-2">Elige una voz (ElevenLabs).</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {voices.map((v) => (
              <button key={v.id}
                onClick={() => set({ voz_id: v.id })}
                data-testid={`agentwiz-voice-${v.id}`}
                className={`text-left border rounded-sm px-3 py-2.5 transition ${
                  draft.voz_id === v.id
                    ? "border-cyan-400 bg-cyan-500/10"
                    : "border-zinc-800 bg-zinc-950 hover:bg-zinc-900"
                }`}>
                <div className="text-sm text-white font-semibold">{v.name}</div>
                <div className="text-[10px] font-mono text-zinc-500">{v.provider} · {v.id}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 4 — Tools */}
      {step === 3 && (
        <div data-testid="agentwiz-step-tools" className="space-y-2">
          <div className="text-sm text-zinc-300 mb-2">Habilita las acciones que tu agente puede tomar.</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {tools.map((t) => {
              const on = (draft.tools || []).includes(t.key);
              return (
                <label key={t.key}
                       data-testid={`agentwiz-tool-${t.key}`}
                       className={`flex items-center gap-3 border rounded-sm px-3 py-2 cursor-pointer transition ${
                         on ? "border-cyan-400 bg-cyan-500/10" : "border-zinc-800 bg-zinc-950 hover:bg-zinc-900"
                       }`}>
                  <input type="checkbox" checked={on} onChange={() => toggleTool(t.key)}
                         className="accent-cyan-400" />
                  <span className="text-sm text-white">{t.label}</span>
                  <span className="ml-auto text-[10px] font-mono text-zinc-500">{t.key}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 5 — Number + Test */}
      {step === 4 && (
        <div data-testid="agentwiz-step-prueba" className="space-y-3">
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Tu número (para la llamada de prueba)</label>
            <Input value={draft.numero} onChange={(e) => set({ numero: e.target.value })}
                   placeholder="+573001234567"
                   data-testid="agentwiz-numero"
                   className="bg-black/40 border-zinc-700 text-white" />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => save("borrador")} disabled={savingCall}
                    data-testid="agentwiz-save-draft"
                    variant="outline"
                    className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
              Guardar borrador
            </Button>
            <Button onClick={testCall} disabled={savingCall || !draft.id}
                    data-testid="agentwiz-testcall"
                    className="btn-cta-grad rounded-sm">
              <PhoneCall size={13} className="mr-1" /> Llamar a mi celular
            </Button>
            <Button onClick={() => save("en_vivo")} disabled={savingCall || !draft.id}
                    data-testid="agentwiz-publish"
                    className="rounded-sm bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/30">
              Publicar en vivo
            </Button>
          </div>
          {testResult && (
            <div data-testid="agentwiz-testresult"
                 className={`text-xs px-3 py-2 rounded-sm border ${
                   testResult.ok
                     ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                     : "border-red-500/40 bg-red-500/10 text-red-200"
                 }`}>
              {testResult.beta && <b>BETA · </b>}{testResult.detail}
            </div>
          )}
        </div>
      )}

      {/* Nav */}
      <div className="flex items-center justify-between mt-6 pt-4 border-t border-zinc-800">
        <Button variant="outline" onClick={back} disabled={step === 0}
                data-testid="agentwiz-back"
                className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
          <CaretLeft size={12} /> Atrás
        </Button>
        {step < STEPS.length - 1 ? (
          <Button onClick={next} disabled={!canNext()}
                  data-testid="agentwiz-next"
                  className="btn-cta-grad rounded-sm">
            Siguiente <CaretRight size={12} />
          </Button>
        ) : (
          <div className="text-[11px] text-zinc-500">Guarda o publica cuando esté listo.</div>
        )}
      </div>
    </div>
  );
}

export default function AgentesPage() {
  const [agents,   setAgents]   = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [creating, setCreating] = useState(false);
  const [editing,  setEditing]  = useState(null);

  const [templates, setTemplates] = useState([]);
  const [tools,     setTools]     = useState([]);
  const [voices,    setVoices]    = useState([]);

  const load = async () => {
    setLoading(true);
    try {
      const [a, t, tl, v] = await Promise.all([
        api.get("/custom-agents"),
        api.get("/custom-agents/templates"),
        api.get("/custom-agents/tools"),
        api.get("/custom-agents/voices"),
      ]);
      setAgents(a.data?.agents || []);
      setTemplates(t.data?.templates || []);
      setTools(tl.data?.tools || []);
      setVoices(v.data?.voices || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "No se pudo cargar.");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const remove = async (id) => {
    if (!window.confirm("¿Borrar este agente?")) return;
    try { await api.delete(`/custom-agents/${id}`); toast.success("Agente borrado."); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "No se pudo borrar."); }
  };

  const activeDraft = useMemo(() => editing || null, [editing]);

  return (
    <Layout title="Agentes"
            subtitle="Crea tu propio agente de voz para rescate, confirmación o cobranza. Beta.">
      <HowItWorks
        testIdPrefix="agentes-howitworks"
        intro="Los 5 agentes operativos (Riesgo, COD, Novedades, Rescate, Analítica) siguen firmes. Aquí construyes agentes propios para casos particulares — como plantillas de Vapi o Retell."
        steps={[
          "Elige una plantilla (rescate, confirmación, citas, cobranza) o parte de cero.",
          "Personaliza el guion con variables tipo {{nombre}} o {{producto}}.",
          "Selecciona la voz y las acciones (herramientas) habilitadas.",
          "Pega tu número y prueba la llamada — Beta: si aún no conectas voz, valida el config.",
        ]}
      />

      {!creating && !editing && (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="text-[10px] uppercase font-mono tracking-widest text-zinc-500">
              {agents.length} agente{agents.length === 1 ? "" : "s"} · BETA
            </div>
            <Button onClick={() => { setCreating(true); setEditing({ ...EMPTY }); }}
                    data-testid="agentes-create-btn"
                    className="btn-cta-grad rounded-sm">
              <Plus size={13} className="mr-1" /> Nuevo agente
            </Button>
          </div>

          {loading && <div className="text-zinc-500 font-mono text-sm">Cargando…</div>}

          {!loading && agents.length === 0 && (
            <div className="border border-dashed border-zinc-800 rounded-sm p-10 text-center bg-zinc-900/30"
                 data-testid="agentes-empty">
              <Robot size={40} className="mx-auto mb-3 text-zinc-600" weight="duotone" />
              <div className="text-lg font-semibold text-white mb-1">Aún no tienes agentes</div>
              <p className="text-sm text-zinc-400 max-w-md mx-auto mb-4">
                Crea el primero — Lyan te guía en 5 pasos.
              </p>
              <Button onClick={() => { setCreating(true); setEditing({ ...EMPTY }); }}
                      data-testid="agentes-empty-create"
                      className="btn-cta-grad rounded-sm">
                Crea el primero
              </Button>
            </div>
          )}

          {!loading && agents.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {agents.map((a) => (
                <div key={a.id}
                     className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-4"
                     data-testid={`agentes-card-${a.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-white truncate">{a.nombre}</div>
                      <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mt-0.5">
                        {a.proposito?.replace("_", " ")} · {a.estado?.replace("_", " ")}
                      </div>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <Button size="sm" variant="outline"
                        onClick={() => { setEditing(a); setCreating(true); }}
                        data-testid={`agentes-edit-${a.id}`}
                        className="h-8 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs">
                        Editar
                      </Button>
                      <button onClick={() => remove(a.id)}
                              data-testid={`agentes-delete-${a.id}`}
                              className="h-8 w-8 grid place-items-center rounded-sm border border-zinc-800 hover:bg-red-500/10 hover:border-red-500/40 text-zinc-500 hover:text-red-300">
                        <Trash size={13} />
                      </button>
                    </div>
                  </div>
                  <p className="text-xs text-zinc-400 mt-3 line-clamp-2">{a.prompt}</p>
                  <div className="mt-3 flex flex-wrap gap-1">
                    {(a.tools || []).slice(0, 6).map((t) => (
                      <span key={t}
                            className="text-[10px] font-mono px-1.5 py-0.5 border border-zinc-700 rounded-sm text-zinc-300">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {creating && (
        <Wizard
          initial={activeDraft}
          templates={templates}
          tools={tools}
          voices={voices}
          onCancel={() => { setCreating(false); setEditing(null); }}
          onSaved={(saved) => { setEditing(saved); load(); }}
        />
      )}
    </Layout>
  );
}
