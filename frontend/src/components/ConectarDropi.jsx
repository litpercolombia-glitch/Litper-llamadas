import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, formatDateTime } from "../lib/api";
import { errorText } from "../lib/assistant";
import { PlugsConnected, ArrowsClockwise } from "@phosphor-icons/react";

/** Conectar Dropi sin API: el cliente inicia sesión en Dropi una vez y Zynex
 *  lee sus pedidos solo, cada pocos minutos. Zynex nunca ve la contraseña y
 *  el permiso es de solo lectura. */
const AVISOS = {
  conectado: ["ok", "Dropi quedó conectado. En unos minutos empiezan a llegar tus pedidos."],
  cancelado: ["mal", "No se conectó: cancelaste el permiso en Dropi."],
  vencido: ["mal", "El enlace venció. Pulsa «Conectar Dropi» de nuevo."],
  error: ["mal", "Dropi no completó la conexión. Inténtalo de nuevo en unos minutos."],
};

export default function ConectarDropi() {
  const { search, pathname } = useLocation();
  const navigate = useNavigate();
  const [est, setEst] = useState(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState(null);

  const cargar = useCallback(() => api.get("/zcall/motor/operacion/dropi/estado")
    .then((r) => setEst(r.data || {})).catch(() => setEst({ sinServicio: true })), []);

  useEffect(() => {
    const v = new URLSearchParams(search).get("dropi");
    if (v && AVISOS[v]) { setMsg(AVISOS[v]); navigate(pathname, { replace: true }); }
    cargar();
  }, [cargar]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!est || est.sinServicio) return null;

  const conectar = async () => {
    setBusy("conectar"); setMsg(null);
    try {
      const r = await api.post("/zcall/motor/operacion/dropi/conectar");
      if (r.data?.url) window.location.assign(r.data.url);
      else throw new Error("sin dirección");
    } catch (e) { setMsg(["mal", errorText(e, "No pude abrir Dropi. Inténtalo de nuevo.")]); setBusy(""); }
  };
  const leer = async () => {
    setBusy("leer"); setMsg(null);
    try {
      const r = await api.post("/zcall/motor/operacion/dropi/sincronizar", null, { timeout: 120000 });
      setMsg(r.data?.ok ? ["ok", `Listo: leí ${r.data.leidos} pedidos y guardé ${r.data.guardados}.`]
        : ["mal", "Dropi no respondió bien. Lo intento de nuevo solo en unos minutos."]);
    } catch (e) { setMsg(["mal", errorText(e, "No pude leer Dropi ahora.")]); }
    finally { setBusy(""); cargar(); }
  };
  const desconectar = async () => {
    setBusy("quitar"); setMsg(null);
    try { await api.post("/zcall/motor/operacion/dropi/desconectar"); setMsg(["ok", "Dropi quedó desconectado. Tus pedidos guardados siguen aquí."]); }
    catch (e) { setMsg(["mal", errorText(e, "No pude desconectar.")]); }
    finally { setBusy(""); cargar(); }
  };
  const activo = est.conectado && !est.necesita_reconectar;

  return (
    <section className="mb-6 border border-zinc-800 rounded-sm bg-zinc-900/50 p-4" data-testid="conectar-dropi" aria-label="Conexión con Dropi">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <PlugsConnected size={18} /> {activo ? "Dropi conectado" : "Conecta tu Dropi"}
          </h3>
          <p className="text-sm text-zinc-300 mt-1 max-w-2xl">
            {activo
              ? `Zynex lee tus pedidos solo, cada ${est.cada_min || 5} minutos.${est.ultimo_sync ? ` Última lectura: ${formatDateTime(est.ultimo_sync)} (${est.ultimo_guardados ?? 0} pedidos).` : " La primera lectura sale en unos minutos."}`
              : est.necesita_reconectar
                ? "El permiso de Dropi venció. Conéctalo de nuevo para que tus pedidos sigan llegando."
                : "Inicias sesión en la página de Dropi una sola vez y tus pedidos llegan solos. Zynex no ve tu contraseña y solo puede leer pedidos."}
          </p>
          {!activo && (
            <p className="text-xs text-zinc-400 mt-1">Dropi permite una sesión por cuenta: si lo usas en un asistente de IA, puede pedirte conectar de nuevo allá.</p>
          )}
          {activo && est.ultimo_error && <p className="text-xs text-amber-300 mt-1">Último intento con error; se reintenta solo.</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {activo ? (
            <>
              <button type="button" onClick={leer} disabled={!!busy}
                      className="h-10 px-3 rounded-sm border border-zinc-600 text-zinc-100 text-sm hover:bg-zinc-800 disabled:opacity-50 inline-flex items-center gap-1.5">
                <ArrowsClockwise size={15} /> {busy === "leer" ? "Leyendo…" : "Leer ahora"}</button>
              <button type="button" onClick={desconectar} disabled={!!busy}
                      className="h-10 px-3 rounded-sm border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-800 disabled:opacity-50">Desconectar</button>
            </>
          ) : (
            <button type="button" onClick={conectar} disabled={!!busy} data-testid="conectar-dropi-boton"
                    className="h-10 px-4 rounded-sm btn-cta-grad text-white text-sm font-medium disabled:opacity-50">
              {busy === "conectar" ? "Abriendo Dropi…" : "Conectar Dropi"}</button>
          )}
        </div>
      </div>
      {msg && (
        <p role="status" className={`mt-3 text-sm text-zinc-100 border rounded-sm px-3 py-2 ${msg[0] === "ok" ? "border-emerald-500/50" : "border-red-500/50"}`}>{msg[1]}</p>
      )}
    </section>
  );
}
