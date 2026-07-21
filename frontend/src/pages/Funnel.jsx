import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import MatrixRain from "../components/MatrixRain";
import ThemeToggle from "../components/ThemeToggle";
import WireframePolyhedron from "../components/WireframePolyhedron";
import Constellation from "../components/Constellation";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Toaster, toast } from "sonner";
import {
  Robot, PhoneCall, WhatsappLogo, ChartLineUp, Clock, Package,
  ShieldCheck, Sparkle, Timer, Fire, CheckCircle, Lightning,
  Trophy, ArrowRight, Users, LockKey, Storefront, ShoppingBag,
  FileXls, GearSix, MetaLogo, PlugsConnected,
} from "@phosphor-icons/react";
import { Link } from "react-router-dom";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
// Public capture endpoint — no API key needed (server allows unauth here).
const publicApi = axios.create({ baseURL: `${BACKEND_URL}/api` });

// -----------------------------------------------------------------------
// Countdown to a fixed launch date (auto-refreshes to next Friday 23:59 CO)
// -----------------------------------------------------------------------
function nextDeadline() {
  const d = new Date();
  // aim at the nearest Friday 23:59:00 America/Bogota (UTC-5)
  const day = d.getUTCDay(); // Sun=0..Sat=6
  const daysToFri = (5 - day + 7) % 7 || 7; // always in the future
  const target = new Date(d);
  target.setUTCDate(d.getUTCDate() + daysToFri);
  target.setUTCHours(23 + 5, 59, 0, 0);
  return target;
}
function useCountdown(target) {
  const [t, setT] = useState(() => Math.max(0, target.getTime() - Date.now()));
  useEffect(() => {
    const id = setInterval(() => setT(Math.max(0, target.getTime() - Date.now())), 1000);
    return () => clearInterval(id);
  }, [target]);
  const s = Math.floor(t / 1000);
  return {
    d: Math.floor(s / 86400),
    h: Math.floor((s % 86400) / 3600),
    m: Math.floor((s % 3600) / 60),
    s: s % 60,
    ms: t,
  };
}

// -----------------------------------------------------------------------
// VIP CAPTURE MODAL / FORM
// -----------------------------------------------------------------------
function VipForm({ onDone }) {
  const [nombre, setNombre] = useState("");
  const [whatsapp, setWhatsapp] = useState("+57");
  const [pais, setPais] = useState("CO");
  const [pedidos, setPedidos] = useState("50-200");
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [success, setSuccess] = useState(null); // {group_url, lead}

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!nombre.trim() || whatsapp.length < 8) {
      toast.error("Ingresa tu nombre y un WhatsApp válido."); return;
    }
    setSending(true);
    try {
      const utm = Object.fromEntries(new URLSearchParams(window.location.search));
      const { data } = await publicApi.post("/vip-leads", {
        nombre, whatsapp, pais, pedidos_semana: pedidos, email, utm,
      });
      const cfg = await publicApi.get("/vip-leads/config").then((r) => r.data).catch(() => ({}));
      setSuccess({ lead: data, group_url: cfg.vip_group_url || "" });
      onDone?.(data);
    } catch (er) {
      toast.error(er.response?.data?.detail || "Error enviando. Reintenta.");
    } finally { setSending(false); }
  };

  if (success) {
    return (
      <div data-testid="vip-success" className="text-center">
        <div className="w-16 h-16 mx-auto rounded-full bg-green-500/15 grid place-items-center mb-4">
          <CheckCircle size={40} className="text-green-400" weight="duotone" />
        </div>
        <h3 className="text-2xl font-semibold text-white mb-2">¡Estás dentro del VIP!</h3>
        <p className="text-sm text-zinc-300 max-w-md mx-auto mb-6">
          En segundos recibirás un WhatsApp de bienvenida. Únete al grupo privado donde
          publicamos las plazas fundadoras y el onboarding.
        </p>
        {success.group_url ? (
          <a
            href={success.group_url}
            target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full px-6 py-3 bg-white text-black font-semibold text-sm hover:bg-zinc-200 transition"
            data-testid="vip-group-link"
          >
            <WhatsappLogo size={18} weight="fill" /> Entrar al Grupo VIP en WhatsApp
          </a>
        ) : (
          <div className="text-xs text-zinc-400">
            (Enviaremos el link del grupo por WhatsApp)
          </div>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3" data-testid="vip-form">
      <Input placeholder="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)}
             className="bg-black/40 border-white/15 text-white placeholder:text-zinc-500 h-11"
             data-testid="vip-nombre" />
      <Input placeholder="WhatsApp (+57...)" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)}
             className="bg-black/40 border-white/15 text-white placeholder:text-zinc-500 h-11"
             data-testid="vip-whatsapp" />
      <div className="grid grid-cols-2 gap-3">
        <Select value={pais} onValueChange={setPais}>
          <SelectTrigger className="bg-black/40 border-white/15 text-white h-11" data-testid="vip-pais">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="CO">Colombia</SelectItem>
            <SelectItem value="EC">Ecuador</SelectItem>
            <SelectItem value="CL">Chile</SelectItem>
            <SelectItem value="MX">México</SelectItem>
            <SelectItem value="PE">Perú</SelectItem>
            <SelectItem value="AR">Argentina</SelectItem>
            <SelectItem value="OTRO">Otro</SelectItem>
          </SelectContent>
        </Select>
        <Select value={pedidos} onValueChange={setPedidos}>
          <SelectTrigger className="bg-black/40 border-white/15 text-white h-11" data-testid="vip-pedidos">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="<50">Menos de 50 pedidos/semana</SelectItem>
            <SelectItem value="50-200">50–200 pedidos/semana</SelectItem>
            <SelectItem value="200-500">200–500 pedidos/semana</SelectItem>
            <SelectItem value="500+">500+ pedidos/semana</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Input placeholder="Email (opcional)" value={email} onChange={(e) => setEmail(e.target.value)}
             className="bg-black/40 border-white/15 text-white placeholder:text-zinc-500 h-11"
             data-testid="vip-email" />
      <Button
        type="submit"
        disabled={sending}
        className="w-full h-12 btn-cta-grad font-semibold text-sm"
        data-testid="vip-submit"
      >
        {sending ? "Enviando…" : (<><Sparkle size={16} weight="fill" /> Quiero entrar al Grupo VIP</>)}
      </Button>
      <p className="text-[11px] text-zinc-500 text-center">
        Sin spam. Puedes salirte cuando quieras.
      </p>
    </form>
  );
}

// -----------------------------------------------------------------------
// VALUE STACK item
// -----------------------------------------------------------------------
function StackItem({ icon: Icon, title, desc, valor }) {
  return (
    <div className="flex items-start gap-3 p-4 rounded-xl border border-white/10 bg-white/[0.04] backdrop-blur-xl"
      data-testid={`stack-${title.toLowerCase().replace(/\s+/g,'-')}`}>
      <div className="w-10 h-10 rounded-lg bg-white/10 grid place-items-center shrink-0">
        <Icon size={20} className="text-white" weight="duotone" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2">
          <h4 className="text-white font-semibold text-sm">{title}</h4>
          <span className="text-xs font-mono text-zinc-400">Valor {valor}</span>
        </div>
        <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------
// FUNNEL PAGE
// -----------------------------------------------------------------------
export default function FunnelPage() {
  useEffect(() => {
    document.title = "Litper Connect — Recupera pedidos en oficina, baja devoluciones";
    // Prefer night on the landing (works with existing theme toggle)
    if (!localStorage.getItem("theme")) {
      document.documentElement.classList.add("matrix-night");
    }
  }, []);

  const deadline = useMemo(() => nextDeadline(), []);
  const cd = useCountdown(deadline);
  const formRef = useRef(null);
  const scrollToForm = () => formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  const stack = [
    { icon: PhoneCall,   title: "IA de llamadas Sofía (hasta 5 intentos)",
      desc: "Voz de mujer colombiana clonada. Confirma la recogida en oficina antes de que expire el plazo del transportador.",
      valor: "$3.900.000" },
    { icon: WhatsappLogo, title: "WhatsApp automático (Chatea Pro)",
      desc: "Fallback inteligente con plantillas 'Reclamo en Oficina' y 'No Oficina' según los días restantes.",
      valor: "$1.500.000" },
    { icon: Clock,       title: "Semáforo por transportadora",
      desc: "Rojo/Amarillo/Verde según los días máximos por carrier (Servientrega 8d, Envía 1d, TCC 3d, etc.).",
      valor: "$900.000" },
    { icon: ChartLineUp, title: "Dashboard de recuperación",
      desc: "Cuánto recaudaste que se iba a devolver. KPI por día, transportadora, vendedor.",
      valor: "$1.200.000" },
    { icon: Robot,       title: "Copiloto IA (multi-LLM)",
      desc: "Groq, Gemini, Claude enrutados según la tarea. Habla en español, ejecuta acciones internas.",
      valor: "$2.000.000" },
    { icon: Package,     title: "Importador Dropi combo-safe",
      desc: "Un pedido con 3 líneas en Dropi se importa como UNA orden con el recaudo correcto. Sin inflar ventas.",
      valor: "$600.000" },
  ];

  return (
    <div className="min-h-screen text-[var(--text-primary)] bg-[var(--bg-primary)] relative overflow-x-hidden">
      <Toaster position="top-right" richColors theme="dark" />
      <Constellation density={110} />
      <MatrixRain />

      {/* TOP MARQUEE TICKER */}
      <div className="marquee relative z-20" data-testid="funnel-marquee">
        <div className="marquee-inner">
          {Array.from({ length: 2 }).flatMap((_, r) => [
            <span key={`a-${r}`}><span className="dot" /> Recupera pedidos represados en oficina</span>,
            <span key={`b-${r}`}><span className="dot" /> Hasta 5 llamadas IA + fallback WhatsApp</span>,
            <span key={`c-${r}`}><span className="dot" /> 13 transportadoras integradas</span>,
            <span key={`d-${r}`}><span className="dot" /> Colombia · Ecuador · Chile</span>,
            <span key={`e-${r}`}><span className="dot" /> Sofía habla como una colombiana real</span>,
            <span key={`f-${r}`}><span className="dot" /> Importador Dropi combo-safe</span>,
          ])}
        </div>
      </div>

      {/* NAV */}
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[color-mix(in_oklab,var(--bg-primary)_75%,transparent)] border-b border-[var(--border)]">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-5 py-3">
          <div className="flex items-center gap-2.5">
            {/* Gradient chevrons logo */}
            <div className="relative w-9 h-9 grid place-items-center">
              <div className="absolute inset-0 rounded-lg" style={{ background: "var(--accent-grad)" }} />
              <div className="absolute inset-[1px] rounded-[7px] bg-[var(--bg-primary)] grid place-items-center">
                <span className="text-[15px] font-bold grad-text tracking-tight">L</span>
              </div>
            </div>
            <div className="leading-tight">
              <div className="font-semibold text-sm">Litper <span className="grad-text">Connect</span></div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--text-muted)]">Recovery Engine</div>
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-6 text-[13px] text-[var(--text-secondary)]">
            <a href="#value-stack" className="hover:text-[var(--text-primary)] transition">Funciones</a>
            <a href="#guarantee"   className="hover:text-[var(--text-primary)] transition">Diagnóstico</a>
            <a href="#pricing"     className="hover:text-[var(--text-primary)] transition">Precios</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/app" className="text-[11px] font-mono uppercase tracking-widest text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition px-3 py-1.5 rounded-full border border-[var(--border)]"
              data-testid="funnel-nav-login">
              <LockKey size={12} className="inline mr-1" /> Ingresar
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="relative max-w-6xl mx-auto px-5 pt-14 pb-16 md:pt-20 md:pb-24">
        <div className="grid md:grid-cols-2 gap-10 items-center">
          {/* LEFT — copy */}
          <div>
            <div className="pill-grad inline-flex items-center gap-2 mb-6" data-testid="funnel-hero-badge">
              <Fire size={12} weight="fill" /> Lanzamiento · Cupos fundadores
            </div>
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-semibold leading-[1.02] tracking-tight"
              data-testid="funnel-hero-headline">
              Recupera los pedidos represados en oficina.<br/>
              <span className="grad-text">Sabe exactamente</span> dónde pierdes plata.
            </h1>
            <p className="mt-5 text-[15px] md:text-base text-[var(--text-secondary)] max-w-xl leading-relaxed"
              data-testid="funnel-hero-subhead">
              Litper Connect es la IA que llama con voz humana y WhatsApp automático
              para confirmar tus COD antes de que el transportador los devuelva.
              Diseñado para e‑commerce en Colombia, Ecuador y Chile.
            </p>

            <div className="mt-7 flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <Button onClick={scrollToForm}
                className="h-12 px-6 btn-cta-grad font-semibold text-sm"
                data-testid="funnel-hero-cta">
                Quiero entrar al Grupo VIP <ArrowRight size={16} weight="bold" />
              </Button>
              <a href="#value-stack" className="h-12 px-2 grid place-items-center text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition">
                Ver qué incluye ↓
              </a>
            </div>

            {/* Trust bar */}
            <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-[10px] font-mono uppercase tracking-widest text-[var(--text-muted)]">
              <span className="flex items-center gap-1.5"><CheckCircle size={12} className="text-emerald-400" /> 13 transportadoras</span>
              <span className="flex items-center gap-1.5"><CheckCircle size={12} className="text-emerald-400" /> Voces IA CO</span>
              <span className="flex items-center gap-1.5"><CheckCircle size={12} className="text-emerald-400" /> Chatea · Twilio · Telnyx</span>
              <span className="flex items-center gap-1.5"><CheckCircle size={12} className="text-emerald-400" /> Dropi combo-safe</span>
            </div>
          </div>

          {/* RIGHT — 3D wireframe */}
          <div className="relative flex items-center justify-center min-h-[380px]">
            <WireframePolyhedron size={380} />
          </div>
        </div>

        {/* Connector pills */}
        <div className="mt-14" data-testid="funnel-connector-pills">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-[var(--text-muted)] mb-3 text-center">
            Se conecta con tu stack
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {[
              { label: "Dropi",       Icon: ShoppingBag },
              { label: "Meta Ads",    Icon: MetaLogo },
              { label: "Shopify",     Icon: Storefront },
              { label: "WhatsApp",    Icon: WhatsappLogo },
              { label: "Excel / CSV", Icon: FileXls },
              { label: "Chatea Pro",  Icon: PlugsConnected },
              { label: "n8n",         Icon: GearSix },
            ].map(({ label, Icon }) => (
              <div key={label} className="chip-glass" data-testid={`connector-pill-${label.toLowerCase().replace(/[^a-z0-9]+/g,'-')}`}>
                <Icon size={14} weight="duotone" /> {label}
              </div>
            ))}
          </div>
        </div>

        {/* Value equation callout */}
        <div className="mt-14 grid md:grid-cols-4 gap-3">
          {[
            ["+38%", "Recuperación en oficina"],
            ["−24%", "Devoluciones evitadas"],
            ["<3 min", "Setup por transportadora"],
            ["24/7", "Sofía llama sin dormir"],
          ].map(([k, v]) => (
            <div key={v} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] backdrop-blur-xl px-4 py-4"
              data-testid={`funnel-stat-${v.toLowerCase().replace(/\s+/g,'-')}`}>
              <div className="text-2xl font-semibold grad-text">{k}</div>
              <div className="text-[11px] font-mono uppercase tracking-widest text-[var(--text-muted)] mt-1">{v}</div>
            </div>
          ))}
        </div>
      </section>

      {/* PROBLEM / AGITATE */}
      <section className="max-w-4xl mx-auto px-5 pb-16">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6 md:p-10">
          <h2 className="text-2xl md:text-3xl font-semibold text-white mb-4">
            Cada pedido que se devuelve te cuesta el doble.
          </h2>
          <p className="text-zinc-300 leading-relaxed">
            Cuando un COD queda "en oficina", el reloj corre: Envía te da 1 día, TCC 3,
            Servientrega 8. Si tu equipo no llama y confirma la recogida, el paquete
            se devuelve y pagas transporte de ida y vuelta, además de perder la venta.
            Multiplícalo por 200 pedidos al mes y son millones tirados.
          </p>
          <p className="text-zinc-100 font-medium mt-4">
            Litper Connect resuelve exactamente esto — con IA que llama y WhatsApp automático.
          </p>
        </div>
      </section>

      {/* VALUE STACK */}
      <section id="value-stack" className="max-w-6xl mx-auto px-5 pb-16">
        <div className="text-center mb-10">
          <div className="text-[11px] font-mono uppercase tracking-[0.25em] text-zinc-400 mb-2">La Grand Slam Offer</div>
          <h2 className="text-3xl md:text-4xl font-semibold text-white">Todo lo que llevas al cerrar hoy</h2>
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          {stack.map((s) => <StackItem key={s.title} {...s} />)}
        </div>

        {/* PRICE MATH */}
        <div id="pricing" className="mt-10 rounded-2xl border border-[var(--border)] bg-gradient-to-b from-[color-mix(in_oklab,var(--accent)_10%,var(--surface))] to-[var(--surface)] backdrop-blur-xl p-6 md:p-8"
          data-testid="funnel-price-math">
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-400 mb-2">Valor total</div>
              <div className="text-3xl font-semibold text-white line-through decoration-red-400/80 decoration-2">
                $10.100.000 <span className="text-sm font-normal text-zinc-400">COP / setup</span>
              </div>
              <div className="text-xs text-zinc-400 mt-1">(si lo construyeras y contrataras por separado)</div>
            </div>
            <div>
              <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-400 mb-2">Precio fundador</div>
              <div className="text-4xl md:text-5xl font-semibold text-white">
                $497.000 <span className="text-sm font-normal text-zinc-400">COP / mes</span>
              </div>
              <div className="text-xs text-emerald-300 mt-1">Sube a $997.000 al cerrar el cupo fundador.</div>
            </div>
          </div>
        </div>
      </section>

      {/* PRECIOS — 3 planes con spotlight */}
      <PricingSection />

      {/* FUNCIONES — grid con tilted cards */}
      <FeaturesGrid />

      {/* FAQ */}
      <FaqSection />


      {/* GARANTIA */}
      <section id="guarantee" className="max-w-4xl mx-auto px-5 pb-16">
        <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.05] backdrop-blur-xl p-6 md:p-10 flex items-start gap-4"
             data-testid="funnel-guarantee">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/15 grid place-items-center shrink-0">
            <ShieldCheck size={26} className="text-emerald-300" weight="duotone" />
          </div>
          <div>
            <h3 className="text-xl md:text-2xl font-semibold mb-2">
              Garantía <span className="grad-text">"Se paga solo o no pagas."</span>
            </h3>
            <p className="text-[var(--text-secondary)] leading-relaxed">
              Si en <b>30 días</b> Litper Connect no te recupera pedidos suficientes para
              pagar el sistema, te devolvemos el 100%. Sin excusas. Sin letras chicas.
              Nosotros llevamos el riesgo — porque el producto ya está probado.
            </p>
          </div>
        </div>
      </section>

      {/* BONOS */}
      <section className="max-w-6xl mx-auto px-5 pb-16">
        <div className="text-center mb-6">
          <div className="text-[11px] font-mono uppercase tracking-[0.25em] text-zinc-400 mb-2">Bonos por entrar hoy</div>
          <h2 className="text-3xl md:text-4xl font-semibold text-white">3 bonos exclusivos fundador</h2>
        </div>
        <div className="grid md:grid-cols-3 gap-3">
          {[
            { icon: WhatsappLogo, title: "Plantillas de WhatsApp aprobadas",
              desc: "Reclamo en Oficina · No Oficina · Cambio de Dirección — probadas y aprobadas por Chatea Pro."},
            { icon: Users, title: "Onboarding 1:1 con nuestro equipo",
              desc: "Setup completo (transportadoras, voces, cadencia, importador) en menos de 3 horas."},
            { icon: Trophy, title: "Acceso al Grupo VIP en WhatsApp",
              desc: "Publicamos actualizaciones, benchmarks y prompts. Networking con otros e-commerce."},
          ].map((b) => (
            <div key={b.title} className="rounded-xl border border-white/10 bg-white/[0.04] backdrop-blur-xl p-5"
              data-testid={`funnel-bonus-${b.title.toLowerCase().split(' ')[0]}`}>
              <b.icon size={22} className="text-white mb-2" weight="duotone" />
              <h4 className="text-white font-semibold text-sm mb-1">{b.title}</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">{b.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* SCARCITY */}
      <section className="max-w-4xl mx-auto px-5 pb-16">
        <div className="rounded-2xl border border-amber-500/25 bg-amber-500/[0.05] backdrop-blur-xl p-6 md:p-8"
          data-testid="funnel-scarcity">
          <div className="flex items-center gap-2 mb-3">
            <Timer size={18} className="text-amber-300" weight="duotone" />
            <span className="text-[11px] font-mono uppercase tracking-[0.25em] text-amber-200">Cupo fundador cierra en</span>
          </div>
          <div className="grid grid-cols-4 gap-2 max-w-md">
            {[["d", cd.d], ["h", cd.h], ["m", cd.m], ["s", cd.s]].map(([lbl, val]) => (
              <div key={lbl} className="rounded-lg bg-black/40 border border-white/10 py-3 text-center">
                <div className="text-3xl md:text-4xl font-semibold text-white font-mono">
                  {String(val).padStart(2, "0")}
                </div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-400">{lbl}</div>
              </div>
            ))}
          </div>
          <p className="text-xs text-zinc-400 mt-4">
            Después el precio fundador expira y sube a $997.000/mes.
          </p>
        </div>
      </section>

      {/* CTA FORM */}
      <section ref={formRef} id="vip" className="max-w-3xl mx-auto px-5 pb-24">
        <div className="rounded-3xl border border-white/15 bg-gradient-to-b from-white/[0.08] to-white/[0.02] backdrop-blur-xl p-6 md:p-10 shadow-[0_0_80px_rgba(90,200,250,0.08)]">
          <div className="text-center mb-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/30 px-3 py-1 text-[11px] font-mono uppercase tracking-widest text-zinc-300 mb-4">
              <Lightning size={12} className="text-yellow-300" weight="fill" />
              Grupo VIP · WhatsApp
            </div>
            <h3 className="text-3xl md:text-4xl font-semibold text-white">
              Reserva tu plaza fundadora
            </h3>
            <p className="text-sm text-zinc-300 mt-2">
              Déjanos tus datos. Te avisamos por WhatsApp cuando abrimos onboarding y te enviamos el link del grupo VIP.
            </p>
          </div>
          <VipForm />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 py-8 text-center text-xs text-zinc-500">
        <div className="max-w-6xl mx-auto px-5">
          Litper Connect · Hecho en Colombia · COD LATAM ·
          <Link to="/app" className="text-zinc-400 hover:text-white transition ml-1"
            data-testid="funnel-footer-login">Panel operadores</Link>
        </div>
      </footer>
    </div>
  );
}


// -----------------------------------------------------------------------
// PRICING
// -----------------------------------------------------------------------
function PricingSection() {
  const [annual, setAnnual] = useState(false);

  const plans = [
    {
      name: "Starter", subtitle: "Para probar el sistema.",
      monthly: 297, annualMul: 10, // 2 meses gratis
      features: [
        "1 usuario operador",
        "Hasta 200 órdenes/mes en cola",
        "Importador Dropi combo-safe",
        "WhatsApp + reglas 24h",
        "1 voz Sofía",
        "Soporte por email",
      ],
      cta: "Empezar",
      highlight: false,
    },
    {
      name: "Growth", subtitle: "Recomendado. Escala el equipo.",
      monthly: 497, annualMul: 10,
      features: [
        "5 usuarios operadores",
        "Hasta 2.000 órdenes/mes",
        "Voces Sofía por país (CO · EC · CL)",
        "Multi-LLM router (Groq · Claude · Gemini)",
        "Prompts pro (6-block ElevenLabs)",
        "Métricas de recuperación",
        "Onboarding 1:1",
      ],
      cta: "Reservar plaza",
      highlight: true,
    },
    {
      name: "Scale · Fundador", subtitle: "Cupo limitado antes del lanzamiento.",
      monthly: 997, annualMul: 10,
      features: [
        "Usuarios ilimitados",
        "Órdenes ilimitadas",
        "Voces custom clonadas (2 incluidas)",
        "SIP dedicado Telnyx",
        "Integración custom (Supabase / n8n / Meta Ads)",
        "Soporte prioritario 24/7",
        "Precio fundador congelado",
      ],
      cta: "Hablar con ventas",
      highlight: false,
    },
  ];

  return (
    <section id="pricing-plans" className="max-w-6xl mx-auto px-5 pb-16" data-testid="funnel-pricing">
      <div className="text-center mb-8">
        <div className="pill-grad inline-flex items-center gap-2 mb-3">
          <Sparkle size={12} weight="fill" /> Precios
        </div>
        <h2 className="text-3xl md:text-4xl font-semibold">
          Plan simple. <span className="grad-text">ROI inmediato.</span>
        </h2>
        <p className="text-sm text-[var(--text-secondary)] max-w-xl mx-auto mt-3">
          Precios en pesos colombianos (COP), miles. Editables desde el panel — solo son sugerencia.
        </p>
        <div className="mt-5 inline-flex rounded-full border border-[var(--border)] p-1 bg-[var(--surface)] backdrop-blur">
          <button onClick={() => setAnnual(false)}
            className={`px-4 py-1.5 text-xs rounded-full transition ${!annual ? "bg-[var(--text-primary)] text-[var(--bg-primary)] font-medium" : "text-[var(--text-secondary)]"}`}
            data-testid="pricing-toggle-monthly">Mensual</button>
          <button onClick={() => setAnnual(true)}
            className={`px-4 py-1.5 text-xs rounded-full transition ${annual ? "bg-[var(--text-primary)] text-[var(--bg-primary)] font-medium" : "text-[var(--text-secondary)]"}`}
            data-testid="pricing-toggle-annual">
            Anual · <span className="grad-text">2 meses gratis</span>
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {plans.map((p) => {
          const price = annual ? p.monthly * p.annualMul : p.monthly;
          return (
            <div key={p.name}
              className={`relative rounded-2xl border p-6 backdrop-blur-xl transition
                ${p.highlight
                  ? "border-transparent bg-gradient-to-b from-[color-mix(in_oklab,var(--accent)_20%,var(--surface))] to-[var(--surface)]"
                  : "border-[var(--border)] bg-[var(--surface)]"}`}
              data-testid={`pricing-plan-${p.name.toLowerCase().replace(/\W+/g,'-')}`}
              style={p.highlight ? { boxShadow: "0 0 0 1px transparent, 0 20px 60px -20px rgba(10,132,255,0.35)" } : {}}>
              {p.highlight && (
                <div className="absolute -top-3 left-6 pill-grad" data-testid="pricing-recommended">
                  Más popular
                </div>
              )}
              <div className="text-sm text-[var(--text-secondary)]">{p.subtitle}</div>
              <h3 className={`text-2xl font-semibold mt-1 ${p.highlight ? "grad-text" : ""}`}>{p.name}</h3>
              <div className="mt-5 flex items-baseline gap-1">
                <span className="text-4xl font-semibold">${price.toLocaleString("es-CO")}</span>
                <span className="text-xs text-[var(--text-muted)]">
                  .000 COP / {annual ? "año" : "mes"}
                </span>
              </div>
              {annual && (
                <div className="text-[11px] text-emerald-400 mt-1">
                  Ahorras ${(p.monthly * 2).toLocaleString("es-CO")}.000 vs pagar mensual.
                </div>
              )}
              <ul className="mt-5 space-y-2">
                {p.features.map((f) => (
                  <li key={f} className="text-sm text-[var(--text-secondary)] flex items-start gap-2">
                    <CheckCircle size={14} className="text-emerald-400 mt-0.5 shrink-0" weight="duotone" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Button
                onClick={() => document.getElementById("vip")?.scrollIntoView({ behavior: "smooth" })}
                className={`w-full mt-6 h-11 ${p.highlight ? "btn-cta-grad" : ""}`}
                variant={p.highlight ? undefined : "outline"}
                data-testid={`pricing-cta-${p.name.toLowerCase().replace(/\W+/g,'-')}`}>
                {p.cta} <ArrowRight size={14} weight="bold" />
              </Button>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// -----------------------------------------------------------------------
// FEATURES GRID
// -----------------------------------------------------------------------
function FeaturesGrid() {
  const items = [
    { Icon: Package,     title: "Importador Dropi combo-safe",
      desc: "Un pedido con 3 líneas se importa como UNA orden con el recaudo correcto. Adiós al inflado." },
    { Icon: PhoneCall,   title: "Sofía IA — voz humana colombiana",
      desc: "Hasta 5 intentos por pedido. Registra el resultado y crea tickets automáticamente." },
    { Icon: WhatsappLogo, title: "WhatsApp 24h + templates Meta",
      desc: "Detecta la ventana de 24h. Fuera de ella usa plantillas aprobadas por Chatea Pro." },
    { Icon: Sparkle,     title: "Prompts pro (6-block ElevenLabs)",
      desc: "Genera scripts Sofía siguiendo Personalidad / Entorno / Tono / Objetivo / Guardrails / Herramientas." },
    { Icon: Clock,       title: "Semáforo por transportadora",
      desc: "Rojo/Amarillo/Verde con los días máximos de cada carrier — Servientrega 8, Envía 1, TCC 3." },
    { Icon: ChartLineUp, title: "Métricas de recuperación",
      desc: "Cuánto recuperaste vs cuánto se hubiera devuelto. Por día, carrier y vendedor." },
  ];
  return (
    <section id="features" className="max-w-6xl mx-auto px-5 pb-16" data-testid="funnel-features">
      <div className="text-center mb-8">
        <div className="pill-grad inline-flex items-center gap-2 mb-3">
          <Robot size={12} /> Funciones
        </div>
        <h2 className="text-3xl md:text-4xl font-semibold">
          Todo lo que necesitas para <span className="grad-text">no perder pedidos</span>.
        </h2>
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        {items.map(({ Icon, title, desc }) => (
          <div key={title}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] backdrop-blur-xl p-5 transition hover:-translate-y-1"
            style={{
              transition: "transform 220ms ease, box-shadow 220ms ease",
            }}
            onMouseEnter={(e) => e.currentTarget.style.boxShadow =
              "0 20px 45px rgba(0,0,0,0.35), 0 0 32px -6px color-mix(in oklab, var(--accent) 55%, transparent)"}
            onMouseLeave={(e) => e.currentTarget.style.boxShadow = "none"}
            data-testid={`feature-${title.toLowerCase().split(" ")[0]}`}>
            <Icon size={22} className="text-white mb-3" weight="duotone" />
            <h4 className="font-semibold text-white text-sm mb-1">{title}</h4>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

// -----------------------------------------------------------------------
// FAQ
// -----------------------------------------------------------------------
function FaqSection() {
  const [open, setOpen] = useState(0);
  const faqs = [
    { q: "¿Funciona con mi cuenta de Chatea Pro / Telnyx / Twilio?",
      a: "Sí. Cada organización configura sus PROPIAS llaves desde /app/config — encriptadas en el servidor. Nunca las vemos en texto plano." },
    { q: "¿Sofía puede sonar como una colombiana real?",
      a: "Sí. Usamos ElevenLabs con voz clonada colombiana. En Growth incluye voces por país (CO/EC/CL). En Scale · Fundador clonamos hasta 2 voces custom." },
    { q: "¿Y si el cliente no responde en 24h?",
      a: "Meta cierra la ventana de conversación. Litper detecta esto y automáticamente cambia a plantillas aprobadas — nunca envía mensajes que Meta rechace." },
    { q: "¿Cuánto tardo en montarlo?",
      a: "Menos de 3 horas con onboarding 1:1 (incluido en Growth y Scale). Sin onboarding, un operador técnico lo tiene listo en un día." },
    { q: "¿Puedo probar antes de pagar?",
      a: "Sí. Únete al Grupo VIP (arriba) y te damos acceso al panel demo con datos reales de prueba." },
    { q: "¿Y la garantía?",
      a: "30 días. Si Litper Connect no te recupera pedidos que paguen el sistema, te devolvemos el 100%. Sin letras chicas." },
  ];
  return (
    <section id="faq" className="max-w-3xl mx-auto px-5 pb-16" data-testid="funnel-faq">
      <div className="text-center mb-6">
        <div className="pill-grad inline-flex items-center gap-2 mb-3">
          <ShieldCheck size={12} /> Preguntas frecuentes
        </div>
        <h2 className="text-3xl md:text-4xl font-semibold">Antes de decidir</h2>
      </div>
      <div className="space-y-2">
        {faqs.map((f, i) => (
          <div key={i}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] backdrop-blur"
            data-testid={`faq-item-${i}`}>
            <button onClick={() => setOpen(open === i ? -1 : i)}
              className="w-full text-left px-4 py-3 flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-white">{f.q}</span>
              <span className="text-xs text-[var(--text-muted)] font-mono">{open === i ? "−" : "+"}</span>
            </button>
            {open === i && (
              <div className="px-4 pb-3 text-sm text-[var(--text-secondary)] leading-relaxed">{f.a}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
