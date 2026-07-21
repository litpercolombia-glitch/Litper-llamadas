import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { toast } from "sonner";
import {
  Sparkle, FloppyDisk, Play, Plus, Trash, Copy, Robot, Globe,
  Package, MegaphoneSimple, MagicWand as Wand,
} from "@phosphor-icons/react";

const ALL_VARS = [
  "customer_first_name", "product_name", "carrier_name", "city",
  "office_address", "days_left", "deadline_text", "total_to_pay",
  "guia", "promo_name", "promo_price",
];

const SCOPE_ICONS = { global: Globe, product: Package, campaign: MegaphoneSimple };

// ---------------------------------------------------------------------------
export default function PromptsPage() {
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [selected, setSelected] = useState(null);
  const [mode, setMode] = useState("paste"); // 'paste' | 'generate'
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [p, pr] = await Promise.all([
        api.get("/prompts"),
        api.get("/products").catch(() => ({ data: [] })),
      ]);
      setItems(p.data || []);
      setProducts(pr.data || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const newDraft = () => ({
    name: "", scope: "global", country: "CO",
    product_id: null, campaign_key: null,
    system_prompt: "", first_message: "",
    variables: ALL_VARS, voice_id: null, active: true, priority: 50,
  });

  const startNew = () => { setSelected(newDraft()); setMode("paste"); };
  const startGenerate = () => { setSelected(newDraft()); setMode("generate"); };

  const save = async () => {
    if (!selected) return;
    if (!selected.name?.trim() || !selected.system_prompt?.trim()) {
      toast.error("Nombre y system prompt son obligatorios."); return;
    }
    try {
      if (selected.id) {
        await api.patch(`/prompts/${selected.id}`, selected);
        toast.success("Prompt actualizado.");
      } else {
        const r = await api.post("/prompts", selected);
        setSelected(r.data);
        toast.success("Prompt creado.");
      }
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error guardando.");
    }
  };

  const del = async (id) => {
    if (!window.confirm("¿Eliminar prompt?")) return;
    await api.delete(`/prompts/${id}`);
    if (selected?.id === id) setSelected(null);
    load();
  };

  return (
    <Layout
      title="Prompts de Sofía"
      subtitle="Global · Producto · Campaña — la campaña gana sobre producto, y producto sobre global."
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={startGenerate} data-testid="prompt-generate-btn">
            <Wand size={14} /> Generar con IA
          </Button>
          <Button onClick={startNew} data-testid="prompt-new-btn">
            <Plus size={14} /> Nuevo prompt
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        {/* LEFT: list */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 backdrop-blur-md overflow-hidden">
          <div className="px-3 py-2 border-b border-zinc-800 text-[10px] font-mono uppercase tracking-widest text-zinc-500">
            Prompts ({items.length})
          </div>
          <div className="max-h-[70vh] overflow-y-auto divide-y divide-zinc-800">
            {loading && <div className="p-4 text-xs text-zinc-500">Cargando…</div>}
            {!loading && items.length === 0 && (
              <div className="p-4 text-xs text-zinc-500">Aún no hay prompts.</div>
            )}
            {items.map((p) => {
              const Icon = SCOPE_ICONS[p.scope] || Globe;
              const isSel = selected?.id === p.id;
              return (
                <button key={p.id}
                  className={`w-full text-left px-3 py-2.5 hover:bg-zinc-800/50 transition ${isSel ? "bg-zinc-800/70" : ""}`}
                  onClick={() => { setSelected(p); setMode("paste"); }}
                  data-testid={`prompt-item-${p.id}`}>
                  <div className="flex items-start gap-2">
                    <Icon size={14} className="text-zinc-400 mt-0.5" weight="duotone" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white truncate">{p.name}</div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        <Badge variant="outline" className="text-[9px] py-0 px-1.5">{p.scope}</Badge>
                        {p.country && <Badge variant="outline" className="text-[9px] py-0 px-1.5">{p.country}</Badge>}
                        {p.campaign_key && <Badge variant="outline" className="text-[9px] py-0 px-1.5">{p.campaign_key}</Badge>}
                        {!p.active && <Badge variant="outline" className="text-[9px] py-0 px-1.5 text-zinc-500">inactivo</Badge>}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* RIGHT: editor */}
        <div>
          {!selected && (
            <div className="rounded-lg border border-dashed border-zinc-700 p-10 text-center text-zinc-500 text-sm">
              Selecciona un prompt o crea uno nuevo. <br/>
              <span className="text-zinc-400">Sofía habla en colombiano, &lt;60s, NUNCA "impermeable" → "antifluido".</span>
            </div>
          )}
          {selected && (
            <PromptEditor
              value={selected}
              onChange={setSelected}
              onSave={save}
              onDelete={selected.id ? () => del(selected.id) : null}
              mode={mode}
              onModeChange={setMode}
              products={products}
            />
          )}
        </div>
      </div>
    </Layout>
  );
}

// ---------------------------------------------------------------------------
function PromptEditor({ value, onChange, onSave, onDelete, mode, onModeChange, products }) {
  const [genForm, setGenForm] = useState({
    product: "", beneficios: "", objeciones: "", transportadora: "",
    tono: "colombiano cálido y directo", country: value.country || "CO",
  });
  const [generating, setGenerating] = useState(false);
  const [previewVars, setPreviewVars] = useState({
    customer_first_name: "María",
    product_name: "Protector Antifluido Premium + 2 Fundas",
    carrier_name: "Servientrega",
    city: "Medellín",
    office_address: "Cra 50 #10-20",
    days_left: "3",
    deadline_text: "hasta el jueves",
    total_to_pay: "$150.000",
    guia: "SGT-987",
    promo_name: "Protector Antifluido Premium + 2 Fundas",
    promo_price: "$149.000",
  });

  const rendered = useMemo(() => {
    let sp = value.system_prompt || "";
    let fm = value.first_message || "";
    for (const [k, v] of Object.entries(previewVars)) {
      sp = sp.replaceAll("{" + k + "}", v);
      fm = fm.replaceAll("{" + k + "}", v);
    }
    return { sp, fm };
  }, [value, previewVars]);

  const generate = async () => {
    if (!genForm.product.trim()) { toast.error("Producto es obligatorio."); return; }
    setGenerating(true);
    try {
      const r = await api.post("/prompts/generate", genForm);
      onChange({ ...value,
                 system_prompt: r.data.system_prompt,
                 first_message: r.data.first_message });
      toast.success(`Generado con ${r.data.model_used}. Revísalo y guarda.`);
      onModeChange("paste");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error generando.");
    } finally { setGenerating(false); }
  };

  const testVoice = async () => {
    const text = value.first_message || rendered.fm || "Hola, soy Sofía.";
    try {
      const res = await api.post("/prompts/test-voice",
        { voice_id: value.voice_id || "", text: text.slice(0, 300) },
        { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = new Audio(url); a.play();
      toast.success("Reproduciendo preview…");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Elige una voz primero (o define ELEVENLABS_DEFAULT_VOICE_ID).");
    }
  };

  const insertVar = (v) => {
    const needle = "{" + v + "}";
    onChange({ ...value, system_prompt: (value.system_prompt || "") + " " + needle });
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 backdrop-blur-md p-5 space-y-4"
      data-testid="prompt-editor">
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        <Robot size={18} className="text-zinc-300" />
        <Input placeholder="Nombre del prompt"
          value={value.name || ""}
          onChange={(e) => onChange({ ...value, name: e.target.value })}
          className="flex-1 min-w-[240px]" data-testid="prompt-name" />
        <label className="text-xs text-zinc-400 flex items-center gap-2">
          <input type="checkbox" checked={value.active !== false}
            onChange={(e) => onChange({ ...value, active: e.target.checked })} />
          Activo
        </label>
      </div>

      {/* Scope row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div>
          <label className="text-[10px] uppercase text-zinc-500 font-mono">Scope</label>
          <Select value={value.scope} onValueChange={(v) => onChange({ ...value, scope: v })}>
            <SelectTrigger data-testid="prompt-scope"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="global">Global (país)</SelectItem>
              <SelectItem value="product">Producto</SelectItem>
              <SelectItem value="campaign">Campaña</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[10px] uppercase text-zinc-500 font-mono">País</label>
          <Select value={value.country || "CO"} onValueChange={(v) => onChange({ ...value, country: v })}>
            <SelectTrigger data-testid="prompt-country"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="CO">Colombia</SelectItem>
              <SelectItem value="EC">Ecuador</SelectItem>
              <SelectItem value="CL">Chile</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {value.scope === "product" && (
          <div className="col-span-2">
            <label className="text-[10px] uppercase text-zinc-500 font-mono">Producto</label>
            <Select value={value.product_id || ""} onValueChange={(v) => onChange({ ...value, product_id: v })}>
              <SelectTrigger data-testid="prompt-product"><SelectValue placeholder="Elegir producto" /></SelectTrigger>
              <SelectContent>
                {products.map((p) => <SelectItem key={p.id} value={p.id}>{p.nombre}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
        {value.scope === "campaign" && (
          <div className="col-span-2">
            <label className="text-[10px] uppercase text-zinc-500 font-mono">Campaña / carrier slug</label>
            <Input value={value.campaign_key || ""}
              onChange={(e) => onChange({ ...value, campaign_key: e.target.value })}
              placeholder="ej. servientrega, envia, blackfriday"
              data-testid="prompt-campaign-key" />
          </div>
        )}
        <div>
          <label className="text-[10px] uppercase text-zinc-500 font-mono">Prioridad</label>
          <Input type="number" value={value.priority || 0}
            onChange={(e) => onChange({ ...value, priority: +e.target.value || 0 })}
            data-testid="prompt-priority" />
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={mode} onValueChange={onModeChange}>
        <TabsList data-testid="prompt-tabs">
          <TabsTrigger value="paste" data-testid="prompt-tab-paste">Pegar</TabsTrigger>
          <TabsTrigger value="generate" data-testid="prompt-tab-generate">Generar con IA</TabsTrigger>
        </TabsList>

        {/* Paste */}
        <TabsContent value="paste" className="space-y-3">
          <div>
            <label className="text-[10px] uppercase text-zinc-500 font-mono">First message (opcional)</label>
            <Input value={value.first_message || ""}
              onChange={(e) => onChange({ ...value, first_message: e.target.value })}
              placeholder="Hola, ¿hablo con {customer_first_name}? Soy Sofía..."
              data-testid="prompt-first-message" />
          </div>
          <div>
            <label className="text-[10px] uppercase text-zinc-500 font-mono">System prompt</label>
            <Textarea rows={16} value={value.system_prompt || ""}
              onChange={(e) => onChange({ ...value, system_prompt: e.target.value })}
              placeholder="Eres Sofía... < 60s ... antifluido ... {product_name} en {carrier_name} ..."
              className="font-mono text-xs"
              data-testid="prompt-system" />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase text-zinc-500 mb-1.5">
              Variables permitidas (haz clic para insertar)
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ALL_VARS.map((v) => (
                <button key={v} onClick={() => insertVar(v)}
                  className="zx-skill-chip" data-testid={`prompt-var-${v}`}>
                  <Copy size={10} /> {"{" + v + "}"}
                </button>
              ))}
            </div>
          </div>

          {/* Preview */}
          <div className="pt-3 border-t border-zinc-800">
            <div className="text-[10px] font-mono uppercase text-zinc-500 mb-2">
              Vista previa con datos de ejemplo — María · Servientrega · Medellín · guía SGT-987
            </div>
            <div className="rounded border border-zinc-800 bg-zinc-950/60 p-3 space-y-2 max-h-64 overflow-y-auto">
              {rendered.fm && (
                <div>
                  <div className="text-[10px] text-zinc-500 mb-1">First message (renderizado)</div>
                  <div className="text-xs text-emerald-200" data-testid="prompt-preview-first">{rendered.fm}</div>
                </div>
              )}
              <div>
                <div className="text-[10px] text-zinc-500 mb-1">System prompt (renderizado)</div>
                <pre className="text-[11px] text-zinc-200 whitespace-pre-wrap font-mono" data-testid="prompt-preview-system">{rendered.sp}</pre>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Generate */}
        <TabsContent value="generate" className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Input placeholder="Producto (ej. Protector Antifluido Premium)"
              value={genForm.product}
              onChange={(e) => setGenForm({ ...genForm, product: e.target.value })}
              data-testid="gen-product" />
            <Input placeholder="Transportadora principal (opcional)"
              value={genForm.transportadora}
              onChange={(e) => setGenForm({ ...genForm, transportadora: e.target.value })}
              data-testid="gen-carrier" />
          </div>
          <Textarea rows={3} placeholder="Beneficios (uno por línea)"
            value={genForm.beneficios}
            onChange={(e) => setGenForm({ ...genForm, beneficios: e.target.value })}
            data-testid="gen-beneficios" />
          <Textarea rows={3} placeholder="Objeciones frecuentes"
            value={genForm.objeciones}
            onChange={(e) => setGenForm({ ...genForm, objeciones: e.target.value })}
            data-testid="gen-objeciones" />
          <Input placeholder="Tono"
            value={genForm.tono}
            onChange={(e) => setGenForm({ ...genForm, tono: e.target.value })}
            data-testid="gen-tono" />
          <Button disabled={generating} onClick={generate}
            className="btn-cta-grad" data-testid="gen-submit">
            <Sparkle size={14} weight="fill" />
            {generating ? "Generando…" : "Generar con IA"}
          </Button>
          <p className="text-[11px] text-zinc-500">
            El LLM (Groq por defecto) escribe un system prompt completo siguiendo el flujo LIT-LOG-RO (identidad → oficina → urgencia → fecha → extensión → guía).
          </p>
        </TabsContent>
      </Tabs>

      {/* Actions */}
      <div className="flex justify-between items-center pt-3 border-t border-zinc-800">
        <div>
          {onDelete && (
            <Button variant="ghost" onClick={onDelete}
              className="text-red-400 hover:text-red-300" data-testid="prompt-delete">
              <Trash size={14} /> Eliminar
            </Button>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={testVoice} data-testid="prompt-test-voice">
            <Play size={14} /> Probar voz
          </Button>
          <Button className="btn-cta-grad" onClick={onSave} data-testid="prompt-save">
            <FloppyDisk size={14} /> Guardar
          </Button>
        </div>
      </div>
    </div>
  );
}
