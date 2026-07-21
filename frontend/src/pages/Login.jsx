import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import MatrixRain from "../components/MatrixRain";
import ThemeToggle from "../components/ThemeToggle";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Toaster, toast } from "sonner";
import { LockKey, ShieldCheck, ArrowRight } from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function LoginPage() {
  const nav = useNavigate();
  const loc = useLocation();
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!key.trim()) return;
    setBusy(true);
    try {
      // Validate against a lightweight authenticated endpoint (health if you
      // pass X-API-Key it returns 200; carriers is protected).
      const r = await axios.get(`${BACKEND_URL}/api/carriers`,
        { headers: { "X-API-Key": key.trim() }, timeout: 8000 });
      if (r.status === 200) {
        localStorage.setItem("litper_operator_ok", "1");
        localStorage.setItem("litper_operator_key", key.trim());
        toast.success("Bienvenido, operador.");
        const to = loc.state?.from?.pathname || "/app";
        nav(to, { replace: true });
      }
    } catch (er) {
      toast.error("Clave inválida. Pídela al admin.");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid place-items-center bg-[var(--bg-primary)] text-white relative overflow-hidden">
      <Toaster position="top-right" richColors theme="dark" />
      <MatrixRain />
      <div className="absolute top-4 right-4"><ThemeToggle /></div>

      <div className="relative z-10 w-full max-w-md mx-auto px-6">
        <div className="mascot-ring mx-auto mb-8" style={{ width: 110, height: 110 }}>
          <LockKey size={40} weight="duotone" className="text-white" />
        </div>
        <h1 className="text-3xl font-semibold text-center text-white mb-1">
          Panel de operadores
        </h1>
        <p className="text-sm text-zinc-400 text-center mb-8">
          Solo el equipo Litper. Ingresa tu clave.
        </p>
        <form onSubmit={submit} className="space-y-3" data-testid="login-form">
          <Input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="Operator key"
            className="bg-black/40 border-white/15 text-white h-11"
            autoFocus
            data-testid="login-key"
          />
          <Button type="submit" disabled={busy || !key.trim()}
            className="w-full h-11 btn-cta-grad" data-testid="login-submit">
            {busy ? "Verificando…" : (<><ShieldCheck size={16} weight="fill" /> Entrar</>)}
            <ArrowRight size={14} weight="bold" />
          </Button>
        </form>
        <p className="text-[11px] text-zinc-500 text-center mt-6">
          ¿No eres del equipo? <a href="/" className="text-zinc-300 hover:text-white transition"
            data-testid="login-back-funnel">Volver al sitio</a>
        </p>
      </div>
    </div>
  );
}
