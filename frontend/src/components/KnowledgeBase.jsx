import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import EmptyState from "./EmptyState";
import {
  BookOpenText, FloppyDisk, Plus, TrashSimple, Sparkle, Check, X, Clock, Package, Question,
} from "@phosphor-icons/react";

const FIELD_CLS = "bg-black/40 border-zinc-700 text-white";
const DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const EMPTY = {
  descripcion: "", tono: "", horarios: [], catalogo: [], faqs: [],
  politicas: "", palabras_prohibidas: [], reglas_marca: "",
};
const MAX_ITEMS = 200;

const clean = (kb) => {
  const out = {};
  Object.keys(EMPTY).forEach((k) => {
    const v = kb?.[k];
    out[k] = Array.isArray(EMPTY[k]) ? (Array.isArray(v) ? v : []) : (typeof v === "string" ? v : "");
  });
  out.catalogo = out.catalogo.map((c) => ({
    nombre: c?.nombre || "", precio: c?.precio == null ? "" : String(c.precio), descripcion: c?.descripcion || "",
  }));
  out.faqs = out.faqs.map((f) => ({ pregunta: f?.pregunta || "", respuesta: f?.respuesta || "" }));
  out.horarios = out.horarios.map((h) => ({
    dia: h?.dia || "", abre: h?.abre || "", cierra: h?.cierra || "", cerrado: !!h?.cerrado,
  }));
  return out;
};

function Section({ icon: Icon, title, hint, children, testId, action }) {
  return (
    <section className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-4 md:p-5" data-testid={testId}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            {Icon && <Icon size={16} weight="duotone" className="text-zinc-400" />} {title}
          </h3>
          {hint && <p className="text-xs text-zinc-500 mt-0.5">{hint}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Pestaña «Base de conocimiento»: GET/PUT /kb y POST /kb/suggest. */
export default function KnowledgeBase() {
  const [form, setForm] = useState(EMPTY);
  const [saved, setSaved] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [started, setStarted] = useState(false);
  const [palabra, setPalabra] = useState("");
  // Sugerir con IA
  const [sugOpen, setSugOpen] = useState(false);
  const [sugTexto, setSugTexto] = useState("");
  const [sugBusy, setSugBusy] = useState(false);
  const [propuesta, setPropuesta] = useState(null); // {faqs: [], catalogo: []}

  const load = async () => {
    setLoading(true); setLoadError("");
    try {
      const r = await api.get("/kb");
      const kb = clean(r.data);
      setForm(kb); setSaved(kb);
    } catch (e) {
      setLoadError(errorText(e, "No se pudo cargar la base de conocimiento."));
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(saved), [form, saved]);
  const vacia = useMemo(() => JSON.stringify(saved) === JSON.stringify(EMPTY), [saved]);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const setItem = (lista, i, patch) =>
    set({ [lista]: form[lista].map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  const delItem = (lista, i) => set({ [lista]: form[lista].filter((_, j) => j !== i) });
  const addItem = (lista, item) => {
    if (form[lista].length >= MAX_ITEMS) { toast.error(`Máximo ${MAX_ITEMS} elementos.`); return; }
    set({ [lista]: [...form[lista], item] });
  };

  const addPalabra = () => {
    const nuevas = palabra.split(",").map((p) => p.trim()).filter(Boolean);
    if (!nuevas.length) return;
    const vistas = new Set(form.palabras_prohibidas.map((p) => p.toLowerCase()));
    const out = [...form.palabras_prohibidas];
    nuevas.forEach((p) => { if (!vistas.has(p.toLowerCase())) { vistas.add(p.toLowerCase()); out.push(p); } });
    set({ palabras_prohibidas: out });
    setPalabra("");
  };

  const save = async () => {
    const body = {
      ...form,
      catalogo: form.catalogo.filter((c) => c.nombre.trim())
        .map((c) => ({ ...c, nombre: c.nombre.trim(), precio: String(c.precio || "").trim() || null })),
      faqs: form.faqs.filter((f) => f.pregunta.trim() && f.respuesta.trim()),
      horarios: form.horarios.filter((h) => h.dia.trim())
        .map((h) => ({ dia: h.dia.trim(), cerrado: !!h.cerrado, abre: h.cerrado ? null : (h.abre || null), cierra: h.cerrado ? null : (h.cierra || null) })),
    };
    setSaving(true);
    try {
      const r = await api.put("/kb", body);
      const kb = clean(r.data);
      setForm(kb); setSaved(kb);
      const n = r.data?.agentes_actualizados || 0;
      toast.success(n ? `Guardado. ${n} agente(s) publicado(s) ya usan la información nueva.` : "Base de conocimiento guardada.");
    } catch (e) {
      toast.error(errorText(e, "No se pudo guardar la base de conocimiento."));
    } finally { setSaving(false); }
  };

  const sugerir = async () => {
    if (sugTexto.trim().length < 10) { toast.error("Cuéntanos un poco más de tu negocio."); return; }
    setSugBusy(true);
    try {
      const r = await api.post("/kb/suggest", { texto: sugTexto.trim() }, { timeout: 90000 });
      setPropuesta({ faqs: r.data?.faqs || [], catalogo: r.data?.catalogo || [] });
    } catch (e) {
      toast.error(errorText(e, "No se pudo generar la propuesta."));
    } finally { setSugBusy(false); }
  };
  const aceptar = (lista, i) => {
    const item = propuesta[lista][i];
    if (lista === "faqs") addItem("faqs", { pregunta: item.pregunta || "", respuesta: item.respuesta || "" });
    else addItem("catalogo", { nombre: item.nombre || "", precio: item.precio == null ? "" : String(item.precio), descripcion: item.descripcion || "" });
    descartar(lista, i);
  };
  const descartar = (lista, i) =>
    setPropuesta((p) => ({ ...p, [lista]: p[lista].filter((_, j) => j !== i) }));

  if (loading) return <div className="text-zinc-500 font-mono text-sm" data-testid="kb-loading">Cargando…</div>;
  if (loadError) {
    return (
      <div className="border border-red-500/30 bg-red-500/5 rounded-sm p-4 text-sm text-red-300" data-testid="kb-error">
        {loadError} <button onClick={load} className="underline ml-2">Reintentar</button>
      </div>
    );
  }

  if (vacia && !started && !dirty) {
    return (
      <EmptyState
        icon={BookOpenText}
        testId="kb-empty"
        title="Tu base de conocimiento está vacía"
        description="Escribe aquí lo que tu negocio sabe (horarios, lo que vendes, preguntas frecuentes, políticas). El asistente y tus agentes de voz lo usarán para responder con datos reales."
        action={{ label: "Empezar a llenarla", onClick: () => setStarted(true) }}
        prompt="Ayúdame a llenar mi base de conocimiento: te cuento mi negocio y tú propones las preguntas frecuentes."
      />
    );
  }

  const pendientes = propuesta ? propuesta.faqs.length + propuesta.catalogo.length : 0;

  return (
    <div className="space-y-4 pb-24" data-testid="kb-form">
      {/* Sugerir con IA */}
      <Section icon={Sparkle} title="Sugerir con IA" testId="kb-suggest"
               hint="Pega una descripción de tu negocio y te proponemos preguntas frecuentes y catálogo. Nada se guarda hasta que lo aceptes y pulses Guardar."
               action={!sugOpen && (
                 <Button variant="outline" onClick={() => setSugOpen(true)} data-testid="kb-suggest-open"
                         className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-8 text-xs shrink-0">
                   <Sparkle size={13} className="mr-1" /> Sugerir con IA
                 </Button>
               )}>
        {sugOpen && (
          <div className="space-y-3">
            <Textarea rows={4} value={sugTexto} onChange={(e) => setSugTexto(e.target.value)} maxLength={6000}
                      placeholder="Ej: Somos una pastelería. Vendemos tortas por encargo desde 25 y cupcakes a 3 cada uno. Entregamos a domicilio de martes a domingo…"
                      className={`${FIELD_CLS} text-sm`} data-testid="kb-suggest-text" />
            <div className="flex flex-wrap gap-2">
              <Button onClick={sugerir} disabled={sugBusy} className="btn-cta-grad rounded-sm h-9" data-testid="kb-suggest-run">
                {sugBusy ? "Pensando…" : "Proponer"}
              </Button>
              <Button variant="outline" onClick={() => { setSugOpen(false); setPropuesta(null); }}
                      className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-9">Cerrar</Button>
            </div>
            {propuesta && (
              <div className="space-y-2" data-testid="kb-suggest-result">
                <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500">
                  Propuesta · {pendientes} por revisar
                </div>
                {pendientes === 0 && <p className="text-xs text-zinc-500">No queda nada por revisar.</p>}
                {["faqs", "catalogo"].map((lista) => propuesta[lista].map((it, i) => (
                  <div key={`${lista}-${i}`} className="border border-zinc-800 rounded-sm p-3 bg-black/30 flex items-start gap-3"
                       data-testid={`kb-suggest-item-${lista}-${i}`}>
                    <div className="flex-1 min-w-0 text-sm">
                      <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-0.5">
                        {lista === "faqs" ? "Pregunta frecuente" : "Producto o servicio"}
                      </div>
                      {lista === "faqs" ? (
                        <><div className="text-white break-words">{it.pregunta}</div>
                          <div className="text-zinc-400 break-words">{it.respuesta}</div></>
                      ) : (
                        <><div className="text-white break-words">{it.nombre}{it.precio !== null && it.precio !== "" ? ` · ${it.precio}` : ""}</div>
                          {it.descripcion && <div className="text-zinc-400 break-words">{it.descripcion}</div>}</>
                      )}
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <Button onClick={() => aceptar(lista, i)} title="Aceptar" aria-label="Aceptar"
                              data-testid={`kb-suggest-accept-${lista}-${i}`}
                              className="h-8 w-8 p-0 rounded-sm bg-emerald-600 hover:bg-emerald-500"><Check size={14} /></Button>
                      <Button variant="outline" onClick={() => descartar(lista, i)} title="Descartar" aria-label="Descartar"
                              className="h-8 w-8 p-0 rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800"><X size={14} /></Button>
                    </div>
                  </div>
                )))}
              </div>
            )}
          </div>
        )}
      </Section>

      <Section icon={BookOpenText} title="Sobre el negocio" testId="kb-section-general"
               hint="En pocas frases: qué haces, para quién y cómo quieres que suenen tus agentes.">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Descripción</label>
            <Textarea rows={3} value={form.descripcion} onChange={(e) => set({ descripcion: e.target.value })}
                      className={`${FIELD_CLS} text-sm`} data-testid="kb-descripcion" />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Tono</label>
            <Input value={form.tono} onChange={(e) => set({ tono: e.target.value })} maxLength={300}
                   placeholder="Ej: cercano y respetuoso, tratando de usted" className={FIELD_CLS} data-testid="kb-tono" />
          </div>
        </div>
      </Section>

      <Section icon={Clock} title="Horarios" testId="kb-section-horarios" hint="Un renglón por día. Marca «Cerrado» si ese día no atiendes."
               action={<Button variant="outline" data-testid="kb-add-horario"
                               onClick={() => addItem("horarios", { dia: DIAS[form.horarios.length % 7], abre: "09:00", cierra: "18:00", cerrado: false })}
                               className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-8 text-xs shrink-0"><Plus size={13} className="mr-1" /> Día</Button>}>
        {form.horarios.length === 0 && <p className="text-xs text-zinc-500">Sin horarios todavía.</p>}
        <div className="space-y-2">
          {form.horarios.map((h, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2" data-testid={`kb-horario-${i}`}>
              <select value={h.dia} onChange={(e) => setItem("horarios", i, { dia: e.target.value })}
                      className="h-9 rounded-md bg-black/40 border border-zinc-700 text-white text-sm px-2 w-32">
                {(DIAS.includes(h.dia) ? DIAS : [h.dia, ...DIAS]).map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
              <input type="time" value={h.abre || ""} disabled={h.cerrado} aria-label="Abre"
                     onChange={(e) => setItem("horarios", i, { abre: e.target.value })}
                     className="h-9 rounded-md bg-black/40 border border-zinc-700 text-white text-sm px-2 disabled:opacity-40" />
              <span className="text-zinc-500 text-xs">a</span>
              <input type="time" value={h.cierra || ""} disabled={h.cerrado} aria-label="Cierra"
                     onChange={(e) => setItem("horarios", i, { cierra: e.target.value })}
                     className="h-9 rounded-md bg-black/40 border border-zinc-700 text-white text-sm px-2 disabled:opacity-40" />
              <label className="text-xs text-zinc-300 flex items-center gap-1.5">
                <input type="checkbox" checked={h.cerrado} onChange={(e) => setItem("horarios", i, { cerrado: e.target.checked })} /> Cerrado
              </label>
              <button onClick={() => delItem("horarios", i)} aria-label="Quitar día"
                      className="text-zinc-500 hover:text-red-400 p-1 ml-auto"><TrashSimple size={14} /></button>
            </div>
          ))}
        </div>
      </Section>

      <Section icon={Package} title={`Catálogo · ${form.catalogo.length}`} testId="kb-section-catalogo"
               hint="Productos o servicios con su precio. Lo que no esté aquí, tus agentes no lo inventan."
               action={<Button variant="outline" onClick={() => addItem("catalogo", { nombre: "", precio: "", descripcion: "" })}
                               data-testid="kb-add-producto"
                               className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-8 text-xs shrink-0"><Plus size={13} className="mr-1" /> Producto</Button>}>
        {form.catalogo.length === 0 && <p className="text-xs text-zinc-500">Sin productos todavía.</p>}
        <div className="space-y-2">
          {form.catalogo.map((c, i) => (
            <div key={i} className="grid grid-cols-1 md:grid-cols-[1fr_8rem_1.5fr_auto] gap-2 items-start" data-testid={`kb-producto-${i}`}>
              <Input value={c.nombre} onChange={(e) => setItem("catalogo", i, { nombre: e.target.value })} maxLength={200}
                     placeholder="Nombre" className={FIELD_CLS} />
              <Input value={c.precio} onChange={(e) => setItem("catalogo", i, { precio: e.target.value })} maxLength={40}
                     placeholder="Precio" className={FIELD_CLS} />
              <Input value={c.descripcion} onChange={(e) => setItem("catalogo", i, { descripcion: e.target.value })} maxLength={1000}
                     placeholder="Detalle (opcional)" className={FIELD_CLS} />
              <button onClick={() => delItem("catalogo", i)} aria-label="Quitar producto"
                      className="text-zinc-500 hover:text-red-400 p-2 justify-self-end"><TrashSimple size={14} /></button>
            </div>
          ))}
        </div>
      </Section>

      <Section icon={Question} title={`Preguntas frecuentes · ${form.faqs.length}`} testId="kb-section-faqs"
               hint="Lo que más te preguntan y la respuesta que quieres que se dé."
               action={<Button variant="outline" onClick={() => addItem("faqs", { pregunta: "", respuesta: "" })}
                               data-testid="kb-add-faq"
                               className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-8 text-xs shrink-0"><Plus size={13} className="mr-1" /> Pregunta</Button>}>
        {form.faqs.length === 0 && <p className="text-xs text-zinc-500">Sin preguntas todavía.</p>}
        <div className="space-y-3">
          {form.faqs.map((f, i) => (
            <div key={i} className="flex gap-2 items-start" data-testid={`kb-faq-${i}`}>
              <div className="flex-1 space-y-1.5 min-w-0">
                <Input value={f.pregunta} onChange={(e) => setItem("faqs", i, { pregunta: e.target.value })} maxLength={500}
                       placeholder="Pregunta" className={FIELD_CLS} />
                <Textarea rows={2} value={f.respuesta} onChange={(e) => setItem("faqs", i, { respuesta: e.target.value })} maxLength={2000}
                          placeholder="Respuesta" className={`${FIELD_CLS} text-sm`} />
              </div>
              <button onClick={() => delItem("faqs", i)} aria-label="Quitar pregunta"
                      className="text-zinc-500 hover:text-red-400 p-2"><TrashSimple size={14} /></button>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Políticas y marca" testId="kb-section-politicas"
               hint="Devoluciones, pagos, garantías… y cómo debe hablar tu marca.">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Políticas</label>
            <Textarea rows={3} value={form.politicas} onChange={(e) => set({ politicas: e.target.value })}
                      className={`${FIELD_CLS} text-sm`} data-testid="kb-politicas" />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Reglas de marca</label>
            <Textarea rows={2} value={form.reglas_marca} onChange={(e) => set({ reglas_marca: e.target.value })}
                      placeholder="Ej: nunca prometer fechas exactas; despedirse con «gracias por preferirnos»."
                      className={`${FIELD_CLS} text-sm`} data-testid="kb-reglas" />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Palabras que no se deben usar</label>
            <div className="flex gap-2">
              <Input value={palabra} onChange={(e) => setPalabra(e.target.value)}
                     onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addPalabra(); } }}
                     placeholder="Escribe una o varias separadas por coma" className={FIELD_CLS} data-testid="kb-palabra-input" />
              <Button variant="outline" onClick={addPalabra} data-testid="kb-palabra-add"
                      className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 shrink-0">Agregar</Button>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2" data-testid="kb-palabras">
              {form.palabras_prohibidas.map((p, i) => (
                <span key={`${p}-${i}`} className="inline-flex items-center gap-1 text-xs bg-zinc-800 border border-zinc-700 rounded-sm px-2 py-1 text-zinc-200">
                  {p}
                  <button onClick={() => set({ palabras_prohibidas: form.palabras_prohibidas.filter((_, j) => j !== i) })}
                          aria-label={`Quitar ${p}`} className="text-zinc-500 hover:text-red-400"><X size={11} /></button>
                </span>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* Barra fija de guardado */}
      <div className="fixed bottom-0 left-0 right-0 md:left-64 z-30 border-t border-zinc-800 bg-zinc-950/95 backdrop-blur px-4 md:px-8 py-3 flex items-center justify-between gap-3"
           data-testid="kb-savebar" data-bottom-bar>
        <span className="text-xs text-zinc-400 truncate">
          {dirty ? "Tienes cambios sin guardar." : "Todo guardado."}
        </span>
        <div className="flex gap-2 shrink-0">
          {dirty && (
            <Button variant="outline" onClick={() => setForm(saved)} disabled={saving}
                    className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-9">Descartar</Button>
          )}
          <Button onClick={save} disabled={saving || !dirty} className="btn-cta-grad rounded-sm h-9" data-testid="kb-save">
            <FloppyDisk size={15} className="mr-1.5" /> {saving ? "Guardando…" : "Guardar"}
          </Button>
        </div>
      </div>
    </div>
  );
}
