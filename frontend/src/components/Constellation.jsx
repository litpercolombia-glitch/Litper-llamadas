import { useEffect, useRef } from "react";

/**
 * Constellation — canvas background of connected nodes + gentle drift.
 * Renders behind everything (z-index: 0). Auto-detects theme by reading the
 * CSS variable --accent so it re-tints between day/night automatically.
 */
export default function Constellation({ density = 90, className = "" }) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let running = true;
    let dpr = window.devicePixelRatio || 1;

    const resize = () => {
      dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
    };
    resize();
    window.addEventListener("resize", resize);

    // Points
    const N = Math.min(density, Math.floor((window.innerWidth * window.innerHeight) / 22000));
    const pts = Array.from({ length: N }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.18 * dpr,
      vy: (Math.random() - 0.5) * 0.18 * dpr,
      // seed a fraction of them as "destellos" that occasionally flash
      spark: Math.random() < 0.18,
      phase: Math.random() * Math.PI * 2,
    }));

    // Sample four ZYNEX gradient stops (fixed colors — perf > perfect theming)
    const gradStops = [
      "0, 216, 255",     // cyan
      "10, 132, 255",    // azure
      "124, 92, 255",    // violet
      "192, 75, 255",    // magenta
    ];
    const themeAlphaLine = () => {
      const dark = document.documentElement.classList.contains("matrix-night") ||
                   !document.documentElement.classList.contains("matrix-day");
      return dark ? 0.28 : 0.22;
    };
    const themeAlphaDot = () => {
      const dark = document.documentElement.classList.contains("matrix-night") ||
                   !document.documentElement.classList.contains("matrix-day");
      return dark ? 0.85 : 0.55;
    };

    const maxDist = 130 * dpr;
    let raf;
    let t0 = performance.now();

    const draw = (now) => {
      if (!running) return;
      const dt = Math.min(48, now - t0); t0 = now;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Move
      for (const p of pts) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;
        p.phase += 0.02;
      }

      // Lines between neighbors
      ctx.lineWidth = 1 * dpr;
      const alphaLineBase = themeAlphaLine();
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const a = pts[i], b = pts[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < maxDist * maxDist) {
            const d = Math.sqrt(d2);
            const alpha = alphaLineBase * (1 - d / maxDist);
            // pick a color based on x position for a gradient sweep across viewport
            const stop = gradStops[Math.floor(((a.x / canvas.width) * gradStops.length)) % gradStops.length];
            ctx.strokeStyle = `rgba(${stop}, ${alpha})`;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      // Dots + destellos
      const alphaDot = themeAlphaDot();
      for (const p of pts) {
        const sparkle = p.spark ? 0.6 + 0.4 * Math.sin(p.phase) : 0;
        const r = (p.spark ? 1.4 : 1) * dpr + sparkle * dpr;
        const stop = gradStops[Math.floor(((p.x / canvas.width) * gradStops.length)) % gradStops.length];
        ctx.fillStyle = `rgba(${stop}, ${alphaDot})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();

        if (p.spark && sparkle > 0.75) {
          // extra glow
          ctx.fillStyle = `rgba(${stop}, 0.16)`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r * 5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [density]);

  return <canvas ref={ref} className={`constellation-canvas ${className}`} aria-hidden />;
}
