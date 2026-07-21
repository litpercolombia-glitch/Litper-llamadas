import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api, formatDateTime } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Sparkle, Plus, TrashSimple, Lock } from "@phosphor-icons/react";
import { toast } from "sonner";

const EMPTY = { name: "", trigger: "", description: "", instructions: "", steps: [] };

export default function SkillsPage() {
  const [skills, setSkills] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);

  const load = async () => {
    const r = await api.get("/skills");
    setSkills(r.data || []);
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name || !form.trigger || !form.instructions)
      return toast.error("Nombre, trigger e instrucciones son obligatorios.");
    try {
      await api.post("/skills", form);
      setOpen(false); setForm(EMPTY);
      toast.success("Skill creada");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
  };

  const remove = async (id) => {
    try { await api.delete(`/skills/${id}`); toast.success("Skill eliminada"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || e.message); }
  };

  return (
    <Layout title="Habilidades del Copilot" subtitle={`${skills.length} skills reutilizables para Marcus`}
      actions={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-white text-black hover:bg-zinc-200 rounded-sm" data-testid="skills-new">
              <Plus size={14} className="mr-1" /> Nueva skill
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-950 border-zinc-800 rounded-sm max-w-2xl">
            <DialogHeader><DialogTitle>Nueva skill</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">Nombre</label>
                  <Input data-testid="skill-form-name"
                    className="bg-zinc-900 border-zinc-800 rounded-sm"
                    value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />
                </div>
                <div>
                  <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">Trigger (slash-command)</label>
                  <Input data-testid="skill-form-trigger"
                    className="bg-zinc-900 border-zinc-800 rounded-sm font-mono"
                    placeholder="ej. revisar-cola"
                    value={form.trigger} onChange={(e) => setForm(f => ({ ...f, trigger: e.target.value }))} />
                </div>
              </div>
              <div>
                <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">Descripción</label>
                <Input className="bg-zinc-900 border-zinc-800 rounded-sm"
                  value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <div>
                <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">Instrucciones para Marcus</label>
                <Textarea data-testid="skill-form-instructions"
                  className="bg-zinc-900 border-zinc-800 rounded-sm min-h-32"
                  placeholder="Explica paso a paso qué hacer, qué tools llamar, qué reportar…"
                  value={form.instructions} onChange={(e) => setForm(f => ({ ...f, instructions: e.target.value }))} />
              </div>
              <Button onClick={create} data-testid="skill-form-submit"
                className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm">Crear skill</Button>
            </div>
          </DialogContent>
        </Dialog>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {skills.length === 0 && (
          <div className="col-span-2 border border-dashed border-zinc-800 p-10 text-center">
            <Sparkle size={32} weight="duotone" className="mx-auto text-zinc-600 mb-3" />
            <p className="text-zinc-400">Aún no hay skills.</p>
          </div>
        )}
        {skills.map(s => (
          <div key={s.id} className="border border-zinc-800 bg-zinc-900/50 p-5 rounded-sm"
               data-testid={`skill-card-${s.id}`}>
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Sparkle size={14} className="text-zinc-500" />
                  <h3 className="text-lg font-semibold text-white">{s.name}</h3>
                  {s.is_seed && (
                    <Lock size={11} className="text-zinc-500" title="Skill semilla (protegida)" />
                  )}
                </div>
                <div className="font-mono text-xs text-zinc-500">/{s.trigger}</div>
              </div>
              {!s.is_seed && (
                <Button variant="ghost" size="sm" onClick={() => remove(s.id)}
                  data-testid={`skill-delete-${s.id}`}
                  className="text-red-400 hover:bg-red-500/10 rounded-sm h-7">
                  <TrashSimple size={12} />
                </Button>
              )}
            </div>
            {s.description && <p className="text-sm text-zinc-400 mb-3">{s.description}</p>}
            <div className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 mb-1">Instrucciones</div>
            <div className="text-xs text-zinc-300 font-mono whitespace-pre-wrap break-words border-l-2 border-zinc-800 pl-3">
              {s.instructions.length > 300 ? s.instructions.slice(0, 300) + "…" : s.instructions}
            </div>
            <div className="text-[10px] font-mono text-zinc-500 mt-3">{formatDateTime(s.created_at)}</div>
          </div>
        ))}
      </div>
    </Layout>
  );
}
