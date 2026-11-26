import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

/**
 * Lluvia Matrix de fondo en toda la app. Liviana (unos 20 cuadros por segundo) y detrás de todo.
 * Cada módulo tiene su color y sus símbolos: al cambiar de módulo la lluvia cambia de tono
 * y cae un momento más rápido, para que se sienta el cambio de lugar.
 */
const MODULOS = [
  { ruta: "/app/logistica", noche: "#19C8FF", dia: "#0369A1", extra: "▤▥⬢→" },
  { ruta: "/app/pedidos", noche: "#19C8FF", dia: "#0369A1", extra: "▤▥⬢→" },
  { ruta: "/app/clientes", noche: "#A78BFA", dia: "#6D28D9", extra: "◇◈⟡" },
  { ruta: "/app/llamadas", noche: "#34E3A0", dia: "#047857", extra: "∿≋◉" },
  { ruta: "/app/conexiones", noche: "#FFB020", dia: "#B45309", extra: "⟢⟣⟤⟥" },
  { ruta: "/app/metricas", noche: "#F472B6", dia: "#BE185D", extra: "▁▃▅▇" },
  { ruta: "/app/ajustes", noche: "#C3C7CE", dia: "#475569", extra: "⚙∎▓▒" },
];
const BASE = { noche: "#64D2FF", dia: "#0369A1", extra: "⬢⬣" };
const moduloDe = (ruta) => MODULOS.find((m) => ruta.startsWith(m.ruta)) || BASE;

export default function MatrixRain() {
  const ref = useRef(null);
  const { pathname } = useLocation();
  const estado = useRef({ modulo: BASE, impulso: 0 });

  // Cambio de módulo: color nuevo y un impulso corto.
  useEffect(() => {
    const m = moduloDe(pathname);
    if (m !== estado.current.modulo) { estado.current.modulo = m; estado.current.impulso = 1; }
    const raiz = document.documentElement;
    const pinta = () => raiz.style.setProperty("--modulo", raiz.classList.contains("matrix-day") ? m.dia : m.noche);
    pinta();
    const ob = new MutationObserver(pinta); ob.observe(raiz, { attributes: true, attributeFilter: ["class"] });
    return () => ob.disconnect();
  }, [pathname]);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    const quieto = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    let rafId, last = 0, cols = [];
    const fontSize = 14;
    const base = "01ZYNEX◇▤⬢∎▓▒░ ".split("");

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr; canvas.height = window.innerHeight * dpr;
      canvas.style.width = window.innerWidth + "px"; canvas.style.height = window.innerHeight + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Array.from({ length: Math.floor(window.innerWidth / fontSize) }, () => Math.random() * window.innerHeight);
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = (t) => {
      if (t - last < 55) { rafId = requestAnimationFrame(draw); return; }
      last = t;
      const w = window.innerWidth, h = window.innerHeight;
      const cs = getComputedStyle(document.documentElement);
      const rainColor = cs.getPropertyValue("--rain-color").trim() || "#C3C7CE";
      const sparkle = cs.getPropertyValue("--modulo").trim() || cs.getPropertyValue("--rain-sparkle").trim() || "#64D2FF";
      const bg = cs.getPropertyValue("--bg-primary").trim() || "#0B0C0E";
      const e = estado.current;
      const glyphs = base.concat(e.modulo.extra.split(""));
      const impulso = e.impulso; e.impulso = Math.max(0, e.impulso - 0.06);

      ctx.fillStyle = bg + "22";
      ctx.fillRect(0, 0, w, h);
      ctx.font = `${fontSize}px "IBM Plex Mono", monospace`;
      for (let i = 0; i < cols.length; i++) {
        const y = cols[i];
        ctx.fillStyle = Math.random() < 0.12 + impulso * 0.6 ? sparkle : rainColor;
        ctx.fillText(glyphs[Math.floor(Math.random() * glyphs.length)], i * fontSize, y);
        cols[i] = y > h + Math.random() * 200 ? -20 : y + fontSize * (0.9 + impulso * 1.6);
      }
      if (!quieto || impulso > 0) rafId = requestAnimationFrame(draw);
    };
    rafId = requestAnimationFrame(draw);
    const despierta = () => { cancelAnimationFrame(rafId); rafId = requestAnimationFrame(draw); };
    window.addEventListener("zynex-modulo", despierta);

    return () => { cancelAnimationFrame(rafId); window.removeEventListener("resize", resize); window.removeEventListener("zynex-modulo", despierta); };
  }, []);

  return <canvas ref={ref} className="matrix-rain" aria-hidden />;
}
