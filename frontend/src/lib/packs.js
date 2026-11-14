import { useEffect, useState } from "react";
import { api } from "./api";

/**
 * Paquetes opcionales instalados en la cuenta (GET /packs).
 *
 * Una sola petición compartida por toda la app. Las pantallas exclusivas de
 * un paquete (por ejemplo contra entrega: transportadoras, novedades,
 * cadencia) solo se muestran si ese paquete está instalado.
 *
 * Regla: si el servidor no dice `installed: true`, el paquete NO está.
 */
export const COD_PACK = "cod_colombia";
const EVENT = "zynex-packs-changed";

let cache = null;   // { loaded: true, installed: string[] }
let pending = null;

const listOf = (data) => (Array.isArray(data) ? data : (data?.packs || data?.items || []));
const keyOf = (p) => p?.key || p?.id || p?.pack || p?.slug || "";

export function installedKeys(data) {
  return listOf(data).filter((p) => p && p.installed === true).map(keyOf).filter(Boolean);
}

export function fetchPacks(force = false) {
  if (cache && !force) return Promise.resolve(cache);
  if (!pending || force) {
    pending = api.get("/packs")
      .then((r) => { cache = { loaded: true, installed: installedKeys(r.data) }; return cache; })
      // Sin respuesta = sin paquetes: las pantallas del paquete quedan ocultas.
      .catch(() => ({ loaded: true, installed: [] }))
      .finally(() => { pending = null; });
  }
  return pending;
}

/** Vuelve a consultar y avisa a las pantallas abiertas (tras instalar un paquete). */
export function refreshPacks() {
  return fetchPacks(true).then((s) => {
    if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENT));
    return s;
  });
}

/** { loaded, installed, has(key), hasCod } */
export function usePacks() {
  const [state, setState] = useState(cache || { loaded: false, installed: [] });
  useEffect(() => {
    let alive = true;
    fetchPacks().then((s) => { if (alive) setState(s); });
    const on = () => { if (alive && cache) setState(cache); };
    window.addEventListener(EVENT, on);
    return () => { alive = false; window.removeEventListener(EVENT, on); };
  }, []);
  const has = (key) => state.installed.includes(key);
  return { loaded: state.loaded, installed: state.installed, has, hasCod: has(COD_PACK) };
}
