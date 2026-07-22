import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { PaperPlaneTilt, ArrowsClockwise, ArrowUpRight, ArrowDownLeft, WhatsappLogo, Warning } from "@phosphor-icons/react";
import { toast } from "sonner";

// ----- WA Template Rules panel -----
function WhatsappRulesPanel() {
  const [templates, setTemplates] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [t, r] = await Promise.all([
        api.get("/whatsapp/templates").catch(() => ({ data: { templates: [] } })),
        api.get("/whatsapp/rules"),
      ]);
      setTemplates((t.data?.templates || []).map((x) => x.name || x.template_name || x).filter(Boolean));
      setRules(r.data || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const [syncing, setSyncing] = useState(false);
  const syncTemplates = async () => {
    setSyncing(true);
    try {
      const r = await api.post("/whatsapp/templates/sync");
      const d = r.data || {};
      if (d.ok) toast.success(d.detail || "Las 3 plantillas requeridas están aprobadas.");
      else toast.error(d.detail || "Faltan plantillas por aprobar.");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error consultando Chatea Pro.");
    } finally { setSyncing(false); }
  };

  const patch = async (id, body) => {
    await api.patch(`/whatsapp/rules/${id}`, body);
    load();
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 backdrop-blur-md p-4 mb-4"
      data-testid="wa-rules-panel">
      <div className="flex items-center gap-2 mb-3">
        <WhatsappLogo size={16} className="text-green-400" weight="duotone" />
        <h3 className="text-sm font-semibold text-white">Reglas de plantillas WhatsApp</h3>
        <span className="text-[10px] font-mono text-zinc-500 ml-auto mr-2">
          {templates.length > 0
            ? `${templates.length} plantillas Chatea Pro detectadas`
            : "Chatea Pro no configurado o sin plantillas"}
        </span>
        <Button size="sm" variant="outline" onClick={syncTemplates} disabled={syncing}
          data-testid="wa-templates-sync">
          {syncing ? "…" : "Sincronizar plantillas"}
        </Button>
      </div>
      <div className="text-xs text-zinc-400 mb-3">
        <Warning size={11} className="inline text-amber-400 mr-1" />
        La regla se aplica automáticamente al enviar el fallback WhatsApp según <b>días restantes en oficina</b>.
      </div>
      <div className="space-y-2">
        {loading && <div className="text-xs text-zinc-500">Cargando reglas…</div>}
        {rules.map((r) => (
          <div key={r.id} className="border border-zinc-800 rounded p-3 grid grid-cols-1 md:grid-cols-[160px_1fr_1fr_100px] gap-2 items-center"
            data-testid={`wa-rule-${r.rule_key}`}>
            <div>
              <div className="text-xs text-white font-semibold">{r.rule_key}</div>
              <div className="text-[10px] font-mono text-zinc-500">
                {r.days_min}–{r.days_max === 99 ? "+" : r.days_max} días
              </div>
            </div>
            <div>
              <label className="text-[10px] uppercase text-zinc-500 font-mono">Plantilla Chatea Pro</label>
              {templates.length > 0 ? (
                <select
                  className="w-full bg-zinc-950 border border-zinc-800 rounded text-xs px-2 py-1.5 text-white"
                  value={r.template_name}
                  onChange={(e) => patch(r.id, { template_name: e.target.value })}
                  data-testid={`wa-rule-template-${r.rule_key}`}>
                  {!templates.includes(r.template_name) && (
                    <option value={r.template_name}>{r.template_name} (no en Chatea)</option>
                  )}
                  {templates.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              ) : (
                <Input value={r.template_name} onChange={(e) => patch(r.id, { template_name: e.target.value })}
                  className="h-8 text-xs" data-testid={`wa-rule-template-${r.rule_key}`} />
              )}
            </div>
            <div>
              <label className="text-[10px] uppercase text-zinc-500 font-mono">Media URL (imagen)</label>
              <Input value={r.media_url || ""} placeholder="https://…"
                onChange={(e) => patch(r.id, { media_url: e.target.value })}
                className="h-8 text-xs" data-testid={`wa-rule-media-${r.rule_key}`} />
            </div>
            <label className="text-xs text-zinc-400 flex items-center gap-2">
              <input type="checkbox" checked={r.active !== false}
                onChange={(e) => patch(r.id, { active: e.target.checked })}
                data-testid={`wa-rule-active-${r.rule_key}`} />
              Activa
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MessagesPage() {
  const [msgs, setMsgs] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ phone: "", text: "" });

  const load = async () => {
    const r = await api.get("/whatsapp/messages", { params: { limit: 200 } });
    setMsgs(r.data || []);
  };
  useEffect(() => { load(); }, []);

  const send = async () => {
    if (!form.phone || !form.text) return toast.error("Teléfono y texto son obligatorios.");
    try {
      const r = await api.post("/whatsapp/send", { phone: form.phone, text: form.text });
      setOpen(false); setForm({ phone: "", text: "" });
      toast.success(r.data.status === "sent" ? "Mensaje enviado" : `Fallo: ${r.data.error || "-"}`);
      load();
    } catch (e) { toast.error(e.message); }
  };

  return (
    <Layout title="Bitácora de Mensajes" subtitle={`${msgs.length} mensajes WhatsApp (Chatea Pro)`}
      actions={
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={load} className="border-zinc-700 rounded-sm bg-transparent">
            <ArrowsClockwise size={14} />
          </Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-white text-black hover:bg-zinc-200 rounded-sm" data-testid="messages-new">
                <PaperPlaneTilt size={14} className="mr-1" /> Enviar WhatsApp
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-950 border-zinc-800 rounded-sm">
              <DialogHeader><DialogTitle>Nuevo mensaje</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div>
                  <label className="text-xs uppercase font-mono tracking-widest text-zinc-500 block mb-1">Teléfono</label>
                  <Input data-testid="messages-form-phone"
                    className="bg-zinc-900 border-zinc-800 rounded-sm"
                    placeholder="+573001234567"
                    value={form.phone}
                    onChange={(e) => setForm(f => ({ ...f, phone: e.target.value }))} />
                </div>
                <div>
                  <label className="text-xs uppercase font-mono tracking-widest text-zinc-500 block mb-1">Mensaje</label>
                  <Textarea data-testid="messages-form-text"
                    className="bg-zinc-900 border-zinc-800 rounded-sm"
                    value={form.text}
                    onChange={(e) => setForm(f => ({ ...f, text: e.target.value }))} />
                </div>
                <Button onClick={send} data-testid="messages-form-submit"
                  className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm">Enviar</Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      }
    >
      <WhatsappRulesPanel />
      <div className="border border-zinc-800 bg-zinc-900/40 divide-y divide-zinc-800">
        {msgs.length === 0 && (
          <div className="py-8 text-center text-zinc-500 text-sm">Sin mensajes aún.</div>
        )}
        {msgs.map((m) => {
          const out = m.direction === "outbound";
          return (
            <div key={m.id} className={`p-4 flex ${out ? "justify-end" : "justify-start"}`}
                 data-testid={`message-${m.id}`}>
              <div className={`max-w-lg border rounded-sm p-3 ${
                  out ? "bg-zinc-800 border-zinc-700"
                      : "bg-zinc-900 border-zinc-800"
                }`}>
                <div className="flex items-center gap-2 mb-1">
                  {out ? <ArrowUpRight size={12} className="text-blue-400" />
                       : <ArrowDownLeft size={12} className="text-green-400" />}
                  <span className="text-[10px] uppercase font-mono tracking-widest text-zinc-500">
                    {out ? "Enviado" : "Recibido"} · {m.status}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-500 ml-auto">{formatDateTime(m.created_at)}</span>
                </div>
                <div className="text-xs font-mono text-zinc-400 mb-1">{m.phone}</div>
                <div className="text-sm text-zinc-100 whitespace-pre-wrap break-words">{m.body || "—"}</div>
                {m.error && <div className="text-xs text-red-400 mt-1">Error: {m.error}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </Layout>
  );
}
