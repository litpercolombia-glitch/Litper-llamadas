import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { errorText } from "../lib/assistant";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Sparkle, MagicWand, CheckCircle, Trash, WarningCircle, ListChecks } from "@phosphor-icons/react";

/** Plantillas por industria: rellenan el cuadro de texto, el usuario las ajusta. */
export const INDUSTRY_TEMPLATES = [
  { key: "clinica", label: "Clínica: recordar citas",
    texto: "Somos una clínica. Quiero un agente que llame a los pacientes un día antes para recordarles su cita, confirme si asistirán y, si no pueden, les ofrezca reprogramarla." },
  { key: "inmobiliaria", label: "Inmobiliaria: calificar interesados",
    texto: "Somos una inmobiliaria. Quiero un agente que contacte a las personas que pidieron información de un inmueble, pregunte su presupuesto, la zona que buscan y cuándo quieren mudarse, y agende una visita con un asesor." },
  { key: "restaurante", label: "Restaurante: reservas",
    texto: "Somos un restaurante. Quiero un agente que confirme las reservas del día, pregunte cuántas personas vienen y si hay alguna alergia o celebración especial." },
  { key: "cobranza", label: "Cobranza: recordar pagos",
    texto: "Quiero un agente que recuerde con amabilidad a los clientes que tienen un pago pendiente, les informe el valor y la fecha límite, y registre si se comprometen a pagar y cuándo." },
  { key: "tienda", label: "Tienda en línea: confirmar pedidos",
    texto: "Somos una tienda en línea. Quiero un agente que contacte al cliente después de su compra para confirmar el pedido, la dirección de entrega y el valor a pagar." },
  { key: "oficina", label: "Envíos: paquete por recoger",
    texto: "Quiero un agente que avise al cliente que su paquete lo está esperando en la oficina de la empresa de envíos, le diga hasta qué día puede recogerlo y confirme cuándo irá por él." },
];

const FIELD_CLS = "bg-black/40 border-zinc-700 text-white";

/**
 * Propuestas de MUESTRA para el modo ejemplo (página pública, sin cuenta y
 * sin IA). Son textos fijos escritos a mano: con una cuenta real, la
 * propuesta la escribe el asistente a partir de la frase del usuario.
 */
const DEMO_AGENTS = {
  clinica: {
    nombre: "Recordatorio de citas", proposito: "Recordar la cita y confirmar asistencia",
    tono: "Cercano y respetuoso", idioma: "Español",
    saludo: "Hola, ¿hablo con {{nombre}}? Le llamo de {{empresa}} por su cita de mañana.",
    prompt: "1. Confirma que hablas con el paciente.\n2. Recuérdale la cita: {{fecha}} a las {{hora}} con {{profesional}}.\n3. Pregunta si asistirá.\n4. Si no puede, ofrece reprogramar y toma el día y la hora que prefiere.\n5. No des consejos médicos: si pregunta algo clínico, ofrece que lo llame el consultorio.",
    cierre: "Gracias por su tiempo. Le esperamos en {{empresa}}.",
    herramientas_texto: "confirmar_cita, reprogramar_cita, crear_ticket",
  },
  inmobiliaria: {
    nombre: "Calificación de interesados", proposito: "Entender qué busca y agendar una visita",
    tono: "Profesional y ágil", idioma: "Español",
    saludo: "Hola {{nombre}}, le llamo de {{empresa}} porque pidió información de un inmueble.",
    prompt: "1. Confirma el inmueble por el que preguntó.\n2. Pregunta presupuesto, zona y fecha en que quiere mudarse.\n3. Si encaja, propone una visita y toma día y hora.\n4. Si no encaja, ofrece enviarle opciones parecidas por WhatsApp.\n5. No prometas precios ni condiciones que no estén en la ficha.",
    cierre: "Listo, un asesor le confirma la visita. Gracias por su interés.",
    herramientas_texto: "agendar_visita, enviar_whatsapp, crear_ticket",
  },
  restaurante: {
    nombre: "Confirmación de reservas", proposito: "Confirmar las reservas del día",
    tono: "Amable y breve", idioma: "Español",
    saludo: "Hola {{nombre}}, le llamo de {{empresa}} para confirmar su reserva de hoy.",
    prompt: "1. Confirma hora y número de personas.\n2. Pregunta si hay alergias o una celebración especial.\n3. Si cambia el número de personas, anótalo.\n4. Si cancela, agradece y libera la mesa.",
    cierre: "Perfecto, les esperamos. ¡Hasta pronto!",
    herramientas_texto: "confirmar_reserva, cancelar_reserva",
  },
  cobranza: {
    nombre: "Recordatorio de pago", proposito: "Recordar un pago pendiente y registrar el compromiso",
    tono: "Respetuoso y claro", idioma: "Español",
    saludo: "Hola, ¿hablo con {{nombre}}? Le llamo de {{empresa}} por un pago pendiente.",
    prompt: "1. Verifica que hablas con el titular antes de dar cifras.\n2. Informa el valor ({{valor}}) y la fecha límite ({{fecha_limite}}).\n3. Pregunta si puede pagar y cuándo.\n4. Registra el compromiso de pago.\n5. Nunca presiones ni amenaces: si hay un problema, ofrece que lo llame una persona.",
    cierre: "Gracias. Queda registrado su compromiso de pago.",
    herramientas_texto: "registrar_compromiso, crear_ticket",
  },
  tienda: {
    nombre: "Confirmación de pedidos", proposito: "Confirmar pedido, dirección y valor",
    tono: "Cercano y directo", idioma: "Español",
    saludo: "Hola {{nombre}}, le llamo de {{empresa}} por el pedido que hizo en nuestra tienda.",
    prompt: "1. Confirma el producto y la cantidad.\n2. Confirma la dirección de entrega.\n3. Informa el valor a pagar ({{valor}}).\n4. Si quiere cambiar algo, anótalo y crea un caso para el equipo.",
    cierre: "Gracias por su compra. Le avisamos cuando salga el envío.",
    herramientas_texto: "confirmar_pedido, crear_ticket, enviar_whatsapp",
  },
  oficina: {
    nombre: "Aviso de paquete por recoger", proposito: "Avisar que el paquete espera y confirmar cuándo lo recoge",
    tono: "Amable y concreto", idioma: "Español",
    saludo: "Hola {{nombre}}, le llamo de {{empresa}}: su paquete ya llegó y lo está esperando.",
    prompt: "1. Di dónde está el paquete ({{direccion_oficina}}).\n2. Informa hasta qué día puede recogerlo ({{fecha_limite}}).\n3. Pregunta cuándo irá por él y regístralo.\n4. Si no puede ir, crea un caso para el equipo.",
    cierre: "Gracias. Recuerde llevar su documento al recogerlo.",
    herramientas_texto: "registrar_fecha_recogida, crear_ticket",
  },
};
const DEMO_KEYWORDS = [
  ["clinica", /cl[ií]nic|pacient|cita|consultorio|dental|m[eé]dic/i],
  ["inmobiliaria", /inmobili|inmueble|apartament|arriendo|visita/i],
  ["restaurante", /restaurant|reserva|mesa/i],
  ["cobranza", /cobr|pago|deuda|cartera|factura/i],
  ["oficina", /paquete|recoger|oficina|env[ií]o/i],
  ["tienda", /tienda|pedido|compra|producto/i],
];
function demoProposal(texto) {
  const hit = DEMO_KEYWORDS.find(([, re]) => re.test(texto));
  if (hit) return { id: "ejemplo", ...DEMO_AGENTS[hit[0]] };
  return {
    id: "ejemplo", nombre: "Agente de ejemplo", proposito: "Lo que describiste",
    tono: "Cercano y profesional", idioma: "Español",
    saludo: "Hola, ¿hablo con {{nombre}}? Le llamo de {{empresa}}.",
    prompt: `Tu encargo: ${texto.slice(0, 400)}\n\n1. Preséntate y confirma con quién hablas.\n2. Cumple el encargo paso a paso, con frases cortas.\n3. Si el cliente pide algo fuera del encargo, crea un caso para el equipo.`,
    cierre: "Gracias por su tiempo.",
    herramientas_texto: "crear_ticket",
  };
}
const DEMO_FALTANTES = [
  "Elegir la voz con la que hablará el agente.",
  "Conectar el número de teléfono desde el que llamará.",
  "Completar los datos de tu empresa que el guion usa entre llaves, como {{empresa}}.",
];
const TYPED_FIELDS = ["nombre", "proposito", "tono", "idioma", "saludo", "prompt", "cierre", "herramientas_texto"];

const reducedMotion = () => {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
};

/** Lo que el propio agente deja ver que le falta (además de lo que diga el servidor). */
function localMissing(agent) {
  const out = [];
  if (!agent?.voz_id) out.push({ re: /\bvoz\b/i, text: "Falta elegir la voz del agente. Sin voz no puede llamar." });
  if (!String(agent?.numero || "").trim()) {
    out.push({ re: /n[uú]mero|tel[eé]fon/i, text: "Falta el número de teléfono desde el que llamará (Conexiones → Números)." });
  }
  return out;
}
const faltanteText = (f) => (typeof f === "string" ? f : (f?.label || f?.detalle || f?.campo || JSON.stringify(f)));

const toolsToText = (h) => (Array.isArray(h) ? h.join(", ") : (h || ""));
const textToTools = (t) => String(t || "").split(",").map((s) => s.trim()).filter(Boolean);

/**
 * Crear un agente con un prompt (estilo "propone → revisas → Aplicar").
 *  1. POST /custom-agents/from-prompt {texto} → {agent (borrador), faltantes}
 *  2. Tarjeta revisable con campos editables.
 *  3. "Aplicar y guardar" → PATCH /custom-agents/{id} · "Descartar" → DELETE.
 *
 * `demo` (página pública): mismo componente, sin cuenta ni servidor. Muestra una
 * propuesta de MUESTRA escribiéndose en pantalla, rotulada como ejemplo, y no
 * guarda nada.
 */
export default function AgentFromPrompt({ onApplied, onDiscarded, assistantName = "Lyan", demo = false, seed = null }) {
  const [texto, setTexto] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [proposal, setProposal] = useState(null); // agente propuesto (editable)
  const [faltantes, setFaltantes] = useState([]);
  const [busy, setBusy] = useState(false);
  const [typed, setTyped] = useState(Infinity); // caracteres ya "escritos" en el modo ejemplo
  const timer = useRef(null);
  useEffect(() => () => clearInterval(timer.current), []);

  // Modo ejemplo: la frase se convierte en agente a la vista, campo por campo.
  const runDemo = (t) => {
    const full = demoProposal(t);
    const total = TYPED_FIELDS.reduce((n, k) => n + String(full[k] || "").length, 0);
    setProposal(full); setFaltantes(DEMO_FALTANTES);
    clearInterval(timer.current);
    if (reducedMotion()) { setTyped(Infinity); return; }
    setTyped(0);
    timer.current = setInterval(() => {
      setTyped((n) => {
        if (n + 6 >= total) { clearInterval(timer.current); return Infinity; }
        return n + 6;
      });
    }, 24);
  };
  // `seed` = { key, n }: la página de presentación carga una plantilla desde fuera (solo modo ejemplo).
  const seedN = seed?.n;
  useEffect(() => {
    if (!demo || !seedN) return;
    const t = INDUSTRY_TEMPLATES.find((x) => x.key === seed.key);
    if (!t) return;
    setTexto(t.texto); setError("");
    runDemo(t.texto);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedN]);
  const typing = demo && typed !== Infinity;
  // Texto visible de un campo mientras se "escribe" (los campos van en orden).
  const shown = (key) => {
    const value = String(proposal?.[key] || "");
    if (!typing) return value;
    let offset = 0;
    for (const k of TYPED_FIELDS) { if (k === key) break; offset += String(proposal?.[k] || "").length; }
    return value.slice(0, Math.max(0, typed - offset));
  };

  const setField = (patch) => setProposal((p) => ({ ...p, ...patch }));

  const generate = async () => {
    const t = texto.trim();
    if (t.length < 10) { setError("Cuéntanos un poco más: qué hace tu negocio y qué debe hacer el agente."); return; }
    if (demo) { setError(""); runDemo(t); return; }
    setGenerating(true); setError("");
    try {
      const r = await api.post("/custom-agents/from-prompt", { texto: t }, { timeout: 120000 });
      const agent = r.data?.agent;
      if (!agent?.id) throw new Error("respuesta-sin-agente");
      setProposal({ ...agent, herramientas_texto: toolsToText(agent.herramientas) });
      setFaltantes(Array.isArray(r.data?.faltantes) ? r.data.faltantes : []);
    } catch (e) {
      setError(e?.message === "respuesta-sin-agente"
        ? "El servidor no devolvió una propuesta. Inténtalo de nuevo con una descripción un poco más detallada."
        : errorText(e, "No se pudo generar el agente. Revisa que tu llave de inteligencia artificial esté conectada e inténtalo de nuevo."));
    } finally { setGenerating(false); }
  };

  const apply = async () => {
    if (!proposal?.nombre?.trim()) { toast.error("Ponle un nombre al agente."); return; }
    if (!proposal?.prompt?.trim()) { toast.error("El guion no puede quedar vacío."); return; }
    setBusy(true);
    try {
      const body = {
        nombre: proposal.nombre.trim(),
        proposito: proposal.proposito || "",
        prompt: proposal.prompt,
        saludo: proposal.saludo || "",
        cierre: proposal.cierre || "",
        tono: proposal.tono || "",
        idioma: proposal.idioma || "",
        herramientas: textToTools(proposal.herramientas_texto),
      };
      const r = await api.patch(`/custom-agents/${proposal.id}`, body);
      const saved = r.data?.agent || { ...proposal, ...body };
      const pendientes = [...faltantes.map(faltanteText),
        ...localMissing(saved).filter((m) => !faltantes.some((f) => m.re.test(faltanteText(f)))).map((m) => m.text)];
      if (pendientes.length) toast.warning("Agente guardado, pero todavía no puede llamar: le falta voz o número.");
      else toast.success("Agente guardado.");
      setProposal(null); setFaltantes([]); setTexto("");
      onApplied?.(saved, pendientes);
    } catch (e) {
      toast.error(errorText(e, "No se pudo guardar el agente."));
    } finally { setBusy(false); }
  };

  const discard = async () => {
    if (demo) { clearInterval(timer.current); setTyped(Infinity); setProposal(null); setFaltantes([]); return; }
    setBusy(true);
    try {
      await api.delete(`/custom-agents/${proposal.id}`);
      toast.info("Propuesta descartada.");
      setProposal(null); setFaltantes([]);
      onDiscarded?.();
    } catch (e) {
      toast.error(errorText(e, "No se pudo descartar la propuesta."));
    } finally { setBusy(false); }
  };

  // Faltantes reales: lo que dijo el servidor + lo que el propio agente deja ver.
  const extra = demo ? [] : localMissing(proposal).filter((m) => !faltantes.some((f) => m.re.test(faltanteText(f))));
  const allFaltantes = [...faltantes.map(faltanteText), ...extra.map((m) => m.text)];

  return (
    <section className={`border border-cyan-500/30 bg-cyan-500/5 rounded-sm p-4 sm:p-5 ${demo ? "" : "mb-6"}`}
             data-testid="agent-from-prompt">
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <MagicWand size={18} weight="duotone" className="text-cyan-300" />
        <h3 className="text-lg font-medium text-zinc-100">Describe tu negocio y qué debe hacer el agente</h3>
        {demo && (
          <span className="ml-auto text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border border-yellow-500/20 bg-yellow-500/10 text-yellow-400 rounded-sm"
                data-testid="agent-demo-badge">
            Ejemplo
          </span>
        )}
      </div>
      <p className="text-sm text-zinc-400 mb-3">
        {demo
          ? "Prueba el creador de agentes. Esto es un ejemplo: muestra una propuesta de muestra, no usa inteligencia artificial ni guarda nada."
          : `Escríbelo con tus palabras. ${assistantName} prepara una propuesta y tú decides si la aplicas.`}
      </p>

      {!proposal && (
        <>
          <Textarea rows={4} value={texto}
                    onChange={(e) => { setTexto(e.target.value); if (error) setError(""); }}
                    placeholder="Ej: Somos una clínica dental. Quiero un agente que llame a los pacientes un día antes para recordarles su cita y confirme si asistirán."
                    data-testid="agent-prompt-input"
                    disabled={generating}
                    className={`${FIELD_CLS} text-sm`} />

          <div className="mt-3">
            <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-2">
              O empieza con una plantilla
            </div>
            <div className="flex flex-wrap gap-2" data-testid="agent-prompt-templates">
              {INDUSTRY_TEMPLATES.map((t) => (
                <button key={t.key} type="button" disabled={generating}
                        onClick={() => { setTexto(t.texto); setError(""); }}
                        data-testid={`agent-prompt-chip-${t.key}`}
                        className="px-3 py-1.5 rounded-sm text-xs border border-zinc-700 bg-zinc-950 text-zinc-300 hover:text-white hover:border-zinc-500 transition disabled:opacity-50">
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="mt-3 text-sm px-3 py-2 rounded-sm border border-red-500/30 bg-red-500/10 text-red-300 flex items-start gap-2"
                 role="alert" data-testid="agent-prompt-error">
              <WarningCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex justify-end mt-4">
            <Button onClick={generate} disabled={generating || !texto.trim()}
                    data-testid="agent-prompt-generate"
                    variant={demo ? "outline" : undefined}
                    className={demo
                      ? "rounded-sm border-cyan-500/40 bg-cyan-500/10 text-cyan-100 hover:bg-cyan-500/20 hover:text-white"
                      : "btn-cta-grad rounded-sm"}>
              <Sparkle size={14} weight="fill" className="mr-1.5" />
              {demo ? "Ver el ejemplo" : generating ? "Generando propuesta…" : "Generar agente"}
            </Button>
          </div>
        </>
      )}

      {proposal && (
        <div className="border border-zinc-800 bg-zinc-950 rounded-sm p-4 mt-2" data-testid="agent-proposal-card">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="text-sm font-semibold text-white">
              {demo ? "Así se ve una propuesta" : `Propuesta de ${assistantName} — revísala antes de aplicar`}
            </div>
            <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border border-yellow-500/20 bg-yellow-500/10 text-yellow-400 rounded-sm"
                  data-testid="agent-proposal-estado">
              {demo ? "Ejemplo · no se guarda" : "Borrador guardado — revísalo y pulsa Aplicar para activarlo"}
            </span>
          </div>
          {!demo && (
            <p className="text-xs text-zinc-400 mb-3" data-testid="agent-proposal-nota">
              Ya está en tu lista de agentes como borrador. «Aplicar» guarda tus cambios; el agente solo podrá
              llamar cuando tenga voz y número. «Descartar» lo borra.
            </p>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Nombre</label>
              <Input value={shown("nombre")} readOnly={typing} onChange={(e) => setField({ nombre: e.target.value })}
                     data-testid="agent-proposal-nombre" className={FIELD_CLS} />
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Para qué sirve</label>
              <Input value={shown("proposito")} readOnly={typing} onChange={(e) => setField({ proposito: e.target.value })}
                     data-testid="agent-proposal-proposito" className={FIELD_CLS} />
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Tono</label>
              <Input value={shown("tono")} readOnly={typing} onChange={(e) => setField({ tono: e.target.value })}
                     data-testid="agent-proposal-tono" className={FIELD_CLS} />
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Idioma</label>
              <Input value={shown("idioma")} readOnly={typing} onChange={(e) => setField({ idioma: e.target.value })}
                     data-testid="agent-proposal-idioma" className={FIELD_CLS} />
            </div>
            <div className="md:col-span-2">
              <label className="text-xs text-zinc-400 block mb-1">Saludo</label>
              <Textarea rows={2} value={shown("saludo")} readOnly={typing} onChange={(e) => setField({ saludo: e.target.value })}
                        data-testid="agent-proposal-saludo" className={`${FIELD_CLS} text-sm`} />
            </div>
            <div className="md:col-span-2">
              <label className="text-xs text-zinc-400 block mb-1">Guion (lo que el agente debe hacer y decir)</label>
              <Textarea rows={8} value={shown("prompt")} readOnly={typing} onChange={(e) => setField({ prompt: e.target.value })}
                        data-testid="agent-proposal-prompt" className={`${FIELD_CLS} font-mono text-xs`} />
            </div>
            <div className="md:col-span-2">
              <label className="text-xs text-zinc-400 block mb-1">Cierre</label>
              <Textarea rows={2} value={shown("cierre")} readOnly={typing} onChange={(e) => setField({ cierre: e.target.value })}
                        data-testid="agent-proposal-cierre" className={`${FIELD_CLS} text-sm`} />
            </div>
            <div className="md:col-span-2">
              <label className="text-xs text-zinc-400 block mb-1">Acciones que puede hacer (separadas por coma)</label>
              <Input value={shown("herramientas_texto")} readOnly={typing}
                     onChange={(e) => setField({ herramientas_texto: e.target.value })}
                     data-testid="agent-proposal-herramientas" className={`${FIELD_CLS} font-mono text-xs`} />
            </div>
          </div>

          <div className="mt-4 border border-zinc-800 rounded-sm p-3 bg-zinc-900/40" data-testid="agent-proposal-faltantes">
            <div className="text-[10px] uppercase tracking-widest font-mono text-zinc-500 mb-2 flex items-center gap-1.5">
              <ListChecks size={13} /> Lo que falta para que pueda llamar
            </div>
            {allFaltantes.length === 0 ? (
              <p className="text-xs text-zinc-400" data-testid="agent-proposal-sin-faltantes">
                Tiene voz y número, y el servidor no reportó pendientes. Haz una llamada de prueba antes de usarlo con clientes.
              </p>
            ) : (
              <ul className="text-sm text-zinc-300 space-y-1 list-disc pl-5">
                {allFaltantes.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            )}
          </div>

          {demo && (
            <div className="flex flex-wrap items-center justify-between gap-3 mt-4" data-testid="agent-demo-footer">
              <p className="text-xs text-zinc-400 max-w-md">
                Con tu cuenta, {assistantName} escribe la propuesta a partir de tu frase y tú la aplicas.{" "}
                <Link to="/register" className="text-cyan-300 underline underline-offset-2 hover:text-cyan-200">Crear cuenta</Link>
              </p>
              <Button variant="outline" onClick={discard} data-testid="agent-demo-reset"
                      className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
                Probar con otra frase
              </Button>
            </div>
          )}

          {!demo && (
          <div className="flex flex-wrap justify-end gap-2 mt-4">
            <Button variant="outline" onClick={discard} disabled={busy}
                    data-testid="agent-proposal-discard"
                    className="rounded-sm border-zinc-700 bg-zinc-900 hover:bg-zinc-800">
              <Trash size={13} className="mr-1.5" /> Descartar
            </Button>
            <Button onClick={apply} disabled={busy}
                    data-testid="agent-proposal-apply"
                    className="btn-cta-grad rounded-sm">
              <CheckCircle size={14} weight="fill" className="mr-1.5" />
              {busy ? "Guardando…" : "Aplicar y guardar"}
            </Button>
          </div>
          )}
        </div>
      )}
    </section>
  );
}
