import { lazy, Suspense, useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Toaster, toast } from "sonner";
import { api } from "../lib/api";
import { GOOGLE_LOGIN_ENABLED, startGoogleLogin } from "../lib/googleLogin";
import {
  LockKey, Envelope, ArrowRight, GoogleLogo, ShieldCheck, Sparkle,
  WhatsappLogo,
} from "@phosphor-icons/react";

// La ayuda se descarga aparte para que el login pinte rápido.
const PageHelp = lazy(() => import("../components/PageHelp"));

const BENEFITS = [
  { title: "Crea un agente con una frase",
    body:  "Describe tu negocio y qué debe hacer. El asistente prepara la propuesta y tú la revisas." },
  { title: "Tú decides antes de cada cambio",
    body:  "El asistente propone y espera a que pulses «Aplicar». Nada se hace a tus espaldas." },
  { title: "Tus llaves, tus proveedores",
    body:  "Conectas tus propias cuentas y pagas al proveedor solo lo que uses. Se guardan cifradas." },
];

export default function LoginPage() {
  const nav = useNavigate();
  const loc = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!email.trim() || !password) return;
    setBusy(true);
    try {
      const { data } = await api.post("/auth/login", { email: email.trim(), password });
      if (data?.ok) {
        localStorage.setItem("zynex_session_ok", "1");
        toast.success(`Hola, ${data.user?.nombre || "bienvenido"}.`);
        const to = loc.state?.from?.pathname || "/app";
        nav(to, { replace: true });
      }
    } catch (er) {
      toast.error(er?.response?.data?.detail || "Credenciales inválidas.");
    } finally { setBusy(false); }
  };


  return (
    <div className="min-h-screen bg-[#050505] text-white flex flex-col md:flex-row relative overflow-hidden">
      <Toaster position="top-right" richColors theme="dark" />

      {/* LEFT — hook + 3 benefits (NO big Lyan illustration) */}
      <section
        className="relative flex-1 flex flex-col justify-center px-8 md:px-16 py-14 login-hero-bg"
        data-testid="login-hero"
      >
        <div className="relative z-10 max-w-lg mx-auto md:mx-0">
          <div className="flex items-center gap-2 mb-5">
            <img src="/lyan.webp" alt="Lyan"
                 className="w-8 h-8 rounded-full object-cover ring-1 ring-cyan-400/50" />
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-cyan-300">
              Zynex OS · Agentes para tu negocio
            </div>
          </div>

          <h1 className="text-3xl md:text-[42px] font-semibold leading-tight mb-6"
              data-testid="login-hook">
            Agentes que llaman y escriben a tus clientes.
            <br />
            <span className="text-cyan-300">Los creas con una frase.</span>
          </h1>

          <div className="space-y-3" data-testid="login-benefits">
            {BENEFITS.map((b, i) => (
              <div key={i} className="flex gap-3 items-start"
                   data-testid={`login-benefit-${i}`}>
                <div className="mt-1 w-6 h-6 rounded-sm border border-cyan-500/40 bg-cyan-500/10 grid place-items-center shrink-0">
                  <Sparkle size={12} weight="fill" className="text-cyan-300" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">{b.title}</div>
                  <div className="text-xs text-zinc-400 leading-snug">{b.body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* RIGHT — auth form */}
      <section className="w-full md:w-[440px] flex flex-col justify-center px-8 md:px-10 py-14 bg-zinc-950 border-t md:border-t-0 md:border-l border-zinc-800">
        <div className="max-w-md w-full mx-auto">
          <h2 className="text-2xl font-semibold mb-1" data-testid="login-title">Entra a Zynex OS</h2>
          <p className="text-sm text-zinc-400 mb-6">
            {GOOGLE_LOGIN_ENABLED ? "Entra con tu correo o con tu cuenta de Google." : "Entra con tu correo y tu contraseña."}
          </p>

          <Suspense fallback={null}><PageHelp helpKey="login" linkAsk={false} /></Suspense>

          {GOOGLE_LOGIN_ENABLED && (
            <>
              <Button
                onClick={startGoogleLogin}
                type="button"
                variant="outline"
                data-testid="login-google-btn"
                style={{ backgroundColor: "#ffffff", color: "#18181b", borderColor: "#d4d4d8" }}
                className="w-full h-11 mb-3 rounded-sm font-medium hover:opacity-90">
                <GoogleLogo size={16} weight="bold" className="mr-2" />
                Continuar con Google
              </Button>

              <div className="flex items-center gap-3 my-4">
                <div className="flex-1 h-px bg-zinc-800" />
                <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">o con correo</span>
                <div className="flex-1 h-px bg-zinc-800" />
              </div>
            </>
          )}

          <form onSubmit={submit} className="space-y-3" data-testid="login-form">
            <div className="relative">
              <Envelope size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                     placeholder="tu@empresa.com"
                     className="bg-black/40 border-white/15 text-white h-11 pl-9"
                     autoFocus required data-testid="login-email" />
            </div>
            <div className="relative">
              <LockKey size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                     placeholder="Contraseña"
                     className="bg-black/40 border-white/15 text-white h-11 pl-9"
                     required minLength={6} data-testid="login-password" />
            </div>

            <Button type="submit" disabled={busy}
                    className="how-it-works-btn w-full h-11 rounded-sm font-semibold text-white"
                    data-testid="login-submit">
              <span className="hiw-glow" aria-hidden="true" />
              <span className="relative z-10 flex items-center gap-2">
                {busy ? "Verificando…" : (<><ShieldCheck size={16} weight="fill" /> Entrar</>)}
                <ArrowRight size={14} weight="bold" />
              </span>
            </Button>
          </form>

          <p className="text-xs text-zinc-400 text-center mt-6">
            ¿Sin cuenta?{" "}
            <Link to="/register" className="text-white hover:underline"
                  data-testid="login-to-register">
              Crea tu organización
            </Link>
          </p>

          {/* Support footer */}
          <div className="mt-8 pt-5 border-t border-zinc-800 text-[11px] text-zinc-500 space-y-1 text-center"
               data-testid="login-support">
            <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500">¿Ayuda?</div>
            <div className="flex justify-center items-center gap-3">
              <a href="mailto:zynexproai@gmail.com"
                 className="inline-flex items-center gap-1 hover:text-white transition"
                 data-testid="login-support-email">
                <Envelope size={11} weight="fill" /> zynexproai@gmail.com
              </a>
              <span className="text-zinc-700">·</span>
              <a href="https://wa.me/573144644054" target="_blank" rel="noreferrer"
                 className="inline-flex items-center gap-1 hover:text-white transition"
                 data-testid="login-support-whatsapp">
                <WhatsappLogo size={11} weight="fill" className="text-emerald-400" /> 314 464 4054
              </a>
            </div>
            <p className="text-[11px] text-zinc-500 mt-2">
              <a href="/" className="text-zinc-400 hover:text-white transition"
                 data-testid="login-back-funnel">← Volver al sitio</a>
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
