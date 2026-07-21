import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Microphone, Plus, TrashSimple, Star } from "@phosphor-icons/react";
import { toast } from "sonner";

const COUNTRIES = ["CO", "EC", "CL", "OTHER"];
const LANGS = ["es-CO", "es-EC", "es-CL", "es-MX", "es-AR", "es", "en", "pt"];

const EMPTY = { name: "", elevenlabs_voice_id: "", language: "es-CO", country: "CO",
                is_default: false, description: "" };

export default function VoicesPage() {
  const [voices, setVoices] = useState([]);
  const [available, setAvailable] = useState({ ok: false, voices: [] });
  const [form, setForm] = useState(EMPTY);
  const [open, setOpen] = useState(false);

  const load = async () => {
    const [v, a] = await Promise.all([
      api.get("/voices"),
      api.get("/voices/elevenlabs/available").catch(() => ({ data: { ok: false, voices: [] } })),
    ]);
    setVoices(v.data || []);
    setAvailable(a.data || { ok: false, voices: [] });
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name || !form.elevenlabs_voice_id) return toast.error("Nombre y voice_id son obligatorios");
    try {
      await api.post("/voices", form);
      setOpen(false); setForm(EMPTY);
      toast.success("Voz registrada");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
  };

  const setDefault = async (v) => {
    try {
      await api.put(`/voices/${v.id}`, { is_default: true, country: v.country });
      toast.success(`${v.name} es la voz por defecto de ${v.country}`);
      load();
    } catch (e) { toast.error(e.message); }
  };

  const remove = async (id) => {
    try { await api.delete(`/voices/${id}`); load(); toast.success("Voz eliminada"); }
    catch (e) { toast.error(e.message); }
  };

  return (
    <Layout title="Voces de IA" subtitle={`${voices.length}/6 voces registradas · Selección por país`}
      actions={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-white text-black hover:bg-zinc-200 rounded-sm" data-testid="voices-new"
              disabled={voices.length >= 6}>
              <Plus size={14} className="mr-1" /> Nueva voz
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-950 border-zinc-800 rounded-sm max-w-lg">
            <DialogHeader><DialogTitle>Registrar voz</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div>
                <label className="text-xs uppercase font-mono tracking-widest text-zinc-500 block mb-1">Nombre</label>
                <Input data-testid="voice-form-name" className="bg-zinc-900 border-zinc-800 rounded-sm"
                  placeholder="Sofía CO" value={form.name}
                  onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs uppercase font-mono tracking-widest text-zinc-500 block mb-1">Voice ID (ElevenLabs)</label>
                {available.ok && available.voices.length > 0 ? (
                  <Select value={form.elevenlabs_voice_id}
                    onValueChange={(v) => setForm(f => ({ ...f, elevenlabs_voice_id: v }))}>
                    <SelectTrigger data-testid="voice-form-eleven" className="bg-zinc-900 border-zinc-800 rounded-sm">
                      <SelectValue placeholder="Selecciona una voz de tu cuenta" />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-zinc-800 max-h-72">
                      {available.voices.map(v => (
                        <SelectItem key={v.voice_id} value={v.voice_id}>
                          {v.name} · {v.category || "-"}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input data-testid="voice-form-eleven" className="bg-zinc-900 border-zinc-800 rounded-sm font-mono"
                    placeholder="21m00Tcm4TlvDq8ikWAM"
                    value={form.elevenlabs_voice_id}
                    onChange={(e) => setForm(f => ({ ...f, elevenlabs_voice_id: e.target.value }))} />
                )}
                {!available.ok && (
                  <p className="text-[11px] text-zinc-500 mt-1 font-mono">
                    Configura ELEVENLABS_API_KEY en backend/.env para elegir de un dropdown.
                  </p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs uppercase font-mono tracking-widest text-zinc-500 block mb-1">País</label>
                  <Select value={form.country} onValueChange={(v) => setForm(f => ({ ...f, country: v }))}>
                    <SelectTrigger className="bg-zinc-900 border-zinc-800 rounded-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-zinc-800">
                      {COUNTRIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs uppercase font-mono tracking-widest text-zinc-500 block mb-1">Idioma</label>
                  <Select value={form.language} onValueChange={(v) => setForm(f => ({ ...f, language: v }))}>
                    <SelectTrigger className="bg-zinc-900 border-zinc-800 rounded-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-zinc-800">
                      {LANGS.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <label className="text-xs uppercase font-mono tracking-widest text-zinc-500 block mb-1">Descripción</label>
                <Textarea className="bg-zinc-900 border-zinc-800 rounded-sm" value={form.description}
                  onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={form.is_default} onCheckedChange={(v) => setForm(f => ({ ...f, is_default: v }))}
                  data-testid="voice-form-default" />
                <label className="text-xs text-zinc-300">Marcar como voz por defecto de este país</label>
              </div>
              <Button onClick={create} data-testid="voice-form-submit"
                className="w-full bg-white text-black hover:bg-zinc-200 rounded-sm">Guardar</Button>
            </div>
          </DialogContent>
        </Dialog>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {voices.length === 0 && (
          <div className="col-span-2 border border-dashed border-zinc-800 p-10 text-center">
            <Microphone size={32} weight="duotone" className="mx-auto text-zinc-600 mb-3" />
            <p className="text-zinc-400 mb-2">Aún no has registrado voces.</p>
            <p className="text-xs text-zinc-500 font-mono">
              Registra hasta 6 voces de ElevenLabs, una por país (CO / EC / CL).
            </p>
          </div>
        )}
        {voices.map(v => (
          <div key={v.id} className={`border rounded-sm p-5 ${
            v.is_default ? "border-white/40 bg-zinc-900" : "border-zinc-800 bg-zinc-900/50"
          }`} data-testid={`voice-card-${v.id}`}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-lg font-semibold text-white">{v.name}</h3>
                <p className="text-xs font-mono text-zinc-500">{v.country} · {v.language}</p>
              </div>
              {v.is_default && (
                <span className="border border-white/40 bg-white/10 px-2 py-0.5 rounded-sm text-[10px] uppercase tracking-widest font-mono text-white">
                  <Star size={10} className="inline mr-1" weight="fill" /> Por defecto
                </span>
              )}
            </div>
            <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1">Voice ID</div>
            <div className="font-mono text-xs text-zinc-300 break-all mb-3">{v.elevenlabs_voice_id}</div>
            {v.description && <p className="text-sm text-zinc-400 mb-3">{v.description}</p>}
            <div className="flex gap-2">
              {!v.is_default && (
                <Button variant="outline" size="sm" onClick={() => setDefault(v)}
                  data-testid={`voice-set-default-${v.id}`}
                  className="border-zinc-700 bg-transparent rounded-sm text-xs">
                  <Star size={12} className="mr-1" /> Fijar por defecto
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => remove(v.id)}
                data-testid={`voice-delete-${v.id}`}
                className="text-red-400 hover:bg-red-500/10 rounded-sm text-xs">
                <TrashSimple size={12} className="mr-1" /> Eliminar
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Layout>
  );
}
