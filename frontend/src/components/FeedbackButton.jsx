import { useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Lightbulb } from "@phosphor-icons/react";

/**
 * Floating feedback button. Present on every authenticated route via App.js
 * mount. Sends to POST /api/feedback which persists AND best-effort emails
 * FEEDBACK_EMAIL (zynexproai@gmail.com).
 */
export default function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!title.trim() || !description.trim()) {
      toast.error("Ponle un título y descríbenos tu idea.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.post("/feedback", {
        title: title.trim(),
        description: description.trim(),
        email: email.trim() || undefined,
        source: "app-fab",
      });
      toast.success(r.data?.message || "¡Gracias! Recibimos tu idea.");
      setTitle(""); setDescription(""); setEmail("");
      setOpen(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "No se pudo enviar. Reintenta.");
    } finally { setBusy(false); }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="feedback-fab"
        data-testid="feedback-fab"
        aria-label="Sugerir función"
        type="button">
        <Lightbulb size={16} weight="fill" /> Sugerir función
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="feedback-dialog" className="bg-zinc-950 border-zinc-800 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lightbulb size={18} weight="fill" className="text-yellow-300" />
              Sugerir función a Zynex
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              Contamos qué te falta o qué haría tu operación 10× más simple. Leemos todas.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">
                Título
              </label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ej: Reintentar rescate en fin de semana"
                data-testid="feedback-title"
                className="bg-black/40 border-zinc-700 text-white"
                maxLength={140}
                required
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">
                Descripción
              </label>
              <Textarea
                rows={5}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Cuéntanos el problema y cómo lo verías resuelto…"
                data-testid="feedback-description"
                className="bg-black/40 border-zinc-700 text-white"
                maxLength={4000}
                required
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-mono tracking-widest text-zinc-500 block mb-1">
                Tu email (opcional)
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@empresa.com — para responderte si hace falta"
                data-testid="feedback-email"
                className="bg-black/40 border-zinc-700 text-white"
              />
            </div>

            <DialogFooter className="gap-2">
              <Button
                type="button" variant="outline"
                onClick={() => setOpen(false)}
                className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800"
                data-testid="feedback-cancel"
              >Cancelar</Button>
              <Button
                type="submit" disabled={busy}
                data-testid="feedback-submit"
                className="btn-cta-grad rounded-sm">
                {busy ? "Enviando…" : "Enviar sugerencia"}
              </Button>
            </DialogFooter>
          </form>

          <div className="mt-4 pt-3 border-t border-zinc-800 text-[11px] text-zinc-500 text-center"
               data-testid="feedback-support">
            ¿Necesitas soporte? Escríbenos a{" "}
            <a href="mailto:zynexproai@gmail.com"
               className="text-cyan-300 hover:text-cyan-200">zynexproai@gmail.com</a>
            {" "}o WhatsApp{" "}
            <a href="https://wa.me/573144754115" target="_blank" rel="noreferrer"
               className="text-emerald-300 hover:text-emerald-200">3144754115</a>.
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
