import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { CheckCircle } from "@phosphor-icons/react";

/** Formulario público de descubrimiento para dropshippers de Dropi (sin sesión). */
const PEDIDOS = [["menos_20", "Menos de 20"], ["20_100", "20 a 100"], ["100_500", "100 a 500"], ["mas_500", "Más de 500"]];
const DOLORES = [["confirmar", "Confirmar pedidos"], ["novedades", "Novedades"], ["oficina", "Pedidos en oficina"],
                 ["devoluciones", "Devoluciones"], ["chats", "Responder chats"]];
const QUIEN = [["yo", "Yo"], ["una_persona", "1 persona"], ["equipo", "Equipo de 2 o más"], ["herramienta", "Un bot o herramienta"]];
const PAISES = ["Colombia", "Ecuador", "Chile", "Guatemala", "México", "Perú", "Panamá", "Paraguay", "Argentina", "Costa Rica", "España", "Otro"];

const caja = "rounded-md border border-zinc-800 bg-zinc-900/60 p-5";
const etiqueta = "block text-sm font-medium text-white mb-2";

function Opcion({ activa, onClick, children, tipo = "radio", name }) {
  return (
    <button type="button" role={tipo} aria-checked={activa} onClick={onClick} data-name={name}
            className={`min-h-[44px] px-3 py-2 rounded-md border text-sm text-left transition-colors ${
              activa ? "border-cyan-400 bg-cyan-500/15 text-white" : "border-zinc-700 bg-zinc-900 text-zinc-200 hover:border-zinc-500"}`}>
      {children}
    </button>
  );
}

export default function EncuestaPage() {
  const [f, setF] = useState({ pedidos_dia: "", pais: "", dolores: [], quien: "", herramienta: "", arreglar: "",
                               whatsapp: "", acepta_contacto: false, sitio_web: "" });
  const [estado, setEstado] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { document.title = "Encuesta · Zynex"; }, []);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const toggle = (d) => set("dolores", f.dolores.includes(d) ? f.dolores.filter((x) => x !== d) : [...f.dolores, d]);
  const listo = f.pedidos_dia && f.pais && f.dolores.length && f.quien
    && (!f.acepta_contacto || f.whatsapp.replace(/\D/g, "").length >= 7);

  const enviar = async (e) => {
    e.preventDefault();
    if (!listo) return;
    setEstado("enviando"); setError("");
    try {
      const origen = new URLSearchParams(window.location.search).get("origen") || undefined;
      await api.post("/encuesta", { ...f, origen, whatsapp: f.acepta_contacto ? f.whatsapp : null });
      setEstado("ok");
    } catch (err) {
      setError(err?.response?.data?.detail || "No pudimos guardar tu respuesta. Intenta de nuevo.");
      setEstado("");
    }
  };

  if (estado === "ok") {
    return (
      <main className="min-h-screen bg-zinc-950 text-white grid place-items-center px-4">
        <div className={`${caja} max-w-md text-center`} data-testid="encuesta-gracias">
          <CheckCircle size={44} weight="fill" className="text-green-400 mx-auto" />
          <h1 className="text-xl font-semibold mt-3">¡Gracias!</h1>
          <p className="text-sm text-zinc-300 mt-2">
            {f.acepta_contacto ? "Te escribimos por WhatsApp cuando abramos la prueba gratis." : "Tu respuesta nos ayuda a decidir qué construir primero."}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-white px-4 py-10" data-testid="encuesta-page">
      <form onSubmit={enviar} className="max-w-xl mx-auto space-y-5" noValidate>
        <header className="space-y-2">
          <div className="text-[11px] font-mono uppercase tracking-[0.25em] text-zinc-300">Zynex · para quienes venden con Dropi</div>
          <h1 className="text-2xl md:text-3xl font-semibold leading-tight">¿Qué te quita más tiempo con tus pedidos de Dropi?</h1>
          <p className="text-sm text-zinc-300">Son 2 minutos. Quienes respondan prueban gratis 14 días antes que nadie.</p>
        </header>

        <section className={caja}>
          <span className={etiqueta} id="q1">1. ¿Cuántos pedidos manejas al día?</span>
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-labelledby="q1">
            {PEDIDOS.map(([v, t]) => <Opcion key={v} name="pedidos" activa={f.pedidos_dia === v} onClick={() => set("pedidos_dia", v)}>{t}</Opcion>)}
          </div>
        </section>

        <section className={caja}>
          <label className={etiqueta} htmlFor="pais">2. ¿En qué país vendes con Dropi?</label>
          <select id="pais" value={f.pais} onChange={(e) => set("pais", e.target.value)}
                  className="w-full min-h-[44px] rounded-md border border-zinc-700 bg-zinc-900 px-3 text-sm text-white">
            <option value="">Elige tu país</option>
            {PAISES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </section>

        <section className={caja}>
          <span className={etiqueta} id="q3">3. ¿Qué te quita más tiempo? <span className="text-zinc-400 font-normal">(puedes marcar varias)</span></span>
          <div className="grid grid-cols-2 gap-2" role="group" aria-labelledby="q3">
            {DOLORES.map(([v, t]) => <Opcion key={v} tipo="checkbox" name="dolor" activa={f.dolores.includes(v)} onClick={() => toggle(v)}>{t}</Opcion>)}
          </div>
        </section>

        <section className={caja}>
          <span className={etiqueta} id="q4">4. ¿Quién lo hace hoy?</span>
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-labelledby="q4">
            {QUIEN.map(([v, t]) => <Opcion key={v} name="quien" activa={f.quien === v} onClick={() => set("quien", v)}>{t}</Opcion>)}
          </div>
        </section>

        <section className={caja}>
          <label className={etiqueta} htmlFor="herr">5. ¿Qué herramienta usas y cuánto pagas al mes? <span className="text-zinc-400 font-normal">(opcional)</span></label>
          <input id="herr" value={f.herramienta} maxLength={300} onChange={(e) => set("herramienta", e.target.value)}
                 placeholder="Ej.: Chatea Pro, 50 dólares" className="w-full min-h-[44px] rounded-md border border-zinc-700 bg-zinc-900 px-3 text-sm text-white placeholder:text-zinc-500" />
        </section>

        <section className={caja}>
          <label className={etiqueta} htmlFor="arr">6. Si pudieras arreglar una sola cosa mañana, ¿cuál sería? <span className="text-zinc-400 font-normal">(opcional)</span></label>
          <textarea id="arr" value={f.arreglar} maxLength={600} rows={3} onChange={(e) => set("arreglar", e.target.value)}
                    className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white" />
        </section>

        <section className={caja}>
          <span className={etiqueta}>7. ¿Quieres probarlo gratis 14 días? <span className="text-zinc-400 font-normal">(opcional)</span></span>
          <label className="flex items-start gap-3 text-sm text-zinc-200 cursor-pointer min-h-[44px]">
            <input type="checkbox" checked={f.acepta_contacto} onChange={(e) => set("acepta_contacto", e.target.checked)}
                   className="mt-1 h-5 w-5 accent-cyan-400" />
            Sí, acepto que Zynex me escriba por WhatsApp sobre la prueba.
          </label>
          {f.acepta_contacto && (
            <input aria-label="Tu WhatsApp" inputMode="tel" value={f.whatsapp} maxLength={25} onChange={(e) => set("whatsapp", e.target.value)}
                   placeholder="Tu WhatsApp con indicativo, ej.: 57 300 123 4567"
                   className="mt-3 w-full min-h-[44px] rounded-md border border-zinc-700 bg-zinc-900 px-3 text-sm text-white placeholder:text-zinc-500" />
          )}
        </section>

        <div className="absolute -left-[9999px]" aria-hidden="true">
          <label>Sitio web<input tabIndex={-1} autoComplete="off" value={f.sitio_web} onChange={(e) => set("sitio_web", e.target.value)} /></label>
        </div>

        {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
        <button type="submit" disabled={!listo || estado === "enviando"} data-testid="encuesta-enviar"
                className="w-full min-h-[48px] rounded-md bg-cyan-400 text-black font-semibold disabled:opacity-60">
          {estado === "enviando" ? "Enviando…" : "Enviar respuestas"}
        </button>
        <p className="text-[11px] text-zinc-400 text-center">Solo usamos tus respuestas para mejorar Zynex. No compartimos tus datos.</p>
      </form>
    </main>
  );
}
