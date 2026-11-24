import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import Constellation from "../components/Constellation";
import ThemeToggle from "../components/ThemeToggle";
import AgentFromPrompt from "../components/AgentFromPrompt";
import PageHelp from "../components/PageHelp";
import {
  ArrowRight, ArrowUp, Bank, Buildings, CaretDown, ForkKnife, Key, Package, PhoneCall,
  Plugs, ShoppingBag, Stethoscope, WhatsappLogo, Envelope,
} from "@phosphor-icons/react";

/**
 * Página de presentación de Zynex OS (ruta "/").
 *
 * Reglas de contenido: nada de cifras de resultados, testimonios, garantías,
 * plazos, conteos ni precios. Solo se describe lo que el producto hace, y la
 * demostración va rotulada como ejemplo.
 */

// Casos de uso: la clave coincide con las plantillas del creador de agentes.
const CASOS = [
  { key: "clinica", Icon: Stethoscope, titulo: "Clínica",
    texto: "Recuerda la cita un día antes, confirma si el paciente asistirá y ofrece reprogramar." },
  { key: "inmobiliaria", Icon: Buildings, titulo: "Inmobiliaria",
    texto: "Contacta a quien pidió información, pregunta presupuesto y zona, y agenda la visita." },
  { key: "restaurante", Icon: ForkKnife, titulo: "Restaurante",
    texto: "Confirma las reservas del día, el número de personas y si hay alergias." },
  { key: "cobranza", Icon: Bank, titulo: "Cobranza",
    texto: "Recuerda un pago pendiente con respeto y registra cuándo se compromete a pagar el cliente." },
  { key: "tienda", Icon: ShoppingBag, titulo: "Tienda en línea",
    texto: "Confirma el pedido, la dirección de entrega y el valor a pagar." },
  { key: "oficina", Icon: Package, titulo: "Reclamo en oficina",
    texto: "Avisa que el paquete espera en la oficina de envíos y confirma cuándo lo recogerá el cliente." },
];

const PASOS = [
  { n: "1", titulo: "Descríbelo con un prompt",
    texto: "Escribe con tus palabras qué hace tu negocio y qué debe hacer el agente. También puedes partir de una plantilla." },
  { n: "2", titulo: "Revisa la propuesta y aplícala",
    texto: "El asistente prepara nombre, saludo, guion y cierre. Cambias lo que quieras; nada se activa hasta que pulsas «Aplicar»." },
  { n: "3", titulo: "Conecta y haz una llamada de prueba",
    texto: "Eliges la voz, conectas tu número y tu WhatsApp, y el agente te llama a ti primero. La app te dice qué falta en cada paso." },
];

const CONECTORES = [
  { Icon: PhoneCall, titulo: "Voz y telefonía",
    texto: "Conectas tu proveedor de telefonía y eliges la voz. El agente llama desde tu número." },
  { Icon: WhatsappLogo, titulo: "WhatsApp",
    texto: "Conectas tu cuenta de WhatsApp para empresas. El agente escribe con tus plantillas aprobadas." },
  { Icon: Plugs, titulo: "Conectores MCP",
    texto: "Dale al agente herramientas de tus propios sistemas (calendario, inventario, CRM) con la dirección de un servidor MCP. Tú decides cuáles activa y cuáles piden confirmación." },
  { Icon: Key, titulo: "Tu propia llave de IA",
    texto: "Usas la llave de tu proveedor de inteligencia artificial. Le pagas a él directamente lo que consumas y ves ese costo en su panel, sin recargo oculto." },
];

const FAQ = [
  { q: "¿Necesito saber programar?",
    a: "No. Escribes qué debe hacer el agente como se lo explicarías a una persona. El asistente lo convierte en un guion que puedes leer y corregir." },
  { q: "¿El asistente hace cambios sin avisarme?",
    a: "No. Antes de cualquier cambio te muestra qué va a hacer y espera a que pulses «Aplicar». Cada acción queda registrada en una bitácora que puedes consultar." },
  { q: "¿Cuánto cuesta?",
    a: "Precios: por minuto y por conversación, visibles antes de pagar. Lo que consumas con tus propios proveedores (telefonía, voz, WhatsApp, inteligencia artificial) se lo pagas a ellos." },
  { q: "¿Qué necesito para que el agente pueda llamar?",
    a: "Una voz y un número de teléfono conectados. Para escribir por WhatsApp, tu cuenta de WhatsApp para empresas. Al crear el agente, la app te muestra la lista exacta de lo que falta." },
  { q: "¿Sirve para mi tipo de empresa?",
    a: "Sirve si tu equipo llama o escribe a clientes para tareas repetidas: recordar, confirmar, calificar, cobrar o avisar. Para operaciones específicas, como envíos contra entrega, hay paquetes opcionales que se instalan desde tu perfil." },
  { q: "¿Qué es un conector MCP?",
    a: "Es una dirección web que le da al agente herramientas nuevas, por ejemplo consultar tu agenda. Conecta solo servidores en los que confíes: sus herramientas pueden actuar en tu nombre." },
  { q: "¿Dónde quedan mis llaves?",
    a: "Se guardan cifradas en el servidor y no se vuelven a mostrar completas. Puedes reemplazarlas o borrarlas cuando quieras." },
];

function Cta({ testId }) {
  return (
    <Link to="/register" data-testid={testId}
          className="btn-cta-grad inline-flex items-center justify-center gap-2 h-12 px-6 rounded-sm text-[15px] font-semibold w-full sm:w-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300">
      Crear mi agente gratis <ArrowRight size={16} weight="bold" />
    </Link>
  );
}

function Eyebrow({ children }) {
  return (
    <div className="text-xs uppercase tracking-[0.15em] font-medium font-mono text-[var(--text-muted)] mb-2">
      {children}
    </div>
  );
}

export default function FunnelPage() {
  const demoRef = useRef(null);
  const [seed, setSeed] = useState(null); // { key, n } → carga una plantilla en la demostración

  const verEjemplo = (key) => {
    setSeed((s) => ({ key, n: (s?.n || 0) + 1 }));
    const el = demoRef.current;
    if (!el) return;
    let smooth = true;
    try { smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { /* noop */ }
    el.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] relative overflow-x-hidden"
         data-testid="funnel-page">
      <Constellation density={70} />

      {/* Barra superior */}
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[color-mix(in_oklab,var(--bg-primary)_80%,transparent)] border-b border-[var(--border)]">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-3 px-4 sm:px-5 py-3">
          <Link to="/" className="flex items-center gap-2.5 min-w-0" aria-label="Zynex OS, inicio">
            <span className="relative w-8 h-8 grid place-items-center shrink-0" aria-hidden="true">
              <span className="absolute inset-0 rounded-sm" style={{ background: "var(--accent-grad)" }} />
              <span className="absolute inset-[1px] rounded-[3px] bg-[var(--bg-primary)] grid place-items-center">
                <span className="text-[14px] font-bold grad-text tracking-tight">Z</span>
              </span>
            </span>
            <span className="font-semibold text-sm truncate">Zynex <span className="grad-text">OS</span></span>
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-[13px] text-[var(--text-secondary)]" aria-label="Secciones">
            <a href="#casos" className="hover:text-[var(--text-primary)] transition">Casos de uso</a>
            <a href="#como-funciona" className="hover:text-[var(--text-primary)] transition">Cómo funciona</a>
            <a href="#conectores" className="hover:text-[var(--text-primary)] transition">Conectores</a>
            <a href="#preguntas" className="hover:text-[var(--text-primary)] transition">Preguntas</a>
          </nav>
          <div className="flex items-center gap-2 shrink-0">
            <Link to="/login" data-testid="funnel-nav-login"
                  className="text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition px-3 py-1.5 rounded-sm border border-[var(--border)]">
              Entrar
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="relative z-10">
        {/* 1 · Primera pantalla: la frase y el producto funcionando */}
        <section className="max-w-6xl mx-auto px-4 sm:px-5 pt-8 pb-12 md:pt-14 md:pb-20" data-testid="funnel-hero">
          <div className="grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] gap-8 lg:gap-10 items-start">
            <div className="lg:pt-6">
              <Eyebrow>Zynex OS · Agentes para cualquier empresa</Eyebrow>
              <h1 className="text-3xl sm:text-4xl lg:text-[44px] font-semibold leading-[1.1] tracking-tight"
                  data-testid="funnel-hero-headline">
                Crea un agente de IA que <span className="grad-text">llama y escribe por WhatsApp</span> a tus clientes.
              </h1>
              <p className="mt-4 text-base sm:text-lg text-[var(--text-secondary)] leading-relaxed max-w-xl"
                 data-testid="funnel-hero-subhead">
                Lo describes con un prompt; pagas por uso.
              </p>
              <div className="mt-6">
                <Cta testId="funnel-hero-cta" />
              </div>
              <p className="mt-3 text-sm text-[var(--text-muted)]">
                ¿Ya tienes cuenta?{" "}
                <Link to="/login" className="underline underline-offset-2 hover:text-[var(--text-primary)]">Entra aquí</Link>
              </p>
            </div>

            {/* La demostración: la frase se convierte en agente a la vista */}
            <div ref={demoRef} id="demo" className="scroll-mt-20 min-w-0" data-testid="funnel-demo">
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs uppercase tracking-[0.15em] font-medium font-mono text-[var(--text-muted)]">
                  Pruébalo aquí
                </span>
                <span className="text-xs font-mono text-[var(--text-muted)]">de la frase al agente</span>
              </div>
              <AgentFromPrompt demo seed={seed} />
            </div>
          </div>
        </section>

        {/* 2 · Casos de uso por industria */}
        <section id="casos" className="scroll-mt-20 border-t border-[var(--border)]" data-testid="funnel-casos">
          <div className="max-w-6xl mx-auto px-4 sm:px-5 py-12 md:py-16">
            <Eyebrow>Casos de uso</Eyebrow>
            <h2 className="text-xl sm:text-2xl tracking-tight font-medium mb-6">Un agente para la tarea que hoy haces a mano</h2>
            <ul className="grid sm:grid-cols-2 lg:grid-cols-3 border-l border-t border-[var(--border)]">
              {CASOS.map(({ key, Icon, titulo, texto }) => (
                <li key={key} className="border-r border-b border-[var(--border)] p-5 flex flex-col"
                    data-testid={`funnel-caso-${key}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Icon size={18} weight="duotone" className="text-[var(--accent)]" aria-hidden="true" />
                    <h3 className="text-lg font-medium">{titulo}</h3>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] leading-relaxed flex-1">{texto}</p>
                  <button type="button" onClick={() => verEjemplo(key)}
                          data-testid={`funnel-caso-ver-${key}`}
                          className="mt-3 self-start inline-flex items-center gap-1.5 text-sm text-[var(--accent)] underline underline-offset-4 decoration-transparent hover:decoration-current transition py-1">
                    Ver este ejemplo <ArrowUp size={13} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* 3 · Cómo funciona */}
        <section id="como-funciona" className="scroll-mt-20 border-t border-[var(--border)]" data-testid="funnel-pasos">
          <div className="max-w-6xl mx-auto px-4 sm:px-5 py-12 md:py-16">
            <Eyebrow>Cómo funciona</Eyebrow>
            <h2 className="text-xl sm:text-2xl tracking-tight font-medium mb-6">Tres pasos</h2>
            <ol className="grid md:grid-cols-3 border-l border-t border-[var(--border)]">
              {PASOS.map((p) => (
                <li key={p.n} className="border-r border-b border-[var(--border)] p-5" data-testid={`funnel-paso-${p.n}`}>
                  <div className="font-mono text-sm text-[var(--accent)] mb-2" aria-hidden="true">{p.n.padStart(2, "0")}</div>
                  <h3 className="text-lg font-medium mb-1.5">{p.titulo}</h3>
                  <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{p.texto}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* 4 · Conectores */}
        <section id="conectores" className="scroll-mt-20 border-t border-[var(--border)]" data-testid="funnel-conectores">
          <div className="max-w-6xl mx-auto px-4 sm:px-5 py-12 md:py-16">
            <Eyebrow>Conectores</Eyebrow>
            <h2 className="text-xl sm:text-2xl tracking-tight font-medium mb-6">Trabaja con tus cuentas y tus sistemas</h2>
            <ul className="grid sm:grid-cols-2 border-l border-t border-[var(--border)]">
              {CONECTORES.map(({ Icon, titulo, texto }) => (
                <li key={titulo} className="border-r border-b border-[var(--border)] p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <Icon size={18} weight="duotone" className="text-[var(--accent)]" aria-hidden="true" />
                    <h3 className="text-lg font-medium">{titulo}</h3>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{texto}</p>
                </li>
              ))}
            </ul>
            <p className="mt-5 text-sm text-[var(--text-secondary)] border border-[var(--border)] rounded-sm px-4 py-3"
               data-testid="funnel-precios">
              <span className="font-medium text-[var(--text-primary)]">Precios:</span> por minuto y por conversación, visibles antes de pagar.
            </p>
          </div>
        </section>

        {/* 5 · Preguntas frecuentes */}
        <section id="preguntas" className="scroll-mt-20 border-t border-[var(--border)]" data-testid="funnel-faq">
          <div className="max-w-3xl mx-auto px-4 sm:px-5 py-12 md:py-16">
            <Eyebrow>Preguntas frecuentes</Eyebrow>
            <h2 className="text-xl sm:text-2xl tracking-tight font-medium mb-6">Antes de empezar</h2>
            <div className="border-t border-[var(--border)]">
              {FAQ.map((f, i) => (
                <details key={f.q} className="group border-b border-[var(--border)]" data-testid={`funnel-faq-${i}`}>
                  <summary className="flex items-center justify-between gap-4 cursor-pointer list-none py-4 text-base font-medium [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <CaretDown size={16} aria-hidden="true"
                               className="shrink-0 text-[var(--text-muted)] transition-transform group-open:rotate-180" />
                  </summary>
                  <p className="pb-4 text-sm text-[var(--text-secondary)] leading-relaxed">{f.a}</p>
                </details>
              ))}
            </div>
            <div className="mt-8">
              <PageHelp helpKey="funnel" linkAsk={false} />
            </div>
          </div>
        </section>

        {/* 6 · Cierre */}
        <section className="border-t border-[var(--border)]" data-testid="funnel-cierre">
          <div className="max-w-3xl mx-auto px-4 sm:px-5 py-14 md:py-20 text-center">
            <h2 className="text-2xl sm:text-3xl tracking-tight font-semibold mb-3">Empieza por una frase</h2>
            <p className="text-sm sm:text-base text-[var(--text-secondary)] leading-relaxed mb-6 max-w-xl mx-auto">
              Crea tu cuenta, describe tu negocio y revisa la propuesta de tu primer agente.
            </p>
            <Cta testId="funnel-final-cta" />
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-[var(--border)] py-8 text-sm text-[var(--text-muted)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-5 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>Zynex OS</span>
          <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
            <a href="mailto:zynexproai@gmail.com" data-testid="funnel-support-email"
               className="inline-flex items-center gap-1.5 hover:text-[var(--text-primary)] transition">
              <Envelope size={14} aria-hidden="true" /> zynexproai@gmail.com
            </a>
            <a href="https://wa.me/573144644054" target="_blank" rel="noreferrer" data-testid="funnel-support-whatsapp"
               className="inline-flex items-center gap-1.5 hover:text-[var(--text-primary)] transition">
              <WhatsappLogo size={14} aria-hidden="true" /> Soporte por WhatsApp
            </a>
            <Link to="/login" data-testid="funnel-footer-login" className="hover:text-[var(--text-primary)] transition">Entrar</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
