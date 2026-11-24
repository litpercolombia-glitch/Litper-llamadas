import { useEffect, useState } from "react";
import { api } from "./api";

export const DEFAULT_ASSISTANT_NAME = "Lyan";
const EVENT = "zynex-org-profile-changed";

// Una sola petición compartida por toda la app; se invalida al guardar el perfil.
let cache = null;
let pending = null;

export function fetchOrgProfile(force = false) {
  if (cache && !force) return Promise.resolve(cache);
  if (!pending || force) {
    pending = api.get("/org/profile")
      .then((r) => { cache = r.data?.profile || r.data || {}; return cache; })
      .catch(() => ({}))
      .finally(() => { pending = null; });
  }
  return pending;
}

export function setOrgProfileCache(profile) {
  cache = profile || {};
  if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENT));
}

export function assistantNameOf(profile) {
  const n = (profile?.nombre_asistente || "").trim();
  return n || DEFAULT_ASSISTANT_NAME;
}

/** Nombre del asistente según GET /org/profile (por defecto "Lyan"). */
export function useAssistantName(enabled = true) {
  const [name, setName] = useState(assistantNameOf(cache));
  useEffect(() => {
    if (!enabled) return undefined; // páginas públicas: sin sesión no se consulta
    let alive = true;
    fetchOrgProfile().then((p) => { if (alive) setName(assistantNameOf(p)); });
    const on = () => setName(assistantNameOf(cache));
    window.addEventListener(EVENT, on);
    return () => { alive = false; window.removeEventListener(EVENT, on); };
  }, [enabled]);
  return name;
}

/** Mensaje de error legible a partir de un error de axios. */
export function errorText(e, fallback = "Algo salió mal. Inténtalo de nuevo.") {
  const d = e?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d.length) return d.map((x) => x?.msg || String(x)).join(" · ");
  if (e?.response?.status === 404) return "Esta función todavía no está disponible en tu servidor.";
  if (e?.code === "ECONNABORTED") return "El servidor tardó demasiado en responder. Inténtalo de nuevo.";
  if (!e?.response) return "No pudimos conectar con el servidor. Revisa tu conexión.";
  return fallback;
}

/** Perfil del negocio (GET /org/profile), compartido y actualizado al guardar. */
export function useOrgProfile(enabled = true) {
  const [profile, setProfile] = useState(cache || {});
  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    fetchOrgProfile().then((p) => { if (alive) setProfile(p || {}); });
    const on = () => setProfile(cache || {});
    window.addEventListener(EVENT, on);
    return () => { alive = false; window.removeEventListener(EVENT, on); };
  }, [enabled]);
  return profile;
}

/**
 * Dinero en la moneda del negocio. Sin moneda conocida NO se inventa una:
 * se muestra el número solo.
 */
export function formatMoney(v, currency) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Math.round(Number(v));
  const code = String(currency || "").trim().toUpperCase();
  if (/^[A-Z]{3}$/.test(code)) {
    try {
      return new Intl.NumberFormat("es", { style: "currency", currency: code, maximumFractionDigits: 0 }).format(n);
    } catch { /* código desconocido: cae al número solo */ }
  }
  return n.toLocaleString("es");
}
