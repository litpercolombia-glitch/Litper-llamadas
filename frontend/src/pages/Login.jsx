import { lazy, Suspense, useEffect, useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Toaster, toast } from "sonner";
import { api } from "../lib/api";
import { GOOGLE_LOGIN_ENABLED, startGoogleLogin } from "../lib/googleLogin";
import {
  LockKey, Envelope, ArrowRight, GoogleLogo, ShieldCheck, Sparkle,
  WhatsappLogo, Eye, EyeSlash,
} from "@phosphor-icons/react";

const CLAVE = "/zcall/motor/operacion/soporte/clave";
const WHATSAPP = "https://wa.me/573144644054?text=" + encodeURIComponent("Hola, no puedo entrar a mi cuenta de Zynex");

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
  const [ver, setVer] = useState(false);                                 // mostrar la contraseña
  const codigo = new URLSearchParams(loc.search).get("clave") || "";
  const [modo, setModo] = useState(codigo ? "cambiar" : "entrar");       // entrar | pedir | cambiar
  const [aviso, setAviso] = useState(null);                              // ["ok" | "mal", texto]
  const [nueva, setNueva] = useState("");
  const [nueva2, setNueva2] = useState("");
  const [porCorreo, setPorCorreo] = useState(true);

  useEffect(() => {
    if (modo !== "pedir") return;
    api.get(`${CLAVE}/estado`).then((r) => setPorCorreo(r.data?.por_correo !== false)).catch(() => {});
  }, [modo]);
  const ir = (m) => { setModo(m); setAviso(null); };

  const pedir = async (e) => {
    e?.preventDefault?.();
    if (!email.trim()) return;
    setBusy(true); setAviso(null);
    try {
      const { data } = await api.post(`${CLAVE}/pedir`, { email: email.trim() });
      setAviso(["ok", data?.mensaje || "Revisa tu correo."]);
    } catch (er) {
      setAviso(["mal", er?.response?.data?.detail || "No pudimos enviar el enlace. Inténtalo de nuevo."]);
    } finally { setBusy(false); }
  };

  const cambiar = async (e) => {
    e?.preventDefault?.();
    if (nueva.length < 8) { setAviso(["mal", "Usa al menos 8 caracteres."]); return; }
    if (nueva !== nueva2) { setAviso(["mal", "Las dos contraseñas no coinciden."]); return; }
    setBusy(true); setAviso(null);
    try {
      const { data } = await api.post(`${CLAVE}/cambiar`, { codigo, password: nueva });
      nav("/login", { replace: true });
      setModo("entrar"); setNueva(""); setNueva2("");
      setAviso(["ok", data?.mensaje || "Listo. Ya puedes entrar con tu contraseña nueva."]);
    } catch (er) {
      setAviso(["mal", er?.response?.data?.detail || "No pudimos guardar la contraseña."]);
    } finally { setBusy(false); }
  };

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
          <h2 className="text-2xl font-semibold mb-1" data-testid="login-title">
            {modo === "entrar" ? "Entra a Zynex OS" : modo === "pedir" ? "Recupera tu contraseña" : "Crea tu contraseña nueva"}
          </h2>
          <p className="text-sm text-zinc-400 mb-6">
            {modo === "entrar" && (GOOGLE_LOGIN_ENABLED ? "Entra con tu correo o con tu cuenta de Google." : "Entra con tu correo y tu contraseña.")}
            {modo === "pedir" && "Escribe el correo de tu cuenta y te enviamos un enlace. Vence en 30 minutos."}
            {modo === "cambiar" && "Escríbela dos veces. Mínimo 8 caracteres."}
          </p>

          {aviso && (
            <div role={aviso[0] === "mal" ? "alert" : "status"} data-testid="login-aviso"
                 className={`mb-4 rounded-md border px-3 py-2 text-sm ${aviso[0] === "ok" ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200" : "border-red-500/40 bg-red-950 text-red-200"}`}>
              {aviso[1]}
            </div>
          )}

          {modo === "pedir" && (
            <form onSubmit={pedir} className="space-y-3" data-testid="clave-pedir-form">
              <label htmlFor="clave-correo" className="sr-only">Correo de tu cuenta</label>
              <div className="relative">
                <Envelope size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                <Input id="clave-correo" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tu@empresa.com"
                       className="bg-black/40 border-white/15 text-white h-11 pl-9" autoFocus required data-testid="clave-correo" />
              </div>
              {porCorreo ? (
                <Button type="submit" disabled={busy} className="btn-cta-grad w-full h-11 rounded-sm font-semibold" data-testid="clave-pedir">
                  {busy ? "Enviando…" : "Enviarme el enlace"}
                </Button>
              ) : (
                <a href={WHATSAPP} target="_blank" rel="noreferrer" data-testid="clave-whatsapp"
                   className="btn-cta-grad w-full h-11 rounded-sm font-semibold inline-flex items-center justify-center gap-2">
                  <WhatsappLogo size={16} weight="fill" /> Pedir ayuda por WhatsApp
                </a>
              )}
              <button type="button" onClick={() => ir("entrar")} className="block mx-auto text-xs text-zinc-400 hover:text-white underline" data-testid="clave-volver">
                Volver a entrar
              </button>
            </form>
          )}

          {modo === "cambiar" && (
            <form onSubmit={cambiar} className="space-y-3" data-testid="clave-cambiar-form">
              <label htmlFor="clave-nueva" className="sr-only">Contraseña nueva</label>
              <Input id="clave-nueva" type={ver ? "text" : "password"} value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="Contraseña nueva"
                     className="bg-black/40 border-white/15 text-white h-11" autoFocus required minLength={8} autoComplete="new-password" data-testid="clave-nueva" />
              <label htmlFor="clave-nueva2" className="sr-only">Repite la contraseña nueva</label>
              <Input id="clave-nueva2" type={ver ? "text" : "password"} value={nueva2} onChange={(e) => setNueva2(e.target.value)} placeholder="Repítela"
                     className="bg-black/40 border-white/15 text-white h-11" required minLength={8} autoComplete="new-password" data-testid="clave-nueva2" />
              <label className="flex items-center gap-2 text-xs text-zinc-400">
                <input type="checkbox" checked={ver} onChange={(e) => setVer(e.target.checked)} /> Mostrar lo que escribo
              </label>
              <Button type="submit" disabled={busy} className="btn-cta-grad w-full h-11 rounded-sm font-semibold" data-testid="clave-cambiar">
                {busy ? "Guardando…" : "Guardar contraseña"}
              </Button>
              <button type="button" onClick={() => ir("pedir")} className="block mx-auto text-xs text-zinc-400 hover:text-white underline">
                Pedir un enlace nuevo
              </button>
            </form>
          )}

          {modo === "entrar" && (<>

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
              <Input type={ver ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)}
                     placeholder="Contraseña"
                     className="bg-black/40 border-white/15 text-white h-11 pl-9 pr-10"
                     required minLength={6} data-testid="login-password" />
              <button type="button" onClick={() => setVer((v) => !v)} aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={ver}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-zinc-400 hover:text-white" data-testid="login-ver">
                {ver ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <div className="text-right -mt-1">
              <button type="button" onClick={() => ir("pedir")} className="text-xs text-cyan-300 hover:text-cyan-200 underline" data-testid="login-olvide">
                ¿Olvidaste tu contraseña?
              </button>
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
          </>)}

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
