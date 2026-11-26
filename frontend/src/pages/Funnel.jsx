import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import { GRATIS, PLANES, WHATSAPP_VENTAS } from "../constants/planes";
import {
  ArrowRight, ChatsCircle, CheckCircle, Lifebuoy, Package, PhoneCall, TrafficSignal, UsersThree, WhatsappLogo,
} from "@phosphor-icons/react";
import "../dia.css";
import "./inicio.css";

/**
 * Página de inicio de Zynex (ruta "/").
 * Reglas de contenido: sin cifras de resultados, sin testimonios y sin promesas de ventas.
 * El tablero del inicio es una simulación rotulada como ejemplo: no usa datos de nadie.
 */

const usd = (n) => `US$${Number.isInteger(n) ? n : n.toFixed(2).replace(".", ",")}`;

// Simulación del tablero: cada pedido avanza por estos pasos.
const PASOS = [
  { estado: "En reparto", tono: "azul", nota: "Va en camino" },
  { estado: "Novedad", tono: "ambar", nota: "El cliente no estaba" },
  { estado: "Zynex llama", tono: "violeta", nota: "Confirmando nueva entrega" },
  { estado: "Reprogramado", tono: "verde", nota: "Entrega acordada para mañana" },
];
const PEDIDOS = [
  { id: "48213", ciudad: "Cali", paso: 0 },
  { id: "48207", ciudad: "Bogotá", paso: 1 },
  { id: "48196", ciudad: "Medellín", paso: 2 },
  { id: "48188", ciudad: "Barranquilla", paso: 3 },
  { id: "48174", ciudad: "Pereira", paso: 0 },
];

function Tablero() {
  const [filas, setFilas] = useState(PEDIDOS);
  const [turno, setTurno] = useState(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return undefined;
    const t = setInterval(() => setTurno((n) => n + 1), 2200);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (!turno) return;
    setFilas((f) => f.map((p, i) => (i === turno % f.length ? { ...p, paso: (p.paso + 1) % PASOS.length } : p)));
  }, [turno]);
  const activa = turno ? turno % filas.length : -1;
  return (
    <div className="ini-tablero" data-testid="inicio-tablero" aria-label="Ejemplo del tablero de Zynex">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-2 text-sm font-medium text-white">
          <span className="ini-pulso" aria-hidden="true" /> Logística · hoy
        </div>
        <span className="text-[11px] rounded-full border border-zinc-700 px-2 py-0.5 text-zinc-400">Ejemplo</span>
      </div>
      <ul>
        {filas.map((p, i) => {
          const s = PASOS[p.paso];
          return (
            <li key={p.id} className={`ini-fila ${i === activa ? "ini-fila-activa" : ""}`}>
              <div className="min-w-0">
                <div className="text-sm text-white ini-num">Pedido {p.id} · {p.ciudad}</div>
                <div className="text-xs text-zinc-400 truncate">{s.nota}</div>
              </div>
              <span className={`ini-chip ini-${s.tono}`}>
                {s.estado === "Zynex llama" && <PhoneCall size={12} weight="fill" />} {s.estado}
              </span>
            </li>
          );
        })}
      </ul>
      <div className="px-4 py-3 border-t border-zinc-800 text-xs text-zinc-400">
        Zynex lee tus pedidos de Dropi cada 5 minutos y te dice cuáles necesitan una llamada.
      </div>
    </div>
  );
}

const PRODUCTOS = [
  { Icon: TrafficSignal, nombre: "Semáforo", precio: "Gratis",
    texto: "Antes de despachar, te dice si a esa ciudad conviene enviar con esa transportadora." },
  { Icon: Package, nombre: "Logística", precio: `Desde ${usd(61)} al mes`,
    texto: "Tus pedidos de Dropi por estado: reparto, novedad, oficina y entregado. Ves qué se está quedando quieto." },
  { Icon: PhoneCall, nombre: "Llamadas", precio: `${usd(124)} al mes`,
    texto: "Un agente de voz llama al cliente cuando hay novedad o el paquete espera en oficina, y deja anotado qué respondió." },
];

const ARRANQUE = [
  { n: "1", titulo: "Conecta tu Dropi", texto: "Entras con tu cuenta de Dropi una vez. No necesitas API ni instalar nada." },
  { n: "2", titulo: "Mira qué haría Zynex", texto: "Arranca en modo sombra: te muestra a quién llamaría y por qué, sin contactar a nadie." },
  { n: "3", titulo: "Enciéndelo cuando quieras", texto: "Tú eliges qué estados atiende y con qué plantilla. Si tu bot ya escribió, Zynex no repite el mensaje: llama." },
];

const FAQ = [
  { q: "¿Necesito la API de Dropi?", a: "No. Zynex lee tus pedidos con tu inicio de sesión de Dropi, en modo de solo lectura." },
  { q: "¿Zynex le escribe a mis clientes sin avisarme?", a: "No. Empieza en modo sombra: solo muestra lo que haría. Nada sale hasta que tú lo enciendes." },
  { q: "¿Puedo pagar solo Logística o solo Llamadas?", a: "Sí, se pagan aparte. Si llevas las dos, pagas 15 % menos que por separado." },
  { q: "¿Qué es el código de socio?", a: "Si llegaste por un socio de Zynex, su código te da 20 % menos mientras sigas con tu plan." },
  { q: "¿Y si me trabo?", a: "Dentro de la app hay un botón de Ayuda: escribes, y una persona del equipo te responde ahí mismo. También está el grupo VIP de usuarios." },
  { q: "¿Dónde quedan mis llaves y datos?", a: "Las llaves se guardan cifradas y no se muestran en pantalla. Cada cuenta solo ve sus propios pedidos." },
];

export default function FunnelPage() {
  const [conCodigo, setConCodigo] = useState(false);
  return (
    <div className="ini min-h-screen bg-zinc-950 text-zinc-100" data-testid="funnel-page">
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-950/85 backdrop-blur">
        <div className="ini-wrap flex items-center justify-between gap-3 py-3">
          <a href="/" className="flex items-center gap-2 font-semibold text-white">
            <img src="/lyan.webp" alt="" className="w-7 h-7 rounded-full object-cover" /> Zynex
          </a>
          <nav className="hidden md:flex items-center gap-6 text-sm text-zinc-400" aria-label="Secciones">
            <a href="#producto" className="hover:text-white">Producto</a>
            <a href="#empezar" className="hover:text-white">Cómo empiezas</a>
            <a href="#precios" className="hover:text-white">Precios</a>
            <a href="#preguntas" className="hover:text-white">Preguntas</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="ini-btn ini-btn-2" data-testid="funnel-login">Entrar</Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main>
        <section className="ini-wrap grid gap-10 lg:grid-cols-[1.05fr_1fr] items-center py-14 md:py-20">
          <div>
            <p className="text-sm text-cyan-300 mb-4">Para tiendas que venden contra entrega con Dropi</p>
            <h1 className="ini-h1" data-testid="funnel-hook">
              Sabe qué pedido se está cayendo <span className="ini-acento">antes de que se devuelva.</span>
            </h1>
            <p className="ini-lead mt-5">
              Zynex vigila tus pedidos de Dropi, te muestra los que necesitan atención y llama al cliente por ti cuando hay novedad.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link to="/register" className="ini-btn ini-btn-1" data-testid="funnel-cta">
                Crear mi cuenta gratis <ArrowRight size={16} weight="bold" />
              </Link>
              <a href="#precios" className="ini-btn ini-btn-2">Ver precios</a>
            </div>
            <p className="mt-4 text-sm text-zinc-400">El Semáforo es gratis. No pide tarjeta.</p>
          </div>
          <Tablero />
        </section>

        <section id="producto" className="border-t border-zinc-800">
          <div className="ini-wrap py-16">
            <h2 className="ini-h2">Tres apps, una sola ficha del pedido</h2>
            <p className="ini-lead mt-3">Lo que ves en Logística es lo mismo que usa Llamadas. Empiezas por la que necesites.</p>
            <div className="mt-10 grid gap-8 md:grid-cols-3">
              {PRODUCTOS.map(({ Icon, nombre, precio, texto }) => (
                <article key={nombre} className="ini-prod">
                  <Icon size={28} className="text-cyan-300" />
                  <h3 className="mt-4 text-lg font-semibold text-white">{nombre}</h3>
                  <p className="mt-2 text-sm text-zinc-400 ini-texto">{texto}</p>
                  <p className="mt-4 text-sm font-medium text-white ini-num">{precio}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="empezar" className="border-t border-zinc-800">
          <div className="ini-wrap py-16 grid gap-10 lg:grid-cols-[1fr_1.4fr]">
            <div>
              <h2 className="ini-h2">Empiezas sin tocar a ningún cliente</h2>
              <p className="ini-lead mt-3">Primero ves, después decides.</p>
            </div>
            <ol className="space-y-6">
              {ARRANQUE.map((p) => (
                <li key={p.n} className="flex gap-4">
                  <span className="ini-paso ini-num" aria-hidden="true">{p.n}</span>
                  <div>
                    <h3 className="text-base font-semibold text-white">{p.titulo}</h3>
                    <p className="mt-1 text-sm text-zinc-400 ini-texto">{p.texto}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="precios" className="border-t border-zinc-800">
          <div className="ini-wrap py-16">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="ini-h2">Precios</h2>
                <p className="ini-lead mt-3">Logística y Llamadas se pagan aparte. Juntas, 15 % menos.</p>
              </div>
              <label className="ini-switch" data-testid="precios-codigo">
                <input type="checkbox" checked={conCodigo} onChange={(e) => setConCodigo(e.target.checked)} />
                <span>Tengo código de socio (20 % menos)</span>
              </label>
            </div>
            <ul className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {PLANES.map((p) => (
                <li key={p.id} className={`ini-plan ${p.paquete ? "ini-plan-paquete" : ""}`}>
                  {p.paquete && <span className="ini-etiqueta">Las dos apps</span>}
                  <h3 className="text-base font-semibold text-white">{p.nombre}</h3>
                  <p className="mt-1 text-sm text-zinc-400">{p.incluye}</p>
                  <p className="mt-4 text-3xl font-semibold text-white ini-num">
                    {usd(conCodigo ? p.conCodigo : p.lista)}<span className="text-sm font-normal text-zinc-400"> al mes</span>
                  </p>
                  {conCodigo && <p className="text-xs text-zinc-400 ini-num">Sin código: {usd(p.lista)}</p>}
                  <a href={p.pago || `${WHATSAPP_VENTAS}?text=${encodeURIComponent(`Hola, quiero el plan ${p.nombre} de Zynex`)}`}
                     target="_blank" rel="noreferrer" className="ini-btn ini-btn-2 mt-5" data-testid={`precio-${p.id}`}>
                    {p.pago ? "Pagar este plan" : "Pedir este plan"}
                  </a>
                </li>
              ))}
            </ul>
            <p className="mt-6 text-sm text-zinc-400 flex flex-wrap gap-x-5 gap-y-2">
              {GRATIS.map((g) => (
                <span key={g} className="inline-flex items-center gap-1.5"><CheckCircle size={16} className="text-emerald-300" /> {g}</span>
              ))}
            </p>
            <p className="mt-2 text-xs text-zinc-400">Precios en dólares, sin impuestos. El plan de Llamadas incluye 200 minutos al mes.</p>
          </div>
        </section>

        <section className="border-t border-zinc-800">
          <div className="ini-wrap py-16 grid gap-8 md:grid-cols-3">
            <div className="md:col-span-1">
              <h2 className="ini-h2">No quedas solo</h2>
              <p className="ini-lead mt-3">El soporte viene con cualquier plan.</p>
            </div>
            <div className="md:col-span-2 grid gap-6 sm:grid-cols-3">
              <div><Lifebuoy size={22} className="text-cyan-300" /><h3 className="mt-3 font-semibold text-white">Ayuda en la app</h3><p className="mt-1 text-sm text-zinc-400">Escribes desde cualquier pantalla y una persona te responde ahí.</p></div>
              <div><ChatsCircle size={22} className="text-cyan-300" /><h3 className="mt-3 font-semibold text-white">Lo arreglamos por ti</h3><p className="mt-1 text-sm text-zinc-400">Si quieres, das permiso por unas horas y entramos a tu cuenta. Tú ves quién entró.</p></div>
              <div><UsersThree size={22} className="text-cyan-300" /><h3 className="mt-3 font-semibold text-white">Grupo VIP</h3><p className="mt-1 text-sm text-zinc-400">Comunidad de usuarios para resolver dudas y enterarte de lo nuevo.</p></div>
            </div>
          </div>
        </section>

        <section id="preguntas" className="border-t border-zinc-800">
          <div className="ini-wrap py-16 max-w-3xl">
            <h2 className="ini-h2">Antes de empezar</h2>
            <div className="mt-8 divide-y divide-zinc-800 border-y border-zinc-800">
              {FAQ.map((f) => (
                <details key={f.q} className="ini-faq">
                  <summary>{f.q}</summary>
                  <p className="pb-4 text-sm text-zinc-400 ini-texto">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-zinc-800">
          <div className="ini-wrap py-20 text-center">
            <h2 className="ini-h2">Conecta tu Dropi y mira tus pedidos hoy</h2>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <Link to="/register" className="ini-btn ini-btn-1">Crear mi cuenta gratis <ArrowRight size={16} weight="bold" /></Link>
              <a href={WHATSAPP_VENTAS} target="_blank" rel="noreferrer" className="ini-btn ini-btn-2"><WhatsappLogo size={16} weight="fill" /> Hablar con una persona</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-zinc-800">
        <div className="ini-wrap py-6 flex flex-wrap items-center justify-between gap-3 text-sm text-zinc-400">
          <span>Zynex</span>
          <span className="flex flex-wrap gap-4">
            <a href="mailto:zynexproai@gmail.com" className="hover:text-white">zynexproai@gmail.com</a>
            <Link to="/login" className="hover:text-white">Entrar</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}
