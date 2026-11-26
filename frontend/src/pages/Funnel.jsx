import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import ThemeToggle from "../components/ThemeToggle";
import { GRATIS, PLANES, WHATSAPP_VENTAS } from "../constants/planes";
import { ArrowRight, WhatsappLogo } from "@phosphor-icons/react";
import "../dia.css";
import "./inicio.css";

/**
 * Página de inicio de Zynex (ruta "/"): la torre de control de Lyan, en 3D.
 * Reglas de contenido: sin cifras de resultados, sin testimonios y sin promesas de ventas.
 * La escena es decoración: no usa datos de nadie.
 */
const usd = (n) => `US$${Number.isInteger(n) ? n : n.toFixed(2).replace(".", ",")}`;

const APPS = [
  { n: "01", nombre: "Semáforo", precio: "Gratis", texto: "Antes de despachar te dice si a esa ciudad conviene enviar con esa transportadora." },
  { n: "02", nombre: "Logística", precio: `Desde ${usd(61)} al mes`, texto: "Tus pedidos de Dropi por estado. Ves cuál se quedó quieto antes de que se devuelva." },
  { n: "03", nombre: "Llamadas", precio: `${usd(124)} al mes`, texto: "Un agente de voz llama al cliente cuando hay novedad y deja anotado qué respondió." },
];
const FAQ = [
  { q: "¿Necesito la API de Dropi?", a: "No. Zynex lee tus pedidos con tu inicio de sesión de Dropi, en modo de solo lectura." },
  { q: "¿Le escribe a mis clientes sin avisarme?", a: "No. Empieza en modo sombra: solo muestra lo que haría. Nada sale hasta que tú lo enciendes." },
  { q: "¿Puedo pagar solo una app?", a: "Sí, se pagan aparte. Si llevas Logística y Llamadas juntas, pagas 15 % menos." },
  { q: "¿Y si me trabo?", a: "Dentro de la app hay un botón de Ayuda: escribes y una persona del equipo te responde ahí mismo. También está el grupo VIP." },
];

export default function FunnelPage() {
  const lienzo = useRef(null);
  const [carga, setCarga] = useState(0);
  const [estado, setEstado] = useState("cargando");      // cargando | listo | plano (sin 3D)
  const [conCodigo, setConCodigo] = useState(false);

  useEffect(() => {
    let escena, vivo = true;
    import("../three/escenaLyan").then(({ montar }) => {
      if (!vivo || !lienzo.current) return;
      escena = montar(lienzo.current, {
        onProgreso: (p) => vivo && setCarga(Math.round(p * 100)),
        onListo: () => vivo && setEstado("listo"),
        onError: () => vivo && setEstado("plano"),
      });
      if (!escena) setEstado("plano");
    }).catch(() => vivo && setEstado("plano"));
    return () => { vivo = false; escena?.destruir(); };
  }, []);

  return (
    <div className={`tc tc-${estado}`} data-testid="funnel-page">
      <canvas ref={lienzo} className="tc-lienzo" aria-hidden="true" />
      {estado === "plano" && <img src="/lyan.webp" alt="" className="tc-plano" />}

      <div className="tc-carga" role="status" aria-live="polite" data-testid="inicio-carga">
        <div className="tc-hex" aria-hidden="true"><span>Z</span></div>
        <div className="tc-carga-txt">Despertando a Lyan <b className="tc-num">{carga}%</b></div>
        <div className="tc-barra"><i style={{ transform: `scaleX(${carga / 100})` }} /></div>
      </div>

      <header className="tc-top">
        <a href="/" className="tc-marca"><span className="tc-hex tc-hex-s" aria-hidden="true"><span>Z</span></span> ZYNEX</a>
        <nav aria-label="Secciones">
          <a href="#rutas">Cómo funciona</a><a href="#apps">Apps</a><a href="#precios">Precios</a><a href="#preguntas">Preguntas</a>
        </nav>
        <div className="tc-top-der">
          <Link to="/login" className="tc-btn tc-btn-2" data-testid="funnel-login">Entrar</Link>
          <ThemeToggle />
        </div>
      </header>

      <main>
        <section className="tc-pantalla tc-hero">
          <div className="tc-col">
            <p className="tc-rotulo">Torre de control para contra entrega</p>
            <h1 className="tc-h1" data-testid="funnel-hook">Lyan vigila<br />tus pedidos.<br /><em>Tú decides.</em></h1>
            <p className="tc-lead">Conectas tu Dropi y Zynex te muestra qué pedido se está cayendo, antes de que se devuelva. Si hay novedad, llama al cliente por ti.</p>
            <div className="tc-acciones">
              <Link to="/register" className="tc-btn tc-btn-1" data-testid="funnel-cta">Crear mi cuenta gratis <ArrowRight size={16} weight="bold" /></Link>
              <a href="#precios" className="tc-btn tc-btn-2">Ver precios</a>
            </div>
            <p className="tc-pista">Toca cualquier parte de la pantalla. Lyan responde.</p>
          </div>
        </section>

        <section id="rutas" className="tc-pantalla tc-der">
          <div className="tc-panel">
            <p className="tc-rotulo">Cómo funciona</p>
            <h2 className="tc-h2">Cada pedido es una ruta. Zynex las ve todas.</h2>
            <ul className="tc-leyenda">
              <li><i className="tc-p tc-p-azul" /> <div><b>En camino</b><span>Zynex lee tu Dropi cada 5 minutos. No necesitas API.</span></div></li>
              <li><i className="tc-p tc-p-ambar" /> <div><b>Novedad</b><span>El pedido se frena. Aparece primero en tu lista, con el motivo.</span></div></li>
              <li><i className="tc-p tc-p-verde" /> <div><b>Resuelto</b><span>Zynex llama al cliente, acuerda la entrega y lo deja anotado.</span></div></li>
            </ul>
            <p className="tc-nota">Empieza en modo sombra: te muestra lo que haría, sin contactar a nadie.</p>
          </div>
        </section>

        <section id="apps" className="tc-pantalla tc-abajo">
          <div className="tc-ancho">
            <p className="tc-rotulo">Tres apps, una sola ficha del pedido</p>
            <div className="tc-apps">
              {APPS.map((a) => (
                <article key={a.n} className="tc-panel tc-app">
                  <span className="tc-n tc-num">{a.n}</span>
                  <h3>{a.nombre}</h3>
                  <p>{a.texto}</p>
                  <b className="tc-num">{a.precio}</b>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="precios" className="tc-pantalla tc-izq">
          <div className="tc-panel tc-precios">
            <div className="tc-precios-top">
              <div><p className="tc-rotulo">Precios</p><h2 className="tc-h2">Se pagan aparte. Juntas, 15 % menos.</h2></div>
              <label className="tc-switch" data-testid="precios-codigo">
                <input type="checkbox" checked={conCodigo} onChange={(e) => setConCodigo(e.target.checked)} />
                <span>Tengo código de socio</span>
              </label>
            </div>
            <ul className="tc-planes">
              {PLANES.map((p) => (
                <li key={p.id} className={p.paquete ? "tc-paquete" : ""}>
                  <div><b>{p.nombre}</b><span>{p.incluye}</span></div>
                  <div className="tc-precio">
                    <strong className="tc-num">{usd(conCodigo ? p.conCodigo : p.lista)}</strong>
                    <a href={p.pago || `${WHATSAPP_VENTAS}?text=${encodeURIComponent(`Hola, quiero el plan ${p.nombre} de Zynex`)}`}
                       target="_blank" rel="noreferrer" data-testid={`precio-${p.id}`}>{p.pago ? "Pagar" : "Pedir"} <ArrowRight size={12} weight="bold" /></a>
                  </div>
                </li>
              ))}
            </ul>
            <p className="tc-nota">Al mes, en dólares, sin impuestos. Incluido en cualquier plan: {GRATIS.join(", ")}.</p>
          </div>
        </section>

        <section id="preguntas" className="tc-pantalla tc-der">
          <div className="tc-panel">
            <p className="tc-rotulo">Antes de empezar</p>
            {FAQ.map((f) => (
              <details key={f.q} className="tc-faq"><summary>{f.q}</summary><p>{f.a}</p></details>
            ))}
          </div>
        </section>

        <section className="tc-pantalla tc-fin">
          <div className="tc-col tc-centro">
            <h2 className="tc-h1 tc-h1-s">Conecta tu Dropi.<br /><em>Lyan hace guardia.</em></h2>
            <div className="tc-acciones">
              <Link to="/register" className="tc-btn tc-btn-1">Crear mi cuenta gratis <ArrowRight size={16} weight="bold" /></Link>
              <a href={WHATSAPP_VENTAS} target="_blank" rel="noreferrer" className="tc-btn tc-btn-2"><WhatsappLogo size={16} weight="fill" /> Hablar con una persona</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="tc-pie">
        <span>Zynex</span>
        <span><a href="mailto:zynexproai@gmail.com">zynexproai@gmail.com</a> · <Link to="/login">Entrar</Link></span>
      </footer>
    </div>
  );
}
