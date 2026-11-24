import { useEffect, useState } from "react";
import { api, formatDateTime } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Switch } from "./ui/switch";
import EmptyState from "./EmptyState";
import {
  Lightning, Plus, TrashSimple, Sparkle, Flask, PencilSimple, CheckCircle, XCircle, ClockCounterClockwise,
} from "@phosphor-icons/react";

const FIELD_CLS = "bg-black/40 border-zinc-700 text-white";
const SELECT_CLS = "w-full h-9 rounded-md bg-black/40 border border-zinc-700 text-white text-sm px-2 focus:outline-none focus:border-zinc-500";

const EVENTOS = {
  pedido_creado: "Cuando se crea un pedido o registro",
  pedido_estado: "Cuando un pedido cambia de estado",
  llamada_terminada: "Cuando termina una llamada",
  mensaje_entrante: "Cuando llega un mensaje de WhatsApp",
  horario: "A una hora fija",
};
const ACCIONES = {
  enviar_whatsapp: "Enviar un WhatsApp",
  crear_tarea: "Crear una tarea para el equipo",
  lanzar_llamada: "Hacer una llamada con un agente",
  llamar_herramienta_mcp: "Usar una herramienta de mis conectores",
};
const OPS = { igual: "es igual a", contiene: "contiene", mayor: "es mayor que", menor: "es menor que" };
const TEL_DEFAULT = { mensaje_entrante: "{{phone}}", llamada_terminada: "{{telefono}}" };

const nuevaRegla = () => ({
  nombre: "", activa: true, limite_diario: 100,
  trigger: { tipo: "pedido_creado", filtro: {}, cron: "" },
  accion: { tipo: "crear_tarea", params: { descripcion: "", tipo: "seguimiento" } },
});

/** filtro del servidor {campo: valor | {op: valor}} ↔ filas editables. */
const filtroAFilas = (filtro) => {
  const filas = [];
  Object.entries(filtro || {}).forEach(([campo, cond]) => {
    if (cond && typeof cond === "object") Object.entries(cond).forEach(([op, valor]) => filas.push({ campo, op, valor: String(valor ?? "") }));
    else filas.push({ campo, op: "igual", valor: String(cond ?? "") });
  });
  return filas;
};
const filasAFiltro = (filas) => {
  const out = {};
  filas.filter((f) => f.campo.trim() && String(f.valor).trim() !== "").forEach((f) => {
    const campo = f.campo.trim();
    if (f.op === "igual" && out[campo] === undefined) out[campo] = f.valor;
    else out[campo] = { ...(typeof out[campo] === "object" ? out[campo] : (out[campo] !== undefined ? { igual: out[campo] } : {})), [f.op]: f.valor };
  });
  return out;
};

const resumenRegla = (r) => {
  const cuando = r.trigger?.tipo === "horario" ? `Horario (${r.trigger?.cron})` : (EVENTOS[r.trigger?.tipo] || r.trigger?.tipo);
  return `${cuando} → ${ACCIONES[r.accion?.tipo] || r.accion?.tipo}`;
};

function Editor({ inicial, meta, agentes, onCancel, onSaved, propuesta }) {
  const [r, setR] = useState(() => ({
    ...nuevaRegla(), ...inicial,
    trigger: { ...nuevaRegla().trigger, ...(inicial?.trigger || {}) },
    accion: { tipo: inicial?.accion?.tipo || "crear_tarea", params: { ...(inicial?.accion?.params || nuevaRegla().accion.params) } },
  }));
  const [filas, setFilas] = useState(() => filtroAFilas(inicial?.trigger?.filtro));
  const [argsTxt, setArgsTxt] = useState(() => JSON.stringify(inicial?.accion?.params?.args || {}, null, 2));
  // Datos de la plantilla, uno por renglón: «nombre = valor o {{campo}}».
  const [ppTxt, setPpTxt] = useState(() => Object.entries(inicial?.accion?.params?.plantilla_params || {})
    .map(([k, v]) => `${k} = ${v}`).join("\n"));
  const [saving, setSaving] = useState(false);
  const campos = (meta?.campos || {})[r.trigger.tipo] || [];
  const p = r.accion.params || {};
  const setP = (patch) => setR((x) => ({ ...x, accion: { ...x.accion, params: { ...x.accion.params, ...patch } } }));
  const setTipoAccion = (tipo) => {
    const base = {
      enviar_whatsapp: { telefono: "", mensaje: "", plantilla: "" },
      crear_tarea: { descripcion: "", tipo: "seguimiento" },
      lanzar_llamada: { agent_id: agentes[0]?.id || "", telefono: "" },
      llamar_herramienta_mcp: { herramienta: "", args: {} },
    }[tipo];
    setR((x) => ({ ...x, accion: { tipo, params: base } }));
  };

  const save = async () => {
    if (!r.nombre.trim()) { toast.error("Ponle un nombre a la regla."); return; }
    const params = { ...p };
    if (r.accion.tipo === "llamar_herramienta_mcp") {
      try { params.args = argsTxt.trim() ? JSON.parse(argsTxt) : {}; }
      catch { toast.error("Los argumentos deben ser un JSON válido, por ejemplo {}."); return; }
    }
    if (r.accion.tipo === "enviar_whatsapp") {
      const pp = {};
      ppTxt.split("\n").map((l) => l.trim()).filter(Boolean).forEach((l) => {
        const i = l.indexOf("=");
        if (i > 0) pp[l.slice(0, i).trim()] = l.slice(i + 1).trim();
      });
      params.plantilla_params = (params.plantilla || "").trim() ? pp : {};
    }
    const trigger = { tipo: r.trigger.tipo, filtro: filasAFiltro(filas) };
    if (r.trigger.tipo === "horario") trigger.cron = (r.trigger.cron || "").trim();
    const body = { nombre: r.nombre.trim(), activa: !!r.activa, limite_diario: Number(r.limite_diario) || 100,
                   trigger, accion: { tipo: r.accion.tipo, params } };
    setSaving(true);
    try {
      const res = inicial?.id ? await api.patch(`/automations/${inicial.id}`, body) : await api.post("/automations", body);
      toast.success(inicial?.id ? "Regla actualizada." : "Regla creada.");
      onSaved(res.data?.rule);
    } catch (e) {
      toast.error(errorText(e, "No se pudo guardar la regla."));
    } finally { setSaving(false); }
  };

  const telPlaceholder = r.trigger.tipo === "horario" ? "+573001112233"
    : `Vacío = ${TEL_DEFAULT[r.trigger.tipo] || "{{customer_phone}}"}`;

  return (
    <div className="border border-zinc-700 rounded-sm bg-zinc-900/60 p-4 md:p-5 space-y-4" data-testid="automation-editor">
      {propuesta && (
        <div className="text-xs text-cyan-200 border border-cyan-500/30 bg-cyan-500/5 rounded-sm px-3 py-2" data-testid="automation-proposal-note">
          Propuesta de la IA. Revísala y ajústala: no se guarda hasta que pulses «Guardar».
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_10rem] gap-3">
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Nombre</label>
          <Input value={r.nombre} onChange={(e) => setR({ ...r, nombre: e.target.value })} maxLength={120}
                 placeholder="Ej: Avisar cuando entra un pedido" className={FIELD_CLS} data-testid="automation-nombre" />
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Límite por día</label>
          <Input type="number" min={1} max={1000} value={r.limite_diario}
                 onChange={(e) => setR({ ...r, limite_diario: e.target.value })} className={FIELD_CLS} data-testid="automation-limite" />
        </div>
      </div>

      <div>
        <label className="text-xs text-zinc-400 block mb-1">¿Cuándo se ejecuta?</label>
        <select value={r.trigger.tipo} data-testid="automation-evento" className={SELECT_CLS}
                onChange={(e) => { setR({ ...r, trigger: { ...r.trigger, tipo: e.target.value } }); setFilas([]); }}>
          {Object.entries(EVENTOS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        {r.trigger.tipo === "horario" && (
          <div className="mt-2">
            <Input value={r.trigger.cron || ""} onChange={(e) => setR({ ...r, trigger: { ...r.trigger, cron: e.target.value } })}
                   placeholder="0 9 * * 1-5" className={`${FIELD_CLS} font-mono`} data-testid="automation-cron" />
            <p className="text-[11px] text-zinc-500 mt-1">
              Formato: minuto hora día mes día-de-semana, en la hora de tu negocio. «0 9 * * 1-5» = lunes a viernes a las 9:00.
              Como mínimo cada 15 minutos.
            </p>
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-zinc-400">Solo si… (opcional)</label>
          <button onClick={() => setFilas([...filas, { campo: campos[0] || "", op: "igual", valor: "" }])}
                  className="text-xs text-cyan-300 hover:text-cyan-200" data-testid="automation-add-filtro">+ condición</button>
        </div>
        {filas.length === 0 && <p className="text-xs text-zinc-500">Sin condiciones: se ejecuta siempre que ocurra el evento.</p>}
        <div className="space-y-2">
          {filas.map((f, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2" data-testid={`automation-filtro-${i}`}>
              <select value={f.campo} className={SELECT_CLS}
                      onChange={(e) => setFilas(filas.map((x, j) => (j === i ? { ...x, campo: e.target.value } : x)))}>
                {(campos.includes(f.campo) ? campos : [f.campo, ...campos]).map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <select value={f.op} className={SELECT_CLS}
                      onChange={(e) => setFilas(filas.map((x, j) => (j === i ? { ...x, op: e.target.value } : x)))}>
                {Object.entries(OPS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
              <Input value={f.valor} placeholder="valor" className={FIELD_CLS}
                     onChange={(e) => setFilas(filas.map((x, j) => (j === i ? { ...x, valor: e.target.value } : x)))} />
              <button onClick={() => setFilas(filas.filter((_, j) => j !== i))} aria-label="Quitar condición"
                      className="text-zinc-500 hover:text-red-400 px-1"><TrashSimple size={14} /></button>
            </div>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-zinc-400 block mb-1">¿Qué hace?</label>
        <select value={r.accion.tipo} onChange={(e) => setTipoAccion(e.target.value)}
                data-testid="automation-accion" className={SELECT_CLS}>
          {Object.entries(ACCIONES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <div className="mt-2 space-y-2">
          {r.accion.tipo === "enviar_whatsapp" && (<>
            <Input value={p.telefono || ""} onChange={(e) => setP({ telefono: e.target.value })}
                   placeholder={`Teléfono · ${telPlaceholder}`} className={FIELD_CLS} data-testid="automation-telefono" />
            <Textarea rows={3} value={p.mensaje || ""} onChange={(e) => setP({ mensaje: e.target.value })} maxLength={1500}
                      placeholder="Mensaje. Ej: Hola {{customer_name}}, recibimos tu pedido." className={`${FIELD_CLS} text-sm`} data-testid="automation-mensaje" />
            <Input value={p.plantilla || ""} onChange={(e) => setP({ plantilla: e.target.value })}
                   placeholder="Plantilla aprobada (opcional)" className={FIELD_CLS} data-testid="automation-plantilla" />
            {(p.plantilla || "").trim() && (<>
              <Textarea rows={2} value={ppTxt} onChange={(e) => setPpTxt(e.target.value)}
                        placeholder={"Datos de la plantilla, uno por renglón:\nnombre = {{customer_name}}"}
                        className={`${FIELD_CLS} text-sm font-mono`} data-testid="automation-plantilla-params" />
              <p className="text-[11px] text-zinc-500">
                A la plantilla solo se le envían los datos que escribas aquí, nada más del pedido o del mensaje.
              </p>
            </>)}
            <p className="text-[11px] text-zinc-500">
              WhatsApp solo permite texto libre si la persona te escribió en las últimas 24 horas; fuera de ese plazo usa una plantilla aprobada.
              Para no saturar a nadie, al mismo número se le envían como máximo 5 mensajes al día, con 5 minutos entre uno y otro.
            </p>
          </>)}
          {r.accion.tipo === "crear_tarea" && (<>
            <Textarea rows={2} value={p.descripcion || ""} onChange={(e) => setP({ descripcion: e.target.value })} maxLength={1000}
                      placeholder="Descripción. Ej: Llamar a {{customer_name}} para confirmar." className={`${FIELD_CLS} text-sm`} data-testid="automation-descripcion" />
            <Input value={p.tipo || ""} onChange={(e) => setP({ tipo: e.target.value })} placeholder="Tipo (ej. seguimiento)" className={FIELD_CLS} />
          </>)}
          {r.accion.tipo === "lanzar_llamada" && (<>
            <select value={p.agent_id || ""} onChange={(e) => setP({ agent_id: e.target.value })} className={SELECT_CLS} data-testid="automation-agente">
              <option value="">Elige un agente…</option>
              {agentes.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
            </select>
            {agentes.length === 0 && <p className="text-[11px] text-amber-300">Aún no tienes agentes de voz. Crea uno en la pestaña Agentes.</p>}
            <Input value={p.telefono || ""} onChange={(e) => setP({ telefono: e.target.value })}
                   placeholder={`Teléfono · ${telPlaceholder}`} className={FIELD_CLS} />
            <p className="text-[11px] text-zinc-500">
              Para no molestar a nadie, al mismo número se le hacen como máximo 3 llamadas al día, con 30 minutos entre una y otra.
            </p>
          </>)}
          {r.accion.tipo === "llamar_herramienta_mcp" && (<>
            <Input value={p.herramienta || ""} onChange={(e) => setP({ herramienta: e.target.value })}
                   placeholder="mcp__servidor__herramienta" className={`${FIELD_CLS} font-mono`} data-testid="automation-herramienta" />
            <Textarea rows={3} value={argsTxt} onChange={(e) => setArgsTxt(e.target.value)}
                      placeholder='Argumentos en JSON, ej. {"correo": "{{customer_phone}}"}' className={`${FIELD_CLS} text-sm font-mono`} />
            <p className="text-[11px] text-zinc-500">Solo herramientas activas en Conexiones y que no exijan confirmación de una persona.</p>
          </>)}
          {campos.length > 0 && (
            <p className="text-[11px] text-zinc-500 break-words">
              Datos que puedes insertar: {campos.map((c) => `{{${c}}}`).join(" ")}
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 justify-end">
        <Button variant="outline" onClick={onCancel} className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-9">Cancelar</Button>
        <Button onClick={save} disabled={saving} className="btn-cta-grad rounded-sm h-9" data-testid="automation-save">
          {saving ? "Guardando…" : "Guardar"}
        </Button>
      </div>
    </div>
  );
}

/** Pestaña «Automatizaciones»: /automations (CRUD, from-prompt, dry-run, runs). */
export default function Automations() {
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({ campos: {}, max: 50 });
  const [runs, setRuns] = useState([]);
  const [agentes, setAgentes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [editing, setEditing] = useState(null);   // null | {regla, propuesta}
  const [texto, setTexto] = useState("");
  const [proposing, setProposing] = useState(false);
  const [pruebas, setPruebas] = useState({});      // id → resultado de «Probar sin enviar»
  const [busyId, setBusyId] = useState(null);

  const load = async () => {
    setLoadError("");
    try {
      const [a, h] = await Promise.all([api.get("/automations"), api.get("/automations/runs")]);
      setItems(a.data?.items || []);
      setMeta({ campos: a.data?.campos || {}, max: a.data?.max || 50 });
      setRuns(h.data?.items || []);
    } catch (e) {
      setLoadError(errorText(e, "No se pudieron cargar las automatizaciones."));
    } finally { setLoading(false); }
  };
  useEffect(() => {
    load();
    api.get("/custom-agents").then((r) => setAgentes(r.data?.agents || [])).catch(() => setAgentes([]));
  }, []);

  const toggle = async (r, activa) => {
    setItems((xs) => xs.map((x) => (x.id === r.id ? { ...x, activa } : x)));
    try {
      await api.patch(`/automations/${r.id}`, { activa });
      toast.success(activa ? "Regla activada." : "Regla en pausa.");
    } catch (e) {
      setItems((xs) => xs.map((x) => (x.id === r.id ? { ...x, activa: !activa } : x)));
      toast.error(errorText(e, "No se pudo cambiar la regla."));
    }
  };
  const borrar = async (r) => {
    if (!window.confirm(`¿Borrar la regla «${r.nombre}»?`)) return;
    try { await api.delete(`/automations/${r.id}`); toast.success("Regla borrada."); load(); }
    catch (e) { toast.error(errorText(e, "No se pudo borrar la regla.")); }
  };
  const probar = async (r) => {
    setBusyId(r.id);
    try {
      const res = await api.post(`/automations/${r.id}/dry-run`, {});
      setPruebas((p) => ({ ...p, [r.id]: res.data }));
    } catch (e) { toast.error(errorText(e, "No se pudo probar la regla.")); }
    finally { setBusyId(null); }
  };
  const proponer = async () => {
    if (texto.trim().length < 8) { toast.error("Describe la regla con un poco más de detalle."); return; }
    setProposing(true);
    try {
      const res = await api.post("/automations/from-prompt", { texto: texto.trim() }, { timeout: 90000 });
      setEditing({ regla: { ...res.data.rule, activa: true }, propuesta: true });
    } catch (e) { toast.error(errorText(e, "No se pudo proponer la regla.")); }
    finally { setProposing(false); }
  };

  if (loading) return <div className="text-zinc-500 font-mono text-sm" data-testid="automations-loading">Cargando…</div>;
  if (loadError) {
    return (
      <div className="border border-red-500/30 bg-red-500/5 rounded-sm p-4 text-sm text-red-300" data-testid="automations-error">
        {loadError} <button onClick={() => { setLoading(true); load(); }} className="underline ml-2">Reintentar</button>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="automations">
      {/* Describe la regla */}
      <section className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-4 md:p-5" data-testid="automation-from-prompt">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-1">
          <Sparkle size={16} weight="duotone" className="text-zinc-400" /> Describe la regla
        </h3>
        <p className="text-xs text-zinc-500 mb-3">Escríbela con tus palabras y te proponemos la regla para que la revises antes de guardarla.</p>
        <Textarea rows={2} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={2000}
                  placeholder="Ej: Cuando entre un pedido de más de 200, crea una tarea para llamar al cliente."
                  className={`${FIELD_CLS} text-sm`} data-testid="automation-prompt-text" />
        <div className="flex flex-wrap gap-2 mt-3">
          <Button onClick={proponer} disabled={proposing} className="btn-cta-grad rounded-sm h-9" data-testid="automation-prompt-run">
            {proposing ? "Pensando…" : "Proponer regla"}
          </Button>
          <Button variant="outline" onClick={() => setEditing({ regla: nuevaRegla(), propuesta: false })}
                  disabled={items.length >= meta.max} data-testid="automation-new"
                  className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-9">
            <Plus size={14} className="mr-1" /> Nueva regla
          </Button>
        </div>
      </section>

      {editing && (
        <Editor key={editing.regla.id || (editing.propuesta ? "propuesta" : "nueva")}
                inicial={editing.regla} propuesta={editing.propuesta} meta={meta} agentes={agentes}
                onCancel={() => setEditing(null)}
                onSaved={() => { setEditing(null); setTexto(""); load(); }} />
      )}

      {/* Lista */}
      {items.length === 0 && !editing ? (
        <EmptyState
          icon={Lightning}
          testId="automations-empty"
          title="Aún no tienes automatizaciones"
          description="Una automatización hace algo por ti cuando pasa algo en tu negocio: por ejemplo, crear una tarea cuando entra un pedido o enviar un WhatsApp cuando termina una llamada."
          action={{ label: "Crear mi primera regla", onClick: () => setEditing({ regla: nuevaRegla(), propuesta: false }) }}
          prompt="Crea una automatización que cree una tarea cada vez que entre un pedido nuevo."
        />
      ) : (
        <div className="space-y-2" data-testid="automations-list">
          <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500">
            Reglas · {items.length} de {meta.max}
          </div>
          {items.map((r) => (
            <div key={r.id} className="border border-zinc-800 rounded-sm bg-zinc-900/40 p-3 md:p-4" data-testid={`automation-${r.id}`}>
              <div className="flex items-start gap-3">
                <Switch checked={!!r.activa} onCheckedChange={(v) => toggle(r, v)} aria-label="Activar o pausar"
                        data-testid={`automation-toggle-${r.id}`} className="mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white break-words">{r.nombre}</div>
                  <div className="text-xs text-zinc-400 break-words">{resumenRegla(r)}</div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">
                    {r.activa ? "Activa" : "En pausa"} · límite {r.limite_diario}/día
                    {r.last_run_at ? ` · última vez ${formatDateTime(r.last_run_at)}` : " · aún no se ha ejecutado"}
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-3">
                <Button variant="outline" onClick={() => probar(r)} disabled={busyId === r.id}
                        data-testid={`automation-dryrun-${r.id}`}
                        className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-8 text-xs">
                  <Flask size={13} className="mr-1" /> {busyId === r.id ? "Probando…" : "Probar sin enviar"}
                </Button>
                <Button variant="outline" onClick={() => setEditing({ regla: r, propuesta: false })}
                        data-testid={`automation-edit-${r.id}`}
                        className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800 h-8 text-xs">
                  <PencilSimple size={13} className="mr-1" /> Editar
                </Button>
                <Button variant="outline" onClick={() => borrar(r)} data-testid={`automation-delete-${r.id}`}
                        className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-red-950 hover:text-red-300 h-8 text-xs">
                  <TrashSimple size={13} className="mr-1" /> Borrar
                </Button>
              </div>
              {pruebas[r.id] && (
                <div className="mt-3 border border-zinc-800 bg-black/30 rounded-sm p-3 text-xs" data-testid={`automation-dryrun-result-${r.id}`}>
                  <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-1">
                    Prueba con un ejemplo · no se envió nada
                  </div>
                  <div className="text-zinc-200 break-words">{pruebas[r.id].que_haria}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Historial */}
      <section data-testid="automation-runs">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <ClockCounterClockwise size={16} weight="duotone" className="text-zinc-400" /> Historial de ejecuciones
          </h3>
          <button onClick={load} className="text-xs text-cyan-300 hover:text-cyan-200" data-testid="automation-runs-refresh">Actualizar</button>
        </div>
        {runs.length === 0 ? (
          <EmptyState compact icon={ClockCounterClockwise} testId="automation-runs-empty"
                      title="Todavía no se ha ejecutado ninguna regla"
                      description="Cada vez que una regla se ejecute verás aquí qué hizo y si salió bien." />
        ) : (
          <div className="border border-zinc-800 rounded-sm divide-y divide-zinc-800">
            {runs.map((x) => (
              <div key={x.id} className="p-3 flex items-start gap-2 text-xs" data-testid={`automation-run-${x.id}`}>
                {x.ok ? <CheckCircle size={15} weight="fill" className="text-emerald-400 shrink-0 mt-0.5" />
                      : <XCircle size={15} weight="fill" className="text-red-400 shrink-0 mt-0.5" />}
                <div className="flex-1 min-w-0">
                  <div className="text-zinc-200 break-words">{x.rule_nombre || "Regla"} <span className="text-zinc-500">· {formatDateTime(x.created_at)}</span></div>
                  <div className={`break-words ${x.ok ? "text-zinc-400" : "text-red-300"}`}>{x.detalle}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
