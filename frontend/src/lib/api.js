import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// The public API key is exposed here BY DESIGN (this is an internal admin dashboard
// consumed by trusted operators). Rotate PUBLIC_API_KEY server-side to invalidate.
const API_KEY = "litper_hub_pk_2026_prod_ChangeMe_9x2Kf7bQvE4mLnT8sZ3H";

export const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: { "X-API-Key": API_KEY },
  timeout: 20000,
});

export const semaforoStyles = {
  rojo:     { dot: "#ef4444", label: "Rojo",     cls: "bg-red-500/10 text-red-400 border-red-500/30" },
  amarillo: { dot: "#eab308", label: "Amarillo", cls: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30" },
  verde:    { dot: "#22c55e", label: "Verde",    cls: "bg-green-500/10 text-green-400 border-green-500/30" },
  gris:     { dot: "#71717a", label: "Gris",     cls: "bg-zinc-500/10 text-zinc-400 border-zinc-500/30" },
};

export const statusStyles = {
  pending:      "bg-zinc-800 text-zinc-300",
  in_progress:  "bg-blue-500/10 text-blue-400",
  confirmado:   "bg-green-500/10 text-green-400",
  rechazado:    "bg-red-500/10 text-red-400",
  ya_recogio:   "bg-emerald-500/10 text-emerald-400",
  extension:    "bg-yellow-500/10 text-yellow-400",
  escalado:     "bg-orange-500/10 text-orange-400",
  detenido:     "bg-zinc-700 text-zinc-300",
};

export function formatCOP(v, currency = "COP") {
  if (v == null) return "-";
  try {
    return new Intl.NumberFormat("es-CO", { style: "currency", currency, maximumFractionDigits: 0 }).format(v);
  } catch { return `${v} ${currency}`; }
}

export function formatDateTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("es-CO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}
