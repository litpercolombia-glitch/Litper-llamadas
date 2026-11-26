import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { Storefront, CheckCircle } from "@phosphor-icons/react";

/** Lo básico de tu tienda, en 7 casillas. Con esto tus agentes y el asistente
 *  responden lo que más preguntan los clientes (envío, garantía, cambios, pagos)
 *  con TUS datos y no inventan. Se guarda en la base de conocimiento como
 *  preguntas frecuentes, así llega igual al asistente y a los agentes de voz. */
const CAMPOS = [
  { k: "despacho", pregunta: "¿Desde dónde despachan?", label: "¿Desde dónde despachas?", ej: "Ej.: Desde Bogotá, barrio Restrepo." },
  { k: "envio", pregunta: "¿Cuánto tarda el envío?", label: "¿Cuánto tarda el envío?", ej: "Ej.: 2 a 4 días hábiles en ciudades principales; 5 a 8 en municipios." },
  { k: "garantia", pregunta: "¿Qué garantía tienen los productos?", label: "¿Qué garantía das?", ej: "Ej.: 30 días por defectos de fábrica." },
  { k: "cambios", pregunta: "¿Puedo cambiar o devolver el producto?", label: "Cambios y devoluciones", ej: "Ej.: Cambios dentro de 5 días, sin uso y en su empaque." },
  { k: "pagos", pregunta: "¿Cómo puedo pagar?", label: "¿Cómo te pueden pagar?", ej: "Ej.: Pagas al recibir, en efectivo." },
  { k: "soporte", pregunta: "¿Cuál es el número de soporte?", label: "Número de soporte", ej: "Ej.: WhatsApp 300 000 0000, lunes a sábado de 8 a 6." },
];

export default function DatosTienda() {
  const [abierto, setAbierto] = useState(false);
  const [tienda, setTienda] = useState("");
  const [v, setV] = useState({});
  const [otras, setOtras] = useState([]);       // preguntas frecuentes que no son de esta tarjeta
  const [cargado, setCargado] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    Promise.all([api.get("/org/profile"), api.get("/kb")]).then(([p, k]) => {
      setTienda(p.data?.empresa || "");
      const faqs = Array.isArray(k.data?.faqs) ? k.data.faqs : [];
      const mias = {};
      CAMPOS.forEach((c) => { const f = faqs.find((x) => x.pregunta === c.pregunta); if (f) mias[c.k] = f.respuesta || ""; });
      setV(mias);
      setOtras(faqs.filter((x) => !CAMPOS.some((c) => c.pregunta === x.pregunta)));
      setCargado(true);
    }).catch(() => setCargado(false));
  }, []);
  if (!cargado) return null;

  const listos = (tienda.trim() ? 1 : 0) + CAMPOS.filter((c) => (v[c.k] || "").trim()).length;
  const total = CAMPOS.length + 1;

  const guardar = async (e) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      const faqs = [...CAMPOS.filter((c) => (v[c.k] || "").trim()).map((c) => ({ pregunta: c.pregunta, respuesta: v[c.k].trim() })), ...otras];
      await api.put("/org/profile", { empresa: tienda.trim() });
      await api.put("/kb", { faqs });
      setMsg(["ok", "Guardado. Tus agentes ya responden con estos datos."]);
    } catch (err) { setMsg(["mal", errorText(err, "No pude guardar. Inténtalo de nuevo.")]); }
    finally { setBusy(false); }
  };

  return (
    <section className="mb-6 border border-zinc-800 rounded-sm bg-zinc-900/50 p-4" data-testid="datos-tienda" aria-label="Datos de tu tienda">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Storefront size={18} /> Datos de tu tienda
            {listos === total && <CheckCircle size={16} weight="fill" className="text-emerald-400" aria-label="Completo" />}
          </h3>
          <p className="text-sm text-zinc-300 mt-1 max-w-2xl">
            Lo que tus clientes más preguntan: envío, garantía, cambios y pagos. Tus agentes responden con esto y no inventan.
            Llevas {listos} de {total}.
          </p>
        </div>
        <button type="button" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto} data-testid="datos-tienda-abrir"
                className="h-10 px-4 rounded-sm border border-zinc-600 text-zinc-100 text-sm hover:bg-zinc-800">
          {abierto ? "Cerrar" : listos === total ? "Editar" : "Completar"}
        </button>
      </div>
      {abierto && (
        <form onSubmit={guardar} className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="md:col-span-2">
            <label htmlFor="dt-tienda" className="block text-sm text-zinc-100 mb-1">Nombre de tu tienda</label>
            <input id="dt-tienda" value={tienda} onChange={(e) => setTienda(e.target.value)} maxLength={120}
                   placeholder="Ej.: Hogar Bonito" autoComplete="organization"
                   className="w-full h-10 rounded-sm bg-black/40 border border-zinc-700 text-white text-sm px-3" />
          </div>
          {CAMPOS.map((c) => (
            <div key={c.k}>
              <label htmlFor={`dt-${c.k}`} className="block text-sm text-zinc-100 mb-1">{c.label}</label>
              <textarea id={`dt-${c.k}`} value={v[c.k] || ""} onChange={(e) => setV((x) => ({ ...x, [c.k]: e.target.value }))}
                        maxLength={600} rows={2} placeholder={c.ej}
                        className="w-full rounded-sm bg-black/40 border border-zinc-700 text-white text-sm px-3 py-2" />
            </div>
          ))}
          <div className="md:col-span-2 flex flex-wrap items-center gap-3">
            <button type="submit" disabled={busy} className="h-10 px-4 rounded-sm btn-cta-grad text-white text-sm font-medium disabled:opacity-50">
              {busy ? "Guardando…" : "Guardar"}</button>
            <span className="text-xs text-zinc-300">Horarios, catálogo y más preguntas están en la pestaña «Base de conocimiento».</span>
          </div>
          {msg && (
            <p role="status" className={`md:col-span-2 text-sm text-zinc-100 border rounded-sm px-3 py-2 ${msg[0] === "ok" ? "border-emerald-500/50" : "border-red-500/50"}`}>{msg[1]}</p>
          )}
        </form>
      )}
    </section>
  );
}
