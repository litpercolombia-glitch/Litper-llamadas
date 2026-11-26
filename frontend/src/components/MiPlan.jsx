import { useState } from "react";
import { CreditCard, UsersThree } from "@phosphor-icons/react";
import { GRATIS, GRUPO_VIP, PLANES, WHATSAPP_VENTAS } from "../constants/planes";

const usd = (n) => `US$${Number.isInteger(n) ? n : n.toFixed(2).replace(".", ",")}`;

/** Planes y precios, lo que va gratis y el grupo VIP. Sin enlace de pago en vivo, el botón lleva a WhatsApp. */
export default function MiPlan() {
  const [abierto, setAbierto] = useState(false);
  return (
    <section className="mb-6 rounded-lg border border-zinc-800 bg-zinc-950 p-4 md:p-5" data-testid="mi-plan" aria-labelledby="mi-plan-titulo">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 id="mi-plan-titulo" className="text-base font-semibold text-white flex items-center gap-2">
            <CreditCard size={18} /> Planes y grupo VIP
          </h3>
          <p className="text-sm text-zinc-400 mt-1">
            Logística y Llamadas se pagan aparte. Si llevas las dos, pagas 15 % menos. Con el código de un socio, 20 % menos para siempre.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={GRUPO_VIP} target="_blank" rel="noreferrer" data-testid="mi-plan-vip"
            className="inline-flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3 py-2 text-sm text-white">
            <UsersThree size={16} /> Entrar al grupo VIP
          </a>
          <button type="button" onClick={() => setAbierto((v) => !v)} aria-expanded={abierto} data-testid="mi-plan-ver"
            className="rounded-md border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3 py-2 text-sm text-white">
            {abierto ? "Ocultar planes" : "Ver planes"}
          </button>
        </div>
      </div>

      {abierto && (
        <div className="mt-4">
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {PLANES.map((p) => (
              <li key={p.id} className={`rounded-md border p-3 ${p.paquete ? "border-cyan-500/40" : "border-zinc-800"} bg-zinc-900`}>
                <div className="text-sm font-medium text-white">{p.nombre}</div>
                <div className="text-xs text-zinc-400 mt-0.5">{p.incluye}</div>
                <div className="mt-2 text-xl font-semibold text-white">{usd(p.lista)}<span className="text-xs font-normal text-zinc-400"> al mes</span></div>
                <div className="text-xs text-emerald-300">Con código de socio: {usd(p.conCodigo)}</div>
                <a href={p.pago || `${WHATSAPP_VENTAS}?text=${encodeURIComponent(`Hola, quiero el plan ${p.nombre} de Zynex`)}`}
                  target="_blank" rel="noreferrer" data-testid={`mi-plan-${p.id}`}
                  className="mt-3 inline-flex rounded-md border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-3 py-1.5 text-sm text-white">
                  {p.pago ? "Pagar este plan" : "Pedir este plan"}
                </a>
              </li>
            ))}
          </ul>
          <p className="text-xs text-zinc-400 mt-3">
            Incluido sin costo en cualquier plan: {GRATIS.join(", ")}. Precios en dólares, sin impuestos.
          </p>
        </div>
      )}
    </section>
  );
}
