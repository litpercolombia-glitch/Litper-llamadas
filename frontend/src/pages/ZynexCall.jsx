import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import EmptyState from "../components/EmptyState";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Switch } from "../components/ui/switch";
import {
  PhoneCall, ArrowsClockwise, PaperPlaneTilt, Robot, TreeStructure, SlidersHorizontal, MagicWand,
  CheckCircle, WarningCircle, XCircle, Copy, MagnifyingGlass, Prohibit,
} from "@phosphor-icons/react";

const TABS = [
  { key: "panel",     label: "Llamadas",        Icon: PhoneCall,         desc: "Cola, resultados y botones para traer pedidos y llamar." },
  { key: "variables", label: "Variables",       Icon: TreeStructure,     desc: "Qué campo de tu Chatea Pro llena cada dato que dice el agente." },
  { key: "agentes",   label: "Agentes",         Icon: Robot,             desc: "Un agente de voz por estado de Dropi, con su ID de ElevenLabs." },
  { key: "reglas",    label: "Reglas y número", Icon: SlidersHorizontal, desc: "Horario, reintentos, modo prueba, número saliente y webhook." },
];

const ESTADO_CLS = {
  en_cola:   "border-sky-500/30 bg-sky-500/10 text-sky-300",
  bloqueada: "border-yellow-500/30 bg-yellow-500/10 text-yellow-200",
  llamando:  "border-violet-500/30 bg-violet-500/10 text-violet-300",
  terminada: "border-green-500/30 bg-green-500/10 text-green-300",
  cancelada: "border-zinc-600 bg-zinc-800/60 text-zinc-400",
  error:     "border-red-500/30 bg-red-500/10 text-red-300",
};
const ESTADO_TXT = { en_cola: "En cola", bloqueada: "Bloqueada", llamando: "Llamando", terminada: "Terminada", cancelada: "Cancelada", error: "Error" };
const VAR_TXT = {
  cliente: "Nombre del cliente", valor: "Valor a pagar", telefono: "Teléfono", producto: "Producto",
  direccion: "Dirección", ciudad: "Ciudad", transportadora: "Transportadora", guia: "Número de guía",
  novedad: "Novedad del repartidor", dropi_order_id: "ID de la orden en Dropi", estado_dropi: "Estado de Dropi",
};
const TRANS_TXT = {
  texto: "Tal cual", numero: "Solo números", telefono_co: "Teléfono +57", corto: "Corto y en minúscula",
  minusculas: "Minúsculas", nombre_corto: "Primeros 2 nombres", ciudad: "Ciudad limpia",
};

const fecha = (iso) => {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short", timeZone: "America/Bogota" }); }
  catch { return iso; }
};
const cop = (v) => (v ? `$${Number(v).toLocaleString("es-CO")}` : "—");

function Pill({ ok, children }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-sm border ${
      ok ? "border-green-500/30 bg-green-500/10 text-green-300" : "border-zinc-700 bg-zinc-900 text-zinc-400"}`}>
      {ok ? <CheckCircle size={12} weight="fill" /> : <XCircle size={12} />} {children}
    </span>
  );
}

function Card({ title, children, actions }) {
  return (
    <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-5">
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          {title && <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-400">{title}</div>}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}

const btnOut = "h-9 rounded-sm border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-xs";

/* ---------------- Panel ---------------- */
function Panel({ d, recargar }) {
  const [busy, setBusy] = useState("");
  const [filtro, setFiltro] = useState("todas");
  const [userNs, setUserNs] = useState("");
  const [vista, setVista] = useState(null);

  const accion = async (k, fn, ok) => {
    setBusy(k);
    try { const r = await fn(); toast.success(ok(r.data)); await recargar(); }
    catch (e) { toast.error(errorText(e)); }
    finally { setBusy(""); }
  };
  const traer = () => accion("traer", () => api.post("/zcall/recoger", {}, { timeout: 90000 }),
    (r) => `Listo: ${r.encolados} en cola${r.bloqueados ? ` · ${r.bloqueados} bloqueados por datos faltantes` : ""}.${r.nota ? " " + r.nota : ""}`);
  const despachar = () => accion("desp", () => api.post("/zcall/despachar", {}, { timeout: 90000 }),
    (r) => r.nada || r.error || `Procesadas ${(r.procesadas || []).length} llamada(s).`);
  const previsualizar = async () => {
    if (!userNs.trim()) return;
    setBusy("prev");
    try { const r = await api.post("/zcall/previsualizar", { user_ns: userNs.trim() }); setVista(r.data); }
    catch (e) { toast.error(errorText(e)); setVista(null); }
    finally { setBusy(""); }
  };
  const encolar = () => accion("enc", () => api.post("/zcall/encolar", { user_ns: userNs.trim(), agente: vista?.agente }),
    (r) => (r.duplicada ? r.mensaje : r.estado === "bloqueada" ? `Quedó bloqueada: faltan ${r.faltantes.join(", ")}.` : "Puesta en cola."));
  const cancelar = (id) => accion("c" + id, () => api.post(`/zcall/llamadas/${id}/cancelar`), () => "Llamada cancelada.");

  const m = d.metricas || {};
  const filas = useMemo(() => (d.llamadas || []).filter((x) => filtro === "todas" || x.estado === filtro), [d, filtro]);

  return (
    <div className="space-y-5">
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
        {[["En cola", m.en_cola], ["Bloqueadas", m.bloqueadas], ["Terminadas", m.terminadas],
          ["Contacto", m.tasa_contacto != null ? `${m.tasa_contacto}%` : "—"],
          ["Éxito", m.tasa_exito != null ? `${m.tasa_exito}%` : "—"]].map(([l, v]) => (
          <div key={l} className="border border-zinc-800 rounded-sm bg-zinc-900/40 px-4 py-3">
            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-400">{l}</div>
            <div className="text-2xl font-semibold text-white mt-1">{v ?? 0}</div>
          </div>
        ))}
      </div>

      <Card title="Acciones" actions={
        <div className="flex flex-wrap gap-2 text-[11px] text-zinc-400 items-center">
          <span className={`px-2 py-0.5 rounded-sm border ${d.config?.modo === "activo" ? "border-green-500/30 text-green-300" : d.config?.modo === "pausado" ? "border-zinc-600 text-zinc-400" : "border-yellow-500/30 text-yellow-200"}`}>
            Modo {d.config?.modo}
          </span>
          <span>{d.ventana_ahora ? "Dentro del horario de llamadas" : `Próximo horario: ${fecha(d.proxima_ventana)}`}</span>
        </div>}>
        <div className="flex flex-wrap gap-2">
          <Button onClick={traer} disabled={!!busy || !d.conexiones?.chatea} data-testid="zc-traer" className="btn-cta-grad rounded-sm h-9 text-sm">
            <ArrowsClockwise size={14} className={`mr-1.5 ${busy === "traer" ? "animate-spin" : ""}`} />
            {busy === "traer" ? "Trayendo…" : "Traer pedidos de Chatea"}
          </Button>
          <Button variant="outline" onClick={despachar} disabled={!!busy} data-testid="zc-despachar" className={btnOut}>
            <PaperPlaneTilt size={14} className="mr-1.5" /> {busy === "desp" ? "Llamando…" : "Llamar ahora"}
          </Button>
          <Button variant="outline" onClick={recargar} disabled={!!busy} className={btnOut}>
            <ArrowsClockwise size={14} className="mr-1.5" /> Refrescar
          </Button>
        </div>
        <p className="text-xs text-zinc-400 mt-3">
          «Traer pedidos» busca en tu Chatea los contactos cuyo estado de Dropi tiene un agente encendido y los pone en cola.
          También puedes pedírselo a tu Claude (Conexiones → Claude). En modo prueba solo se llama a los números del equipo.
        </p>
        {!d.conexiones?.chatea && <p className="text-xs text-yellow-200/80 mt-2">Conecta Chatea Pro en Conexiones para traer pedidos.</p>}
      </Card>

      <Card title="Un contacto puntual">
        <div className="flex flex-wrap gap-2">
          <Input aria-label="user_ns del contacto" value={userNs} onChange={(e) => setUserNs(e.target.value)} placeholder="user_ns del contacto en Chatea (ej. f140677u…)"
                 className="bg-black/40 border-zinc-700 text-white font-mono text-xs flex-1 min-w-[14rem]" data-testid="zc-userns" />
          <Button variant="outline" onClick={previsualizar} disabled={!userNs.trim() || !!busy} className={btnOut}>
            <MagnifyingGlass size={14} className="mr-1.5" /> {busy === "prev" ? "Leyendo…" : "Ver qué diría el agente"}
          </Button>
        </div>
        {vista && (
          <div className="mt-4 border border-zinc-800 rounded-sm bg-black/30 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="text-zinc-400">Agente:</span> <b className="text-white">{vista.agente || "ninguno"}</b>
              {vista.listo ? <Pill ok>Listo para llamar</Pill> : <span className="text-[11px] px-2 py-0.5 rounded-sm border border-yellow-500/30 bg-yellow-500/10 text-yellow-200">Faltan: {vista.faltantes.join(", ")}</span>}
            </div>
            <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
              {Object.entries(vista.variables || {}).map(([k, v]) => (
                <div key={k} className="flex gap-2 text-xs"><span className="text-zinc-400 w-36 shrink-0">{VAR_TXT[k] || k}</span><span className="text-zinc-200 break-all">{v || "—"}</span></div>
              ))}
            </div>
            {vista.agente && (
              <Button onClick={encolar} disabled={!!busy} className="btn-cta-grad rounded-sm h-9 text-sm mt-4">Poner en cola</Button>
            )}
          </div>
        )}
      </Card>

      <Card title={`Llamadas (${filas.length})`} actions={
        <div className="flex flex-wrap gap-1">
          {["todas", "en_cola", "bloqueada", "terminada", "cancelada", "error"].map((k) => (
            <button key={k} onClick={() => setFiltro(k)}
                    className={`text-[11px] px-2.5 py-1 min-h-[28px] rounded-sm border ${filtro === k ? "border-white text-white" : "border-zinc-800 text-zinc-400 hover:text-white"}`}>
              {k === "todas" ? "Todas" : ESTADO_TXT[k]}
            </button>
          ))}
        </div>}>
        {filas.length === 0 ? (
          <EmptyState icon={PhoneCall} testId="zc-empty" title="Sin llamadas todavía"
                      description="Trae pedidos de Chatea o pídele a tu Claude que suba los pedidos de Dropi." />
        ) : (
          <div className="overflow-x-auto -mx-5 px-5">
            <table className="w-full text-sm min-w-[720px]">
              <thead>
                <tr className="text-left text-[10px] font-mono uppercase tracking-widest text-zinc-400 border-b border-zinc-800">
                  <th className="py-2 pr-3">Cliente</th><th className="py-2 pr-3">Agente</th><th className="py-2 pr-3">Estado</th>
                  <th className="py-2 pr-3">Resultado</th><th className="py-2 pr-3">Valor</th><th className="py-2 pr-3">Próxima / fecha</th><th />
                </tr>
              </thead>
              <tbody>
                {filas.map((x) => (
                  <tr key={x.id} className="border-b border-zinc-900 align-top">
                    <td className="py-2.5 pr-3">
                      <div className="text-white">{x.cliente || "—"}</div>
                      <div className="text-[11px] font-mono text-zinc-400">{x.telefono || "sin teléfono"}{x.dropi_order_id ? ` · #${x.dropi_order_id}` : ""}</div>
                    </td>
                    <td className="py-2.5 pr-3 text-zinc-300">{x.agente}</td>
                    <td className="py-2.5 pr-3">
                      <span className={`text-[11px] px-2 py-0.5 rounded-sm border ${ESTADO_CLS[x.estado] || ""}`}>{ESTADO_TXT[x.estado] || x.estado}</span>
                      {x.motivo_estado && <div className="text-[11px] text-zinc-400 mt-1 max-w-[16rem]">{x.motivo_estado}</div>}
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="text-zinc-200 text-xs font-mono">{x.resultado || "—"}</div>
                      {x.nota && <div className="text-[11px] text-zinc-400 mt-1 max-w-[18rem]">{x.nota}</div>}
                      {x.direccion_corregida && <div className="text-[11px] text-yellow-200/80 mt-1">Dirección: {x.direccion_corregida}</div>}
                    </td>
                    <td className="py-2.5 pr-3 text-zinc-300">{cop(x.valor)}</td>
                    <td className="py-2.5 pr-3 text-xs text-zinc-400">{fecha(x.proxima_llamada || x.actualizado)}</td>
                    <td className="py-2.5 text-right">
                      {["en_cola", "bloqueada"].includes(x.estado) && (
                        <button onClick={() => cancelar(x.id)} aria-label="Cancelar llamada" title="Cancelar"
                                className="h-8 w-8 grid place-items-center rounded-sm border border-zinc-800 hover:bg-red-500/10 hover:border-red-500/40 text-zinc-400 hover:text-red-300">
                          <Prohibit size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

/* ---------------- Variables ---------------- */
function Variables({ d, recargar }) {
  const [campos, setCampos] = useState(null);
  const [busy, setBusy] = useState("");
  const mapa = useMemo(() => Object.fromEntries((d.mapeo || []).map((m) => [m.variable, m])), [d]);

  const leerCampos = async () => {
    setBusy("leer");
    try { const r = await api.get("/zcall/campos-chatea", { timeout: 60000 }); setCampos(r.data.campos || []); }
    catch (e) { toast.error(errorText(e)); }
    finally { setBusy(""); }
  };
  const automapear = async (remapear) => {
    setBusy("auto");
    try { const r = await api.post("/zcall/automapear", { remapear }, { timeout: 60000 }); toast.success(r.data.mensaje); await recargar(); }
    catch (e) { toast.error(errorText(e)); }
    finally { setBusy(""); }
  };
  const guardar = async (variable, ref, transformacion) => {
    const c = (campos || []).find((f) => f.var_ns === ref);
    try {
      await api.put("/zcall/mapeo", {
        variable, fuente: variable === "telefono" && ref === "phone" ? "suscriptor" : "campo", ref,
        nombre_campo: c?.name || mapa[variable]?.nombre_campo, transformacion,
      });
      toast.success(`${VAR_TXT[variable] || variable} guardado.`); await recargar();
    } catch (e) { toast.error(errorText(e)); }
  };

  return (
    <div className="space-y-5">
      <Card title="Enlazar con tu Chatea Pro" actions={
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={leerCampos} disabled={!!busy || !d.conexiones?.chatea} className={btnOut}>
            <ArrowsClockwise size={14} className="mr-1.5" /> {busy === "leer" ? "Leyendo…" : "Leer mis campos"}
          </Button>
          <Button onClick={() => automapear(false)} disabled={!!busy || !d.conexiones?.chatea} className="btn-cta-grad rounded-sm h-9 text-sm" data-testid="zc-automapear">
            <MagicWand size={14} className="mr-1.5" /> {busy === "auto" ? "Enlazando…" : "Enlazar automáticamente"}
          </Button>
        </div>}>
        <p className="text-sm text-zinc-400">
          Cada negocio llama distinto a sus campos. Zynex los encuentra solo (incluidos los de la integración Chatea↔Dropi) y usa
          campos de respaldo cuando el principal viene vacío. Si algo no cuadra, cámbialo abajo.
        </p>
        {!d.conexiones?.chatea && <p className="text-xs text-yellow-200/80 mt-2">Primero conecta Chatea Pro en Conexiones.</p>}
      </Card>

      <Card title="Variables">
        <div className="divide-y divide-zinc-900">
          {(d.variables_disponibles || []).map((v) => {
            const m = mapa[v];
            return (
              <div key={v} className="py-3 grid gap-2 md:grid-cols-[12rem_1fr_11rem] items-center">
                <div>
                  <div className="text-sm text-white">{VAR_TXT[v] || v}</div>
                  <div className="text-[11px] font-mono text-zinc-400">{`{{${v}}}`}</div>
                </div>
                <div className="min-w-0">
                  {campos ? (
                    <select aria-label={`Campo de Chatea para ${VAR_TXT[v] || v}`} defaultValue={m?.ref || ""} onChange={(e) => e.target.value && guardar(v, e.target.value, m?.transformacion || "texto")}
                            className="w-full bg-black/40 border border-zinc-700 rounded-sm text-xs text-white px-2 h-9">
                      <option value="">— Elegir campo —</option>
                      {v === "telefono" && <option value="phone">Teléfono del contacto</option>}
                      {campos.map((c) => <option key={c.var_ns} value={c.var_ns}>{c.name}</option>)}
                    </select>
                  ) : (
                    <div className="text-xs text-zinc-300 break-words">
                      {m ? m.nombre_campo || m.ref : <span className="text-yellow-200/80">Sin enlazar</span>}
                      {m?.refs_alt?.length > 0 && <span className="text-zinc-400"> · {m.refs_alt.length} respaldo(s)</span>}
                    </div>
                  )}
                </div>
                <select aria-label={`Formato de ${VAR_TXT[v] || v}`} value={m?.transformacion || "texto"} disabled={!m}
                        onChange={(e) => guardar(v, m.ref, e.target.value)}
                        className="bg-black/40 border border-zinc-700 rounded-sm text-xs text-white px-2 h-9 disabled:opacity-40">
                  {(d.transformaciones || []).map((t) => <option key={t} value={t}>{TRANS_TXT[t] || t}</option>)}
                </select>
              </div>
            );
          })}
        </div>
      </Card>

      <Card title="Campos y etiquetas que Zynex escribe en Chatea">
        <div className="grid gap-4 md:grid-cols-2 text-xs">
          <ul className="space-y-1.5">{(d.campos_resultado || []).map((c) => <li key={c} className="font-mono text-zinc-300">{c}</li>)}</ul>
          <ul className="space-y-1.5">{(d.etiquetas || []).map((c) => <li key={c} className="font-mono text-zinc-300">{c}</li>)}</ul>
        </div>
        <p className="text-[11px] text-zinc-400 mt-3">Créalos en tu Chatea con estos nombres exactos para ver el resultado de cada llamada en el chat del cliente.</p>
      </Card>
    </div>
  );
}

/* ---------------- Agentes ---------------- */
function AgenteRow({ a, recargar }) {
  const [aid, setAid] = useState(a.elevenlabs_agent_id || "");
  const [busy, setBusy] = useState(false);
  const patch = async (body, ok) => {
    setBusy(true);
    try { await api.patch(`/zcall/agentes/${a.agente}`, body); toast.success(ok); await recargar(); }
    catch (e) { toast.error(errorText(e)); }
    finally { setBusy(false); }
  };
  return (
    <div className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-white">{a.nombre}</div>
          <div className="text-[11px] font-mono text-zinc-400 mt-0.5">Dropi: {a.estados_dropi.join(" · ")}</div>
          <div className="text-[11px] text-zinc-400 mt-1">Necesita: {a.requeridas.map((r) => VAR_TXT[r] || r).join(", ")}</div>
        </div>
        <label className="flex items-center gap-2 text-xs text-zinc-300">
          {a.activo ? "Encendido" : "Apagado"}
          <Switch checked={!!a.activo} disabled={busy}
                  onCheckedChange={(v) => patch({ activo: v }, v ? "Agente encendido." : "Agente apagado.")} />
        </label>
      </div>
      <div className="flex flex-wrap gap-2 mt-3">
        <Input aria-label={`ID de ElevenLabs para ${a.nombre}`} value={aid} onChange={(e) => setAid(e.target.value)} placeholder="ID del agente en ElevenLabs (agent_…)"
               className="bg-black/40 border-zinc-700 text-white font-mono text-xs flex-1 min-w-[14rem]" />
        <Button variant="outline" disabled={busy || aid === (a.elevenlabs_agent_id || "")}
                onClick={() => patch({ elevenlabs_agent_id: aid }, "ID guardado.")} className={btnOut}>Guardar</Button>
      </div>
    </div>
  );
}

function Agentes({ d, recargar }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400 max-w-3xl">
        Cada agente se activa por el estado del pedido en Dropi (los mismos nombres de Dropi). Crea el agente en tu ElevenLabs,
        pega aquí su ID y enciéndelo. Si falta un dato obligatorio, la llamada queda bloqueada y no se hace.
      </p>
      {(d.agentes || []).map((a) => <AgenteRow key={a.agente} a={a} recargar={recargar} />)}
    </div>
  );
}

/* ---------------- Reglas y número ---------------- */
function Reglas({ d, recargar }) {
  const c = d.config || {};
  const [f, setF] = useState({ ventana_ini: c.ventana_ini, ventana_fin: c.ventana_fin, max_intentos: c.max_intentos,
    minutos_entre_intentos: c.minutos_entre_intentos, pre_aviso_whatsapp: !!c.pre_aviso_whatsapp, auto_recoger: !!c.auto_recoger });
  const [equipo, setEquipo] = useState("");
  const [num, setNum] = useState({ proveedor: "twilio", numero: "", direccion: "" });
  const [prueba, setPrueba] = useState({ agente: "confirmacion", telefono: "" });
  const [hook, setHook] = useState("");
  const [busy, setBusy] = useState("");

  const run = async (k, fn, ok) => {
    setBusy(k);
    try { const r = await fn(); toast.success(typeof ok === "function" ? ok(r.data) : ok); await recargar(); return r.data; }
    catch (e) { toast.error(errorText(e)); return null; }
    finally { setBusy(""); }
  };
  const guardarReglas = () => run("reglas", () => api.patch("/zcall/config", { ...f, max_intentos: Number(f.max_intentos), minutos_entre_intentos: Number(f.minutos_entre_intentos) }), "Reglas guardadas.");
  const guardarEquipo = () => run("equipo", () => api.patch("/zcall/config", { numeros_equipo: equipo.split(/[,\n]/).map((x) => x.trim()).filter(Boolean) }), "Números del equipo guardados.");
  const modo = (m) => {
    let confirmacion;
    if (m === "activo") {
      confirmacion = window.prompt("Vas a llamar a clientes reales. Escribe ACTIVAR para confirmar.");
      if (confirmacion !== "ACTIVAR") return;
    }
    run("modo", () => api.patch("/zcall/config", { modo: m, confirmacion }), `Modo ${m}.`);
  };
  const importar = () => run("num", () => api.post("/zcall/numero", num, { timeout: 60000 }), (r) => r.mensaje);
  const webhook = async () => {
    if (d.conexiones?.webhook && !window.confirm("Ya tienes un webhook. Si generas otro, el anterior deja de funcionar. ¿Continuar?")) return;
    const r = await run("hook", () => api.post("/zcall/webhook-url"), "Webhook generado.");
    if (r?.url) setHook(r.url);
  };
  const probar = () => run("prueba", () => api.post("/zcall/llamar-prueba", prueba, { timeout: 60000 }), "Llamada de prueba iniciada.");
  const inp = "bg-black/40 border-zinc-700 text-white text-xs";

  return (
    <div className="space-y-5">
      <Card title="Conexiones">
        <div className="flex flex-wrap gap-2">
          <Pill ok={d.conexiones?.chatea}>Chatea Pro</Pill><Pill ok={d.conexiones?.elevenlabs}>ElevenLabs</Pill>
          <Pill ok={d.conexiones?.numero}>Número {c.numero_saliente || ""}</Pill><Pill ok={d.conexiones?.webhook}>Webhook</Pill>
          <Pill ok={d.conexiones?.claude}>Claude</Pill>
        </div>
        <p className="text-xs text-zinc-400 mt-3">Las llaves de Chatea Pro, ElevenLabs y Twilio se guardan cifradas en Conexiones → Credenciales. Cada negocio usa las suyas.</p>
      </Card>

      <Card title="Modo">
        <div className="flex flex-wrap gap-2">
          {[["prueba", "Prueba (solo equipo)"], ["activo", "Activo (clientes reales)"], ["pausado", "Pausado"]].map(([k, l]) => (
            <Button key={k} variant="outline" disabled={!!busy || c.modo === k} onClick={() => modo(k)}
                    className={`${btnOut} ${c.modo === k ? "!border-white !text-white" : ""}`}>{l}</Button>
          ))}
        </div>
        <p className="text-xs text-zinc-400 mt-3">Para activar se necesitan ElevenLabs, número y webhook conectados, y escribir ACTIVAR.</p>
      </Card>

      <Card title="Horario y reintentos" actions={
        <Button onClick={guardarReglas} disabled={!!busy} className="btn-cta-grad rounded-sm h-9 text-sm">Guardar reglas</Button>}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[["ventana_ini", "Desde (hora Colombia)", "time"], ["ventana_fin", "Hasta", "time"],
            ["max_intentos", "Intentos máximos", "number"], ["minutos_entre_intentos", "Minutos entre intentos", "number"]].map(([k, l, t]) => (
            <label key={k} className="text-xs text-zinc-400 space-y-1 block">{l}
              <Input type={t} value={f[k] ?? ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} className={inp} />
            </label>
          ))}
        </div>
        <div className="flex flex-wrap gap-6 mt-4 text-xs text-zinc-300">
          <label className="flex items-center gap-2"><Switch checked={f.pre_aviso_whatsapp} onCheckedChange={(v) => setF({ ...f, pre_aviso_whatsapp: v })} /> Avisar por WhatsApp antes de llamar</label>
          <label className="flex items-center gap-2"><Switch checked={f.auto_recoger} onCheckedChange={(v) => setF({ ...f, auto_recoger: v })} /> Traer pedidos y llamar solo dentro del horario</label>
        </div>
        <p className="text-[11px] text-zinc-400 mt-2">Lunes a sábado. Solo se reintenta si fue buzón o el cliente pidió que lo llamaran después.</p>
      </Card>

      <Card title="Números del equipo (modo prueba)" actions={
        <Button variant="outline" onClick={guardarEquipo} disabled={!!busy || !equipo.trim()} className={btnOut}>Guardar</Button>}>
        <Input aria-label="Números del equipo" value={equipo} onChange={(e) => setEquipo(e.target.value)} placeholder="3001234567, 3109876543" className={inp} />
        <p className="text-[11px] text-zinc-400 mt-2">Guardados: {(c.numeros_equipo || []).join(", ") || "ninguno"}. Al guardar se reemplaza la lista.</p>
      </Card>

      <Card title="Número saliente" actions={
        <Button variant="outline" onClick={importar} disabled={!!busy || !num.numero.trim()} className={btnOut}>Conectar número</Button>}>
        <div className="grid gap-3 sm:grid-cols-[10rem_1fr_1fr]">
          <select aria-label="Proveedor de telefonía" value={num.proveedor} onChange={(e) => setNum({ ...num, proveedor: e.target.value })}
                  className="bg-black/40 border border-zinc-700 rounded-sm text-xs text-white px-2 h-9">
            <option value="twilio">Twilio</option><option value="sip">SIP trunk</option>
          </select>
          <Input aria-label="Número saliente" value={num.numero} onChange={(e) => setNum({ ...num, numero: e.target.value })} placeholder="+57 300 000 0000" className={inp} />
          {num.proveedor === "sip" && <Input aria-label="Dirección del trunk SIP" value={num.direccion} onChange={(e) => setNum({ ...num, direccion: e.target.value })} placeholder="sip.tuproveedor.com" className={inp} />}
        </div>
        <p className="text-[11px] text-zinc-400 mt-2">Se importa a tu propia cuenta de ElevenLabs. Twilio usa el SID y token que guardaste en Credenciales.</p>
      </Card>

      <Card title="Webhook de resultados" actions={
        <Button variant="outline" onClick={webhook} disabled={!!busy} className={btnOut}>{d.conexiones?.webhook ? "Generar nuevo" : "Generar webhook"}</Button>}>
        {hook ? (
          <div className="flex flex-wrap gap-2 items-center">
            <code className="text-xs font-mono text-zinc-200 break-all flex-1">{hook}</code>
            <Button size="sm" variant="outline" className={btnOut} onClick={() => navigator.clipboard.writeText(hook).then(() => toast.success("Copiada."))}><Copy size={13} className="mr-1" />Copiar</Button>
          </div>
        ) : <p className="text-xs text-zinc-400">Pégalo en ElevenLabs → Agents → Settings → Post-call webhook. Solo se muestra una vez.</p>}
      </Card>

      <Card title="Llamada de prueba" actions={
        <Button onClick={probar} disabled={!!busy || !prueba.telefono.trim()} className="btn-cta-grad rounded-sm h-9 text-sm">Llamar</Button>}>
        <div className="grid gap-3 sm:grid-cols-2">
          <select aria-label="Agente para la llamada de prueba" value={prueba.agente} onChange={(e) => setPrueba({ ...prueba, agente: e.target.value })}
                  className="bg-black/40 border border-zinc-700 rounded-sm text-xs text-white px-2 h-9">
            {(d.agentes || []).map((a) => <option key={a.agente} value={a.agente}>{a.nombre}</option>)}
          </select>
          <Input aria-label="Número del equipo para la prueba" value={prueba.telefono} onChange={(e) => setPrueba({ ...prueba, telefono: e.target.value })} placeholder="Número del equipo" className={inp} />
        </div>
        <p className="text-[11px] text-zinc-400 mt-2 flex items-start gap-1.5"><WarningCircle size={13} className="mt-0.5 shrink-0" />Solo números del equipo guardados arriba. Consume créditos de tu ElevenLabs.</p>
      </Card>
    </div>
  );
}

export default function ZynexCallPage() {
  const initial = new URLSearchParams(window.location.search).get("tab") || "panel";
  const [tab, setTab] = useState(TABS.find((t) => t.key === initial) ? initial : "panel");
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  const recargar = useCallback(async () => {
    try { const r = await api.get("/zcall/estado"); setD(r.data); setErr(""); }
    catch (e) { setErr(errorText(e, "No se pudo cargar Zynex Call.")); }
  }, []);
  useEffect(() => { recargar(); }, [recargar]);

  const current = TABS.find((t) => t.key === tab) || TABS[0];
  const switchTab = (k) => {
    setTab(k);
    const url = new URL(window.location.href); url.searchParams.set("tab", k);
    window.history.replaceState({}, "", url.toString());
  };

  return (
    <Layout title="Llamadas" subtitle={current.desc}>
      <div className="flex flex-wrap gap-1 border-b border-zinc-800 mb-6" data-testid="zc-tabs">
        {TABS.map(({ key, label, Icon }) => (
          <button key={key} onClick={() => switchTab(key)} data-testid={`zc-tab-${key}`}
                  className={`px-4 py-2.5 text-sm font-medium flex items-center gap-2 border-b-2 -mb-px transition ${
                    tab === key ? "text-white border-white" : "text-zinc-400 border-transparent hover:text-white hover:border-zinc-600"}`}>
            <Icon size={16} weight="duotone" /> {label}
          </button>
        ))}
      </div>
      {err && <div role="alert" className="text-sm px-3 py-2 rounded-sm border border-red-500/30 bg-red-500/10 text-red-300 mb-4">{err}</div>}
      {!d && !err && <div className="text-zinc-400 font-mono text-sm">Cargando…</div>}
      {d && tab === "panel" && <Panel d={d} recargar={recargar} />}
      {d && tab === "variables" && <Variables d={d} recargar={recargar} />}
      {d && tab === "agentes" && <Agentes d={d} recargar={recargar} />}
      {d && tab === "reglas" && <Reglas d={d} recargar={recargar} />}
    </Layout>
  );
}
