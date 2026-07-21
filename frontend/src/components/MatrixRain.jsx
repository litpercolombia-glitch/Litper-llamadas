import { useEffect, useRef } from "react";

/**
 * Silver Matrix Rain — canvas background rendering falling silver glyphs.
 * Light on the CPU (throttled to ~20fps). Sits behind all UI, respects the
 * `--rain-opacity` and `--rain-color` theme variables.
 */
export default function MatrixRain() {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let rafId;
    let last = 0;

    const glyphs = "01ABCDEF◇◈▤▥⬢⬣∎▓▒░⟡⟢⟣⟤⟥ ".split("");
    let cols = [];
    let fontSize = 14;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const colCount = Math.floor(window.innerWidth / fontSize);
      cols = Array.from({ length: colCount }, () => Math.random() * window.innerHeight);
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = (t) => {
      if (t - last < 55) { rafId = requestAnimationFrame(draw); return; }
      last = t;
      const w = window.innerWidth;
      const h = window.innerHeight;
      const cs = getComputedStyle(document.documentElement);
      const rainColor = cs.getPropertyValue("--rain-color").trim() || "#C3C7CE";
      const sparkle = cs.getPropertyValue("--rain-sparkle").trim() || "#64D2FF";
      const bg = cs.getPropertyValue("--bg-primary").trim() || "#0B0C0E";

      // Fade trail
      ctx.fillStyle = bg + "22"; // very transparent
      ctx.fillRect(0, 0, w, h);

      ctx.font = `${fontSize}px "IBM Plex Mono", monospace`;
      for (let i = 0; i < cols.length; i++) {
        const y = cols[i];
        const x = i * fontSize;
        const g = glyphs[Math.floor(Math.random() * glyphs.length)];
        ctx.fillStyle = (Math.random() < 0.12) ? sparkle : rainColor;
        ctx.fillText(g, x, y);
        cols[i] = (y > h + Math.random() * 200) ? -20 : y + fontSize * 0.9;
      }
      rafId = requestAnimationFrame(draw);
    };
    rafId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="matrix-rain" aria-hidden />;
}
