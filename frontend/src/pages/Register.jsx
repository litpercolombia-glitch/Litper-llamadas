import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import MatrixRain from "../components/MatrixRain";
import Constellation from "../components/Constellation";
import ThemeToggle from "../components/ThemeToggle";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Toaster, toast } from "sonner";
import { api } from "../lib/api";
import { LockKey, ShieldCheck, ArrowRight, GoogleLogo, User, Envelope, Buildings } from "@phosphor-icons/react";

export default function RegisterPage() {
  const nav = useNavigate();
  const [nombre, setNombre] = useState("");
  const [org, setOrg] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!email || !password || !nombre) return;
    if (password.length < 6) { toast.error("Mínimo 6 caracteres."); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/auth/register", {
        email: email.trim(), password,
        nombre: nombre.trim(),
        org_name: org.trim() || "Mi organización",
      });
      if (data?.ok) {
        localStorage.setItem("litper_operator_ok", "1");
        toast.success(`Cuenta creada. Bienvenido, ${data.user?.nombre}.`);
        nav("/app", { replace: true });
      }
    } catch (er) {
      toast.error(er?.response?.data?.detail || "No se pudo registrar.");
    } finally { setBusy(false); }
  };

  const google = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/app";
    window.location.href =
      "https://auth.emergentagent.com/?redirect=" + encodeURIComponent(redirectUrl);
  };

  return (
    <div className="min-h-screen grid place-items-center bg-[var(--bg-primary)] text-[var(--text-primary)] relative overflow-hidden">
      <Toaster position="top-right" richColors theme="dark" />
      <Constellation density={70} />
      <MatrixRain />
      <div className="absolute top-4 right-4"><ThemeToggle /></div>

      <div className="relative z-10 w-full max-w-md mx-auto px-6 py-10">
        <div className="mascot-ring mx-auto mb-6" style={{ width: 88, height: 88 }}>
          <Buildings size={34} weight="duotone" className="text-white" />
        </div>
        <h1 className="text-3xl font-semibold text-center text-white mb-1"
            data-testid="register-title">
          Crea tu organización
        </h1>
        <p className="text-sm text-zinc-400 text-center mb-8">
          BYOK · Sin límite de operadores · 14 días gratis.
        </p>

        <Button
          onClick={google}
          type="button"
          variant="outline"
          data-testid="register-google-btn"
          style={{ backgroundColor: "#ffffff", color: "#18181b", borderColor: "#d4d4d8" }}
          className="w-full h-11 mb-3 rounded-sm font-medium hover:opacity-90">
          <GoogleLogo size={16} weight="bold" className="mr-2" />
          Continuar con Google
        </Button>

        <div className="flex items-center gap-3 my-4">
          <div className="flex-1 h-px bg-zinc-800" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">o con email</span>
          <div className="flex-1 h-px bg-zinc-800" />
        </div>

        <form onSubmit={submit} className="space-y-3" data-testid="register-form">
          <div className="relative">
            <User size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <Input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)}
              placeholder="Tu nombre" required
              className="bg-black/40 border-white/15 text-white h-11 pl-9"
              data-testid="register-nombre" />
          </div>
          <div className="relative">
            <Buildings size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <Input type="text" value={org} onChange={(e) => setOrg(e.target.value)}
              placeholder="Nombre de la empresa (opcional)"
              className="bg-black/40 border-white/15 text-white h-11 pl-9"
              data-testid="register-org" />
          </div>
          <div className="relative">
            <Envelope size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@empresa.com" required
              className="bg-black/40 border-white/15 text-white h-11 pl-9"
              data-testid="register-email" />
          </div>
          <div className="relative">
            <LockKey size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Contraseña (mín. 6)" required minLength={6}
              className="bg-black/40 border-white/15 text-white h-11 pl-9"
              data-testid="register-password" />
          </div>
          <Button type="submit" disabled={busy}
            className="w-full h-11 btn-cta-grad" data-testid="register-submit">
            {busy ? "Creando cuenta…" : (<><ShieldCheck size={16} weight="fill" /> Crear cuenta</>)}
            <ArrowRight size={14} weight="bold" />
          </Button>
        </form>

        <p className="text-xs text-zinc-400 text-center mt-6">
          ¿Ya tienes cuenta?{" "}
          <Link to="/login" className="text-white hover:underline" data-testid="register-to-login">
            Inicia sesión
          </Link>
        </p>
      </div>
    </div>
  );
}
