import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { CheckCircle, Circle, X } from "@phosphor-icons/react";

/** Instalación en 4 pasos: le dice al cliente nuevo qué le falta para dejar Zynex andando.
 *  Se muestra en Logística y Clientes hasta que los 4 pasos estén listos o lo cierre. */
const CLAVE = "zynex-inicio-rapido-cerrado";
const leer = () => { try { return localStorage.getItem(CLAVE) === "1"; } catch { return false; } };

export default function InicioRapido() {
  const [d, setD] = useState(null);
  const [cerrado, setCerrado] = useState(leer);
  useEffect(() => {
    if (cerrado) return;
    Promise.all([
      api.get("/zcall/estado").then((r) => r.data).catch(() => ({})),
      api.get("/zcall/motor/panel").then((r) => r.data).catch(() => ({})),
      api.get("/zcall/motor/clientes", { params: { filtro: "todos", q: "" } }).then((r) => r.data).catch(() => ({})),
    ]).then(([estado, panel, cli]) => setD({
      claude: !!estado?.conexiones?.claude,
      pedidos: (cli?.resumen?.todos || 0) > 0,
      plantillas: panel?.vinculado === true && panel?.sin_plantilla === 0,
      decisiones: (panel?.tareas || []).length > 0,
      listo: panel?.conectado !== false,
    }));
  }, [cerrado]);
  if (cerrado || !d || !d.listo) return null;
  const pasos = [
    { ok: d.claude, t: "Conecta tu Claude", s: "Es el puente con tu Dropi. Toma 5 minutos.", to: "/app/conexiones?tab=claude", cta: "Conectar" },
    { ok: d.pedidos, t: "Trae tu operación", s: "Tus pedidos de los últimos 30, 60 o 90 días, para medir desde hoy.", to: "/app/clientes", cta: "Traer pedidos" },
    { ok: d.plantillas, t: "Elige tus plantillas", s: "Pon en cada casilla la plantilla de WhatsApp que tú quieras usar.", to: "/app/logistica?tab=casillas", cta: "Elegir" },
    { ok: d.decisiones, t: "Mira lo que decide el motor", s: "Arranca en modo sombra: decide y anota, pero no envía nada.", to: "/app/logistica", cta: "Ver panel" },
  ];
  const hechos = pasos.filter((p) => p.ok).length;
  if (hechos === pasos.length) return null;
  const cerrar = () => { try { localStorage.setItem(CLAVE, "1"); } catch { /* sin almacenamiento: se cierra solo en esta visita */ } setCerrado(true); };
  return (
    <section className="mb-5 border border-zinc-800 rounded-sm bg-zinc-900/40 p-5" data-testid="inicio-rapido" aria-labelledby="inicio-rapido-t">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h2 id="inicio-rapido-t" className="text-base font-semibold text-white">Deja Zynex andando en 4 pasos</h2>
          <p className="text-sm text-zinc-300">Llevas {hechos} de {pasos.length}. Completo toma menos de una hora.</p>
        </div>
        <button type="button" onClick={cerrar} aria-label="Cerrar los primeros pasos"
                className="h-9 w-9 shrink-0 grid place-items-center rounded-sm border border-zinc-700 text-zinc-300 hover:bg-zinc-800"><X size={16} /></button>
      </div>
      <ol className="grid gap-3 md:grid-cols-2">
        {pasos.map((p, i) => (
          <li key={p.t} className="flex items-start gap-3 border border-zinc-800 rounded-sm p-3 min-w-0">
            {p.ok ? <CheckCircle size={20} weight="fill" className="text-emerald-400 shrink-0 mt-0.5" aria-label="Listo" />
                  : <Circle size={20} className="text-zinc-400 shrink-0 mt-0.5" aria-label="Pendiente" />}
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-white">{i + 1}. {p.t}</div>
              <div className="text-xs text-zinc-300">{p.s}</div>
              {!p.ok && <Link to={p.to} className="inline-block mt-1.5 text-sm text-zinc-100 underline decoration-zinc-500 hover:decoration-emerald-400">{p.cta}</Link>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
