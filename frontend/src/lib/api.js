import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Zynex OS v2 uses HttpOnly cookie auth (`litper_session`). No more operator
// key on the client — internal routes now accept either the JWT cookie OR
// the legacy X-API-Key (kept for external agents). The browser stops
// shipping the static key entirely.
export const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  timeout: 20000,
  withCredentials: true,
});

// Automatic 401 → /login redirect. Prevents blank pages when the session
// expires or is invalidated on the backend.
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401
        && typeof window !== "undefined"
        && !window.location.pathname.startsWith("/login")
        && !window.location.pathname.startsWith("/register")
        && !window.location.pathname.startsWith("/funnel")
        && window.location.pathname !== "/") {
      localStorage.removeItem("litper_operator_ok");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

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
