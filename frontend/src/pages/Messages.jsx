import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { PaperPlaneTilt, ArrowsClockwise, ArrowUpRight, ArrowDownLeft } from "@phosphor-icons/react";
import { toast } from "sonner";

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
